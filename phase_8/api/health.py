"""
Vercel Serverless Function: GET /api/health
Monitors system health, catalog availability, and deployment telemetry.
"""
from http.server import BaseHTTPRequestHandler
import json
import sys
from pathlib import Path

# Bootstrap project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_8.config import get_deployment_config


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Health Function."""

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        config = get_deployment_config()
        clean_parquet = PROJECT_ROOT / "phase_2" / "data" / "processed" / "zomato_clean.parquet"

        catalog_present = clean_parquet.is_file()
        catalog_records = 12494 if catalog_present else 0

        payload = {
            "status": "healthy",
            "service": "GourmetAI-Serverless-Engine",
            "environment": config.vercel_env,
            "version": "1.0.0",
            "catalog": {
                "source": config.data_source,
                "records": catalog_records,
                "available": catalog_present,
            },
            "llm": {
                "provider": "google-gemini" if config.has_gemini_credentials else "mock-fallback",
                "model": config.gemini_model,
                "has_credentials": config.has_gemini_credentials,
            },
            "serverless_timeout_seconds": config.timeout_seconds,
        }

        resp_bytes = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(resp_bytes)
