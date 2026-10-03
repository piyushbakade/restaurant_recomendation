"""
Automated Test Suite for Phase 6: Interactive Web UI & API Layer.

Covers:
- Request validation schemas (valid data, empty location, out-of-range rating)
- Health check and metadata endpoint handlers
- Recommendations endpoint handler (Phase 3 -> 4 -> 5 integration)
- Live HTTP server execution:
  - GET / (Serves index.html with correct SEO and form elements)
  - GET /static/css/style.css (Serves glassmorphic stylesheets)
  - GET /static/js/app.js (Serves client-side reactive logic)
  - GET /api/health (JSON health status)
  - GET /api/metadata (Preset locations and cuisines)
  - POST /api/recommendations (End-to-end JSON response contract)
  - Error responses (400 empty body, 422 validation, 404 not found)
  - CORS header handling
"""
import threading
import time
from typing import Generator
import pytest
import requests
from pydantic import ValidationError

from phase_4.config import CLEAN_DATA_FILE
from phase_6.api import (
    RecommendationRequest,
    handle_health_endpoint,
    handle_metadata_endpoint,
    handle_recommendations_endpoint,
)
from phase_6.server import ThreadedHTTPServer, create_server


# -------------------------------------------------------------------------
# 1. Pydantic Request Validation Tests
# -------------------------------------------------------------------------

def test_recommendation_request_validation_valid():
    """Verify valid request model parsing."""
    req = RecommendationRequest(
        location="Koramangala",
        cuisines=["Italian", "Pizza"],
        max_budget=1000,
        min_rating=4.2,
        vibe_or_notes="romantic date",
        top_k=3,
    )
    assert req.location == "Koramangala"
    assert req.max_budget == 1000
    assert req.min_rating == 4.2
    assert req.top_k == 3


def test_recommendation_request_blank_location():
    """Verify blank or whitespace location is rejected."""
    with pytest.raises(ValidationError):
        RecommendationRequest(location="   ")


def test_recommendation_request_invalid_rating():
    """Verify out-of-range rating (> 5.0 or < 1.0) is rejected."""
    with pytest.raises(ValidationError):
        RecommendationRequest(location="Koramangala", min_rating=5.5)

    with pytest.raises(ValidationError):
        RecommendationRequest(location="Koramangala", min_rating=0.5)


# -------------------------------------------------------------------------
# 2. Endpoint Handler Unit Tests
# -------------------------------------------------------------------------

def test_api_health_endpoint():
    """Verify health check endpoint returns expected structure."""
    res = handle_health_endpoint()
    assert res["status"] == "healthy"
    assert "catalog_size" in res
    assert "endpoints" in res
    assert len(res["endpoints"]) >= 3


def test_api_metadata_endpoint():
    """Verify metadata endpoint returns presets for UI."""
    res = handle_metadata_endpoint()
    assert "popular_locations" in res
    assert "popular_cuisines" in res
    assert "Koramangala" in res["popular_locations"]
    assert any(c["name"] == "Italian" for c in res["popular_cuisines"])


@pytest.mark.skipif(not CLEAN_DATA_FILE.exists(), reason="Requires Phase 2 clean dataset")
def test_api_recommendations_endpoint_handler():
    """Verify recommendations endpoint returns standardized ARCHITECTURE.md JSON contract."""
    payload = {
        "location": "Koramangala",
        "cuisines": ["Italian"],
        "max_budget": 1000,
        "min_rating": 4.0,
        "vibe_or_notes": "romantic dinner",
        "top_k": 3,
    }
    res = handle_recommendations_endpoint(payload)

    assert res["status"] == "success"
    assert "query_summary" in res
    assert "total_candidates_found" in res
    assert "recommendations" in res
    assert len(res["recommendations"]) == 3

    top_rec = res["recommendations"][0]
    assert "restaurant_id" in top_rec
    assert "name" in top_rec
    assert "price_for_two" in top_rec
    assert "rating" in top_rec
    assert "recommendation_reason" in top_rec
    assert top_rec["match_rank"] == 1


# -------------------------------------------------------------------------
# 3. Live HTTP Server Integration Tests
# -------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_server() -> Generator[str, None, None]:
    """Spins up an ephemeral HTTP server on port 0 (OS allocated free port) for integration tests."""
    server: ThreadedHTTPServer = create_server(host="127.0.0.1", port=0)
    assigned_port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)  # Allow server to bind and start listening

    base_url = f"http://127.0.0.1:{assigned_port}"
    yield base_url

    server.shutdown()
    server.server_close()


def test_http_get_index_html(live_server):
    """Verify root / delivers HTML template with all necessary frontend components."""
    resp = requests.get(f"{live_server}/", timeout=5)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["Content-Type"]
    html = resp.text

    assert "GourmetAI" in html
    assert "recommendation-form" in html
    assert "location-input" in html
    assert "budget-slider" in html
    assert "cuisine-grid" in html
    assert "submit-btn" in html


def test_http_get_static_css(live_server):
    """Verify static CSS delivery with proper MIME type and glassmorphism definitions."""
    resp = requests.get(f"{live_server}/static/css/style.css", timeout=5)
    assert resp.status_code == 200
    assert "text/css" in resp.headers["Content-Type"]
    css = resp.text
    assert "--bg-dark" in css
    assert "glass-card" in css


def test_http_get_static_js(live_server):
    """Verify static JavaScript delivery with proper MIME type."""
    resp = requests.get(f"{live_server}/static/js/app.js", timeout=5)
    assert resp.status_code == 200
    assert "javascript" in resp.headers["Content-Type"]
    js = resp.text
    assert "DOMContentLoaded" in js
    assert "executeSearch" in js


def test_http_get_api_health(live_server):
    """Verify GET /api/health over live HTTP."""
    resp = requests.get(f"{live_server}/api/health", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "catalog_size" in data


def test_http_get_api_metadata(live_server):
    """Verify GET /api/metadata over live HTTP."""
    resp = requests.get(f"{live_server}/api/metadata", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert "popular_locations" in data
    assert "popular_cuisines" in data


@pytest.mark.skipif(not CLEAN_DATA_FILE.exists(), reason="Requires Phase 2 clean dataset")
def test_http_post_recommendations_success(live_server):
    """Verify POST /api/recommendations executes end-to-end over live HTTP."""
    payload = {
        "location": "Indiranagar",
        "cuisines": ["Continental"],
        "max_budget": 1500,
        "min_rating": 4.0,
        "vibe_or_notes": "rooftop dinner with cocktails",
        "top_k": 3,
    }
    resp = requests.post(f"{live_server}/api/recommendations", json=payload, timeout=10)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["query_summary"]["location"] == "Indiranagar"
    assert len(data["recommendations"]) == 3
    assert data["recommendations"][0]["match_rank"] == 1
    assert "Access-Control-Allow-Origin" in resp.headers


def test_http_post_recommendations_validation_error(live_server):
    """Verify POST /api/recommendations with invalid payload returns 422."""
    payload = {
        "location": "",  # Empty location triggers validation failure
        "min_rating": 9.9,  # Out of range rating
    }
    resp = requests.post(f"{live_server}/api/recommendations", json=payload, timeout=5)
    assert resp.status_code == 422
    data = resp.json()
    assert "Validation error" in data["detail"]


def test_http_cors_options(live_server):
    """Verify OPTIONS pre-flight request handles CORS properly."""
    resp = requests.options(f"{live_server}/api/recommendations", timeout=5)
    assert resp.status_code == 204
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"
    assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")


def test_http_not_found(live_server):
    """Verify unknown path returns 404."""
    resp = requests.get(f"{live_server}/unknown/endpoint", timeout=5)
    assert resp.status_code == 404
