"""
Output Service for Phase 7.
Coordinates pipeline execution, validation, caching headers, and standardized output generation.
"""
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

from phase_3.models import UserPreferenceInput
from phase_3.normalizer import PreferenceNormalizer
from phase_4.engine import RecommendationEngine
from phase_5.generator import (
    DeterministicMockProvider,
    GeminiProvider,
    RecommendationGenerator,
    TemplateFallbackProvider,
)
from phase_7.contracts import (
    StandardErrorResponse,
    StandardSuccessResponse,
)
from phase_7.formatter import ResponseFormatter
from phase_7.validator import ContractValidator, ValidationReport

logger = logging.getLogger(__name__)


class OutputService:
    """
    High-level orchestrator for the Phase 7 Output Layer.
    Connects candidate retrieval and recommendation generation to standardized contract outputs.
    """

    def __init__(
        self,
        engine: Optional[RecommendationEngine] = None,
        generator: Optional[RecommendationGenerator] = None,
    ):
        self.engine = engine or RecommendationEngine()
        self.generator = generator or RecommendationGenerator(provider=DeterministicMockProvider())
        self.normalizer = PreferenceNormalizer()

    def generate_recommendations(
        self,
        location: str,
        cuisines: Optional[Union[List[str], str]] = None,
        max_budget: Optional[Union[int, str]] = 1000,
        min_rating: Optional[float] = 3.8,
        vibe_or_notes: Optional[str] = None,
        top_k: int = 5,
        online_order_only: bool = False,
        book_table_only: bool = False,
        provider_override: Optional[str] = None,
    ) -> StandardSuccessResponse:
        """
        Runs the end-to-end recommendation pipeline and outputs a verified Phase 7 contract response.
        """
        start_time = time.perf_counter()

        # 1. Normalize preferences
        user_input = UserPreferenceInput(
            location=location,
            cuisines=cuisines if isinstance(cuisines, list) else ([cuisines] if cuisines else []),
            max_budget=max_budget,
            min_rating=min_rating,
            vibe_or_notes=vibe_or_notes,
            online_order_only=online_order_only,
            book_table_only=book_table_only,
        )
        pref = self.normalizer.normalize(user_input)

        # 2. Determine active generator
        if provider_override == "gemini":
            active_gen = RecommendationGenerator(provider=GeminiProvider())
        elif provider_override == "template":
            active_gen = RecommendationGenerator(provider=TemplateFallbackProvider())
        elif provider_override == "mock":
            active_gen = RecommendationGenerator(provider=DeterministicMockProvider())
        else:
            active_gen = self.generator

        # 3. Generate recommendations via Phase 5
        phase5_resp = active_gen.recommend_from_query(
            query=user_input,
            recommendation_engine=self.engine,
            top_k=top_k,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 5. Format to Phase 7 Standard Contract
        provider_name = active_gen.provider.__class__.__name__
        formatted_response = ResponseFormatter.from_phase5_response(
            phase5_resp=phase5_resp,
            execution_time_ms=elapsed_ms,
            provider_name=provider_name,
        )

        # 6. Validate contract conformance
        validation: ValidationReport = ContractValidator.validate_success_response(
            formatted_response.model_dump()
        )
        if not validation.is_valid:
            logger.warning("Phase 7 contract validation warnings/errors: %s", validation.errors)

        return formatted_response

    @classmethod
    def compute_etag(cls, response: Union[StandardSuccessResponse, StandardErrorResponse, Dict[str, Any]]) -> str:
        """
        Computes a deterministic MD5 hash for HTTP ETag headers (useful for client/serverless caching).
        """
        if hasattr(response, "model_dump"):
            data = response.model_dump()
        else:
            data = dict(response)

        # Exclude dynamic timestamp from hash computation to enable proper caching
        data_copy = {k: v for k, v in data.items() if k != "meta"}
        raw_bytes = json.dumps(data_copy, sort_keys=True).encode("utf-8")
        return f'W/"{hashlib.md5(raw_bytes).hexdigest()}"'
