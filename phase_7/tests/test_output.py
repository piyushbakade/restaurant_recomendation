"""
Automated Test Suite for Phase 7: Output Layer & Standardized JSON Contract.
Tests schema validation, domain integrity, formatting (JSON & Markdown), performance, and pipeline integration.
"""
import json
import pytest

from phase_7.contracts import (
    MetaContract,
    QuerySummaryContract,
    RestaurantOutputContract,
    StandardErrorResponse,
    StandardSuccessResponse,
)
from phase_7.formatter import ResponseFormatter
from phase_7.run_output import run_demo
from phase_7.service import OutputService
from phase_7.validator import ContractValidator, ValidationReport


# Exact payload from ARCHITECTURE.md line 283-310
ARCHITECTURE_MD_SAMPLE_CONTRACT = {
    "status": "success",
    "query_summary": {
        "location": "Koramangala",
        "cuisines": ["Italian"],
        "max_budget": 1000,
        "min_rating": 4.0,
    },
    "total_candidates_found": 18,
    "recommendations": [
        {
            "restaurant_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
            "name": "Toscano",
            "location": "Koramangala 5th Block",
            "cuisines": ["Italian", "Pizza", "Desserts"],
            "price_for_two": 900,
            "rating": 4.4,
            "votes": 1280,
            "popular_dishes": ["Ravioli", "Bruschetta", "Tiramisu"],
            "recommendation_reason": "Toscano perfectly matches your ₹1,000 budget while exceeding your 4.0 rating target with a 4.4 rating. Situated right in Koramangala 5th Block, it is celebrated for authentic wood-fired pizzas and homemade ravioli, making it an ideal Italian dining choice.",
        }
    ],
    "meta": {
        "execution_time_ms": 745,
    },
}


def test_architecture_contract_exact_compliance():
    """Verify that ARCHITECTURE.md JSON contract satisfies Phase 7 Pydantic schemas and validator with 0 errors."""
    report = ContractValidator.validate_success_response(ARCHITECTURE_MD_SAMPLE_CONTRACT)
    assert report.is_valid, f"Validation failed: {report.errors}"
    assert len(report.errors) == 0

    model = StandardSuccessResponse.model_validate(ARCHITECTURE_MD_SAMPLE_CONTRACT)
    assert model.status == "success"
    assert model.query_summary.location == "Koramangala"
    assert model.query_summary.cuisines == ["Italian"]
    assert model.query_summary.max_budget == 1000
    assert model.query_summary.min_rating == 4.0
    assert model.total_candidates_found == 18
    assert len(model.recommendations) == 1
    assert model.recommendations[0].name == "Toscano"
    assert model.recommendations[0].price_for_two == 900
    assert model.recommendations[0].rating == 4.4
    assert model.meta.execution_time_ms == 745


def test_validator_detects_duplicate_restaurant_ids():
    """Ensures duplicate restaurant IDs in the recommendations array are caught."""
    bad_data = {
        "status": "success",
        "query_summary": {"location": "Indiranagar", "cuisines": ["Cafe"], "max_budget": 500, "min_rating": 3.5},
        "total_candidates_found": 5,
        "recommendations": [
            {
                "restaurant_id": "duplicate-uuid-1234",
                "name": "Cafe Coffee Day",
                "location": "Indiranagar 100ft Rd",
                "cuisines": ["Cafe"],
                "price_for_two": 400,
                "rating": 3.8,
                "votes": 50,
                "popular_dishes": ["Cappuccino"],
                "recommendation_reason": "Great cozy spot for affordable hot coffee in Indiranagar.",
            },
            {
                "restaurant_id": "duplicate-uuid-1234",  # Duplicate ID
                "name": "Another Branch",
                "location": "Indiranagar 12th Main",
                "cuisines": ["Cafe"],
                "price_for_two": 400,
                "rating": 3.8,
                "votes": 50,
                "popular_dishes": ["Cappuccino"],
                "recommendation_reason": "Great cozy spot for affordable hot coffee in Indiranagar.",
            },
        ],
        "meta": {"execution_time_ms": 120},
    }
    report = ContractValidator.validate_success_response(bad_data)
    assert not report.is_valid
    assert any("Duplicate restaurant_id" in err for err in report.errors)


def test_validator_detects_placeholder_artifacts():
    """Ensures LLM or template placeholder artifacts (e.g. {{reason}}, [TODO]) fail validation."""
    placeholder_data = {
        "status": "success",
        "query_summary": {"location": "Whitefield", "cuisines": [], "max_budget": 1000, "min_rating": 3.0},
        "total_candidates_found": 1,
        "recommendations": [
            {
                "restaurant_id": "uuid-wh-01",
                "name": "Sample Bistro",
                "location": "Whitefield Main Road",
                "cuisines": ["Continental"],
                "price_for_two": 600,
                "rating": 4.0,
                "votes": 100,
                "popular_dishes": ["Pasta"],
                "recommendation_reason": "This is a placeholder reason {{reason}} for testing.",
            }
        ],
        "meta": {"execution_time_ms": 50},
    }
    report = ContractValidator.validate_success_response(placeholder_data)
    assert not report.is_valid
    assert any("placeholder artifact" in err for err in report.errors)


def test_validator_detects_out_of_bounds_metrics():
    """Ensures rating > 5.0 and negative price or negative latency are caught."""
    invalid_metrics_data = {
        "status": "success",
        "query_summary": {"location": "Koramangala", "cuisines": [], "max_budget": 1000, "min_rating": 3.0},
        "total_candidates_found": 1,
        "recommendations": [
            {
                "restaurant_id": "uuid-km-99",
                "name": "Crazy Place",
                "location": "Koramangala",
                "cuisines": ["Fast Food"],
                "price_for_two": -50,  # Negative price
                "rating": 6.8,  # > 5.0 rating
                "votes": 10,
                "popular_dishes": [],
                "recommendation_reason": "A fun place with impossible ratings and negative prices.",
            }
        ],
        "meta": {"execution_time_ms": -10},  # Negative latency
    }
    report = ContractValidator.validate_success_response(invalid_metrics_data)
    assert not report.is_valid
    assert any("price_for_two" in err or "rating" in err or "execution_time_ms" in err for err in report.errors)


def test_content_sanitizer():
    """Verifies that malicious HTML entities and control chars are safely encoded."""
    dirty_text = "<script>alert('xss')</script> Delicious \u200B\x00pizza & pasta!   "
    clean = ContractValidator.sanitize_text(dirty_text)
    assert "<script>" not in clean
    assert "&lt;script&gt;" in clean
    assert "\u200B" not in clean
    assert "\x00" not in clean
    assert "Delicious" in clean


def test_response_formatter_json_serialization():
    """Tests JSON and Pretty JSON serialization idempotency."""
    resp = StandardSuccessResponse.model_validate(ARCHITECTURE_MD_SAMPLE_CONTRACT)
    json_str = ResponseFormatter.to_json(resp)
    pretty_json_str = ResponseFormatter.to_pretty_json(resp)

    assert isinstance(json_str, str)
    assert isinstance(pretty_json_str, str)
    assert "\n" in pretty_json_str

    parsed = json.loads(json_str)
    assert parsed["status"] == "success"
    assert parsed["recommendations"][0]["name"] == "Toscano"


def test_response_formatter_markdown_output():
    """Verifies that the markdown formatter produces structured GitHub-flavored Markdown."""
    resp = StandardSuccessResponse.model_validate(ARCHITECTURE_MD_SAMPLE_CONTRACT)
    md = ResponseFormatter.to_markdown(resp)

    assert "# 🍽️ GourmetAI Recommendation Report - Koramangala" in md
    assert "**Max Budget for Two**: ₹1,000" in md
    assert "Toscano" in md
    assert "★ 4.4" in md
    assert "Ravioli" in md


def test_standard_error_response_conformance():
    """Verifies error responses format correctly and pass validator."""
    err = ResponseFormatter.format_error(
        error_code="LOCATION_NOT_FOUND",
        message="Could not resolve location 'Atlantis' in Bangalore.",
        details={"attempted_locality": "Atlantis"},
        execution_time_ms=15,
    )
    err_dict = err.model_dump()
    report = ContractValidator.validate_error_response(err_dict)

    assert report.is_valid, f"Error validation failed: {report.errors}"
    assert err.status == "error"
    assert err.error_code == "LOCATION_NOT_FOUND"
    assert err.meta.execution_time_ms == 15


def test_output_service_pipeline_end_to_end():
    """Integrates OutputService with Phase 4 retrieval + Phase 5 generation and validates result."""
    service = OutputService()
    response = service.generate_recommendations(
        location="Koramangala",
        cuisines=["Italian", "Pizza"],
        max_budget=1200,
        min_rating=4.0,
        vibe_or_notes="cozy romantic candle-light dinner",
        top_k=3,
        provider_override="mock",
    )

    assert response.status == "success"
    assert response.query_summary.location.lower() == "koramangala"
    assert response.total_candidates_found > 0
    assert 1 <= len(response.recommendations) <= 3
    assert response.meta.execution_time_ms >= 0

    # Strict contract validation
    report = ContractValidator.validate_success_response(response.model_dump())
    assert report.is_valid, f"Pipeline output contract validation failed: {report.errors}"


def test_output_service_relaxed_search_flag():
    """Verifies contract serialization when query requires filter relaxation."""
    service = OutputService()
    # Extremely restrictive search to trigger relaxation
    response = service.generate_recommendations(
        location="Frazer Town",
        cuisines=["Mexican"],
        max_budget=200,
        min_rating=4.8,
        top_k=2,
        provider_override="template",
    )

    assert response.status == "success"
    assert response.total_candidates_found >= 0
    report = ContractValidator.validate_success_response(response.model_dump())
    assert report.is_valid


def test_etag_determinism():
    """Verifies ETag is deterministic across identical recommendations."""
    resp1 = StandardSuccessResponse.model_validate(ARCHITECTURE_MD_SAMPLE_CONTRACT)
    resp2 = StandardSuccessResponse.model_validate(ARCHITECTURE_MD_SAMPLE_CONTRACT)

    etag1 = OutputService.compute_etag(resp1)
    etag2 = OutputService.compute_etag(resp2)
    assert etag1 == etag2
    assert etag1.startswith('W/"')


def test_serialization_speed_performance():
    """Ensures high-throughput serialization completes in sub-5ms."""
    import time
    service = OutputService()
    response = service.generate_recommendations(
        location="Indiranagar",
        cuisines=["Cafe"],
        max_budget=800,
        min_rating=3.5,
        top_k=5,
        provider_override="mock",
    )

    t0 = time.perf_counter()
    for _ in range(50):
        _ = ResponseFormatter.to_json(response)
    avg_ms = ((time.perf_counter() - t0) / 50) * 1000

    assert avg_ms < 5.0, f"Serialization took too long: {avg_ms:.2f} ms"


def test_cli_demo_runner():
    """Verifies that the manual CLI demo runs cleanly without raising exceptions."""
    try:
        run_demo()
    except Exception as e:
        pytest.fail(f"run_demo() raised an unexpected exception: {e}")
