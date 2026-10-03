"""
Vercel Serverless Function: POST /api/recommendations
Native Vercel Python entrypoint with 15-second execution timeout safeguard and LLM fallback resilience.
"""
from http.server import BaseHTTPRequestHandler
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Bootstrap project root to sys.path for serverless execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_4.engine import RecommendationEngine
from phase_5.generator import (
    DeterministicMockProvider,
    GeminiProvider,
    RecommendationGenerator,
    TemplateFallbackProvider,
)
from phase_7.formatter import ResponseFormatter
from phase_8.config import get_deployment_config

logger = logging.getLogger(__name__)

# Reusable serverless cold-start singleton cache
_cached_engine = None
_cached_generator = None


def get_cached_engine():
    global _cached_engine
    if _cached_engine is None:
        _cached_engine = RecommendationEngine()
    return _cached_engine


def get_cached_generator(provider_name=None):
    global _cached_generator
    config = get_deployment_config()

    if provider_name == "mock":
        return RecommendationGenerator(provider=DeterministicMockProvider())
    elif provider_name == "template":
        return RecommendationGenerator(provider=TemplateFallbackProvider())
    elif provider_name == "gemini":
        return RecommendationGenerator(provider=GeminiProvider(api_key=config.gemini_api_key))

    if _cached_generator is None:
        if config.has_gemini_credentials:
            _cached_generator = RecommendationGenerator(
                provider=GeminiProvider(api_key=config.gemini_api_key)
            )
        else:
            _cached_generator = RecommendationGenerator(
                provider=DeterministicMockProvider()
            )
    return _cached_generator


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function HTTP request handler."""

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, If-None-Match")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        start_time = time.perf_counter()
        config = get_deployment_config()
        timeout_budget = config.timeout_seconds  # Default 15s

        # 1. Parse request body
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_json_error(400, "EMPTY_PAYLOAD", "Request body cannot be empty.")
                return

            raw_body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(raw_body)
        except Exception as e:
            self._send_json_error(400, "INVALID_JSON", f"Malformed JSON request: {str(e)}")
            return

        # 2. Extract and sanitize inputs
        location = data.get("location", "").strip()
        if not location:
            self._send_json_error(400, "MISSING_LOCATION", "Field 'location' is required.")
            return

        cuisines = data.get("cuisines")
        if isinstance(cuisines, str):
            cuisines = [c.strip() for c in cuisines.split(",") if c.strip()]
        elif not isinstance(cuisines, list):
            cuisines = []

        max_budget = data.get("max_budget", 1000)
        min_rating = data.get("min_rating", 3.8)
        vibe_or_notes = data.get("vibe_or_notes")
        top_k = min(max(int(data.get("top_k", 5)), 1), 20)
        provider_override = data.get("provider")

        query_payload = {
            "location": location,
            "cuisines": cuisines,
            "max_budget": max_budget,
            "min_rating": min_rating,
            "vibe_or_notes": vibe_or_notes,
            "online_order_only": bool(data.get("online_order_only", False)),
            "book_table_only": bool(data.get("book_table_only", False)),
        }

        # 3. Execute with 15-second safeguard & error fallback
        try:
            engine = get_cached_engine()
            generator = get_cached_generator(provider_override)

            # Check elapsed time before calling LLM
            time_left = timeout_budget - (time.perf_counter() - start_time)
            if time_left < 2.0:
                # Less than 2s left, engage fast template fallback to guarantee < 15s return
                logger.warning("Approaching timeout budget (%s left). Engaging fast fallback.", time_left)
                generator = RecommendationGenerator(provider=TemplateFallbackProvider())

            try:
                raw_response = generator.recommend_from_query(
                    query=query_payload,
                    recommendation_engine=engine,
                    top_k=top_k,
                )
            except Exception as llm_err:
                # ARCHITECTURE.md line 328: Fallback to template-based recommendation on LLM error
                logger.warning("LLM provider failed (%s). Falling back to Template provider.", llm_err)
                fallback_gen = RecommendationGenerator(provider=TemplateFallbackProvider())
                raw_response = fallback_gen.recommend_from_query(
                    query=query_payload,
                    recommendation_engine=engine,
                    top_k=top_k,
                )

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # 4. Standardize via Phase 7 Output Layer
            formatted = ResponseFormatter.from_phase5_response(
                phase5_resp=raw_response,
                execution_time_ms=elapsed_ms,
                provider_name=getattr(raw_response, "provider_used", generator.provider_name),
            )

            # 5. Emit response
            resp_bytes = ResponseFormatter.to_json(formatted).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.send_header("Cache-Control", "no-store")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(resp_bytes)

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("Unhandled serverless execution error: %s", e, exc_info=True)
            self._send_json_error(
                500,
                "SERVERLESS_EXECUTION_ERROR",
                f"An internal error occurred: {str(e)}",
                execution_time_ms=elapsed_ms,
            )

    def _send_json_error(self, status_code: int, code: str, msg: str, execution_time_ms: int = 0):
        err_obj = ResponseFormatter.format_error(
            error_code=code,
            message=msg,
            execution_time_ms=execution_time_ms,
        )
        resp_bytes = err_obj.model_dump_json().encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp_bytes)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(resp_bytes)
