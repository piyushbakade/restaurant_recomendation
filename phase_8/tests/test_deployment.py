"""
Automated Test Suite for Phase 8: Vercel Serverless Deployment & Configuration.
Tests manifests, environment configurations, serverless handlers, fallback resilience, and database schema generation.
"""
import io
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from phase_8.api.health import handler as HealthHandler
from phase_8.api.metadata import handler as MetadataHandler
from phase_8.api.recommendations import handler as RecommendationsHandler
from phase_8.config import DeploymentConfig, get_deployment_config
from phase_8.db_migration import export_sql_file, generate_ddl_sql


class MockServerlessRequest:
    """Helper mock simulating BaseHTTPRequestHandler socket stream for tests."""

    def __init__(self, method: str, path: str, body: bytes = b"", headers: dict = None):
        headers = headers or {}
        if body and "Content-Length" not in headers:
            headers["Content-Length"] = str(len(body))

        req_lines = [f"{method} {path} HTTP/1.1", "Host: localhost"]
        for k, v in headers.items():
            req_lines.append(f"{k}: {v}")
        req_lines.append("")
        req_lines.append("")
        req_data = "\r\n".join(req_lines).encode("utf-8") + body

        self.r = io.BytesIO(req_data)
        self.w = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "r" in mode:
            return self.r
        return self.w

    def sendall(self, b):
        self.w.write(b)

    def settimeout(self, t):
        pass

    def setsockopt(self, *args):
        pass

    @property
    def status_code(self) -> int:
        raw = self.w.getvalue().decode("utf-8", errors="ignore")
        if not raw:
            return 0
        first_line = raw.split("\r\n")[0]
        parts = first_line.split()
        return int(parts[1]) if len(parts) > 1 else 0

    @property
    def response_headers(self) -> dict:
        raw = self.w.getvalue().decode("utf-8", errors="ignore")
        headers = {}
        if "\r\n\r\n" in raw:
            head_part = raw.split("\r\n\r\n", 1)[0]
            lines = head_part.split("\r\n")[1:]
            for l in lines:
                if ":" in l:
                    k, v = l.split(":", 1)
                    headers[k.strip()] = v.strip()
        return headers

    def get_response_json(self) -> dict:
        raw = self.w.getvalue().decode("utf-8", errors="ignore")
        if "\r\n\r\n" in raw:
            body_part = raw.split("\r\n\r\n", 1)[1]
            return json.loads(body_part) if body_part else {}
        return {}


def test_vercel_json_manifest_conformance():
    """Validates that vercel.json exists, contains valid schema, routes, and security headers."""
    phase8_manifest = Path("phase_8/vercel.json")
    root_manifest = Path("vercel.json")

    assert phase8_manifest.is_file(), "phase_8/vercel.json must exist"
    assert root_manifest.is_file(), "root vercel.json must exist"

    manifest = json.loads(phase8_manifest.read_text(encoding="utf-8"))
    assert manifest.get("version") == 2

    # Check routes
    route_dests = [r.get("dest") for r in manifest.get("routes", [])]
    assert "/phase_8/api/recommendations.py" in route_dests
    assert "/phase_8/api/health.py" in route_dests
    assert "/phase_8/api/metadata.py" in route_dests
    assert "/phase_6/templates/index.html" in route_dests

    # Check security headers
    headers = manifest.get("headers", [{}])[0].get("headers", [])
    header_keys = [h["key"] for h in headers]
    assert "X-Content-Type-Options" in header_keys
    assert "X-Frame-Options" in header_keys
    assert "Referrer-Policy" in header_keys
    assert "Access-Control-Allow-Origin" in header_keys


def test_env_example_templates_exist_and_complete():
    """Verifies that .env.example files are present in root and phase_8/ with critical keys."""
    root_env = Path(".env.example")
    phase8_env = Path("phase_8/.env.example")

    assert root_env.is_file(), ".env.example must exist in root"
    assert phase8_env.is_file(), ".env.example must exist in phase_8/"

    content = root_env.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY" in content
    assert "DATABASE_URL" in content
    assert "SERVERLESS_TIMEOUT_SECONDS" in content
    assert "RESTAURANT_DATA_SOURCE" in content


def test_config_loader_defaults_and_validation():
    """Tests environment variable loading and validation logic in DeploymentConfig."""
    config = DeploymentConfig()
    assert config.timeout_seconds == 15
    assert "flash" in config.gemini_model
    assert config.data_source in ("local_parquet", "cloud_postgres")

    val = config.validate()
    assert "status" in val
    assert "config_summary" in val
    assert isinstance(val["warnings"], list)


def test_serverless_recommendations_handler_post_success():
    """Simulates a valid POST /api/recommendations execution through the serverless function."""
    payload = json.dumps({
        "location": "Koramangala",
        "cuisines": ["Italian"],
        "max_budget": 1000,
        "min_rating": 4.0,
        "top_k": 3,
        "provider": "mock",
    }).encode("utf-8")

    req = MockServerlessRequest("POST", "/api/recommendations", body=payload)
    RecommendationsHandler(req, ("127.0.0.1", 80), None)

    assert req.status_code == 200
    assert req.response_headers.get("Content-Type") == "application/json; charset=utf-8"

    resp = req.get_response_json()
    assert resp["status"] == "success"
    assert resp["query_summary"]["location"] == "Koramangala"
    assert resp["total_candidates_found"] > 0
    assert len(resp["recommendations"]) <= 3
    assert resp["meta"]["execution_time_ms"] >= 0


def test_serverless_recommendations_handler_missing_location():
    """Ensures 400 Bad Request when location is blank."""
    payload = json.dumps({
        "location": "   ",
        "max_budget": 1000,
    }).encode("utf-8")

    req = MockServerlessRequest("POST", "/api/recommendations", body=payload)
    RecommendationsHandler(req, ("127.0.0.1", 80), None)

    assert req.status_code == 400
    resp = req.get_response_json()
    assert resp["status"] == "error"
    assert resp["error_code"] == "MISSING_LOCATION"


def test_serverless_recommendations_handler_options_cors():
    """Verifies OPTIONS pre-flight request returns 204 with CORS headers."""
    req = MockServerlessRequest("OPTIONS", "/api/recommendations")
    RecommendationsHandler(req, ("127.0.0.1", 80), None)

    assert req.status_code == 204
    assert req.response_headers.get("Access-Control-Allow-Origin") == "*"
    assert "POST" in req.response_headers.get("Access-Control-Allow-Methods", "")


def test_serverless_health_handler():
    """Verifies GET /api/health serverless endpoint."""
    req = MockServerlessRequest("GET", "/api/health")
    HealthHandler(req, ("127.0.0.1", 80), None)

    assert req.status_code == 200
    resp = req.get_response_json()
    assert resp["status"] == "healthy"
    assert resp["service"] == "GourmetAI-Serverless-Engine"
    assert resp["catalog"]["available"] is True


def test_serverless_metadata_handler():
    """Verifies GET /api/metadata serverless endpoint."""
    req = MockServerlessRequest("GET", "/api/metadata")
    MetadataHandler(req, ("127.0.0.1", 80), None)

    assert req.status_code == 200
    resp = req.get_response_json()
    assert "popular_locations" in resp
    assert "popular_cuisines" in resp
    assert resp["default_budget"] == 1000


def test_llm_error_fallback_resilience():
    """
    Tests ARCHITECTURE.md line 328:
    'If the LLM provider returns an error, the API falls back to generating
     a template-based recommendation from the top-ranked candidate's database attributes.'
    """
    payload = json.dumps({
        "location": "Indiranagar",
        "cuisines": ["Cafe"],
        "max_budget": 800,
        "min_rating": 3.5,
        "top_k": 2,
    }).encode("utf-8")

    # Mock GeminiProvider.generate to raise a network/API exception
    with patch("phase_5.generator.GeminiProvider.generate", side_effect=RuntimeError("Simulated LLM API Timeout")):
        req = MockServerlessRequest("POST", "/api/recommendations", body=payload)
        RecommendationsHandler(req, ("127.0.0.1", 80), None)

        assert req.status_code == 200
        resp = req.get_response_json()
        assert resp["status"] == "success"
        assert len(resp["recommendations"]) > 0
        assert resp["meta"]["provider"] in ("TemplateFallbackProvider", "DeterministicMockProvider")


def test_database_migration_schema_ddl():
    """Validates the generated PostgreSQL DDL for Neon / Supabase."""
    ddl = generate_ddl_sql()
    assert "CREATE TABLE IF NOT EXISTS restaurants" in ddl
    assert "restaurant_id VARCHAR(64) PRIMARY KEY" in ddl
    assert "CREATE INDEX IF NOT EXISTS idx_restaurants_cuisines ON restaurants USING GIN (cuisines);" in ddl
    assert "CREATE INDEX IF NOT EXISTS idx_restaurants_name_trgm ON restaurants USING GIN" in ddl

    sql_file = export_sql_file()
    assert sql_file.is_file()
    assert sql_file.stat().st_size > 500
