"""
Automated Test Suite for Phase 5: LLM Recommendation & Anti-Hallucination Guardrails.

Covers:
- Prompt engineering with <verified_restaurants> XML context enclosure
- Closed-world constraint and anti-hallucination guardrail validation
- Detection and rejection of hallucinated restaurants
- Deterministic mock provider and personalization from dining intent / vibe
- Template fallback synthesizer for zero-downtime resilience
- End-to-end integration: Phase 3 (Preferences) -> Phase 4 (Engine) -> Phase 5 (LLM Curation)
- Strict adherence to ARCHITECTURE.md JSON output contract
"""
from typing import List
from unittest.mock import MagicMock, patch
import pytest

from phase_3.models import BudgetTier, NormalizedPreference
from phase_4.config import CLEAN_DATA_FILE
from phase_4.engine import RecommendationEngine
from phase_4.models import CandidateRestaurant, ScoreBreakdown, ScoredRestaurant
from phase_5.generator import (
    DeterministicMockProvider,
    GeminiProvider,
    RecommendationGenerator,
    TemplateFallbackProvider,
)
from phase_5.guardrails import AntiHallucinationGuardrail
from phase_5.models import (
    FinalCuratedRestaurant,
    LLMRecommendationItem,
    LLMStructuredOutput,
    Phase5Response,
)
from phase_5.prompt import SYSTEM_INSTRUCTION, build_user_prompt


@pytest.fixture
def sample_preference() -> NormalizedPreference:
    return NormalizedPreference(
        raw_location="koramangala",
        resolved_location="Koramangala 5th Block",
        resolved_cluster="Koramangala",
        location_match_confidence=0.95,
        cuisines=["Italian", "Pizza"],
        max_budget=1000,
        budget_tier=BudgetTier.MID_RANGE,
        min_rating=4.0,
        vibe_or_notes="cozy romantic candle-light dinner",
    )


@pytest.fixture
def sample_candidates() -> List[ScoredRestaurant]:
    c1 = CandidateRestaurant(
        restaurant_id="11111111-1111-1111-1111-111111111111",
        name="Toscano",
        address="Koramangala 5th Block",
        location="Koramangala 5th Block",
        location_cluster="Koramangala",
        cuisines=["Italian", "Pizza"],
        cost_for_two=900,
        rate=4.4,
        votes=2500,
        dish_liked=["Ravioli", "Tiramisu", "Wood Fired Pizza"],
        sample_reviews=["Wonderful Italian food and romantic vibes."],
    )
    c2 = CandidateRestaurant(
        restaurant_id="22222222-2222-2222-2222-222222222222",
        name="Little Italy",
        address="Koramangala 1st Block",
        location="Koramangala 1st Block",
        location_cluster="Koramangala",
        cuisines=["Italian", "Pizza"],
        cost_for_two=1000,
        rate=4.2,
        votes=1800,
        dish_liked=["Pasta Primavera", "Nachos"],
        sample_reviews=["Classic vegetarian Italian."],
    )
    return [
        ScoredRestaurant(
            restaurant=c1,
            scores=ScoreBreakdown(
                cuisine_score=1.0,
                rating_score=0.88,
                price_score=0.9,
                popularity_score=0.8,
                final_score=0.91,
            ),
            rank=1,
        ),
        ScoredRestaurant(
            restaurant=c2,
            scores=ScoreBreakdown(
                cuisine_score=1.0,
                rating_score=0.84,
                price_score=1.0,
                popularity_score=0.75,
                final_score=0.87,
            ),
            rank=2,
        ),
    ]


# -------------------------------------------------------------------------
# 1. Prompt Engineering & XML Enclosure Tests
# -------------------------------------------------------------------------

def test_system_instruction_closed_world():
    """Verify system prompt enforces closed-world constraint and anti-hallucination rules."""
    assert "CLOSED-WORLD RULE" in SYSTEM_INSTRUCTION
    assert "Never invent" in SYSTEM_INSTRUCTION
    assert "ATTRIBUTE INTEGRITY" in SYSTEM_INSTRUCTION
    assert "FACT-GROUNDED REASONING" in SYSTEM_INSTRUCTION


def test_build_user_prompt_structure(sample_preference, sample_candidates):
    """Verify prompt wraps candidates in <verified_restaurants> XML tags."""
    prompt = build_user_prompt(sample_preference, sample_candidates)

    assert "<verified_restaurants>" in prompt
    assert "</verified_restaurants>" in prompt
    assert "Koramangala 5th Block" in prompt
    assert "Italian" in prompt
    assert "Rs. 1,000" in prompt
    assert "Toscano" in prompt
    assert "11111111-1111-1111-1111-111111111111" in prompt
    assert "cozy romantic candle-light dinner" in prompt


# -------------------------------------------------------------------------
# 2. Anti-Hallucination Guardrail Tests
# -------------------------------------------------------------------------

def test_guardrail_valid_recommendations(sample_preference, sample_candidates):
    """Verify legitimate candidate recommendations pass through the guardrail."""
    llm_output = LLMStructuredOutput(
        recommendations=[
            LLMRecommendationItem(
                restaurant_id="11111111-1111-1111-1111-111111111111",
                name="Toscano",
                recommendation_reason="Toscano is ideal for your romantic dinner with fresh Ravioli and authentic pizza.",
                highlighted_dishes=["Ravioli", "Tiramisu"],
                match_highlights=["Rs. 900 for two", "4.4 rating"],
            )
        ]
    )

    curated = AntiHallucinationGuardrail.validate_and_merge(
        llm_output, sample_candidates, sample_preference
    )

    # 1 verified match from LLM, 1 backfilled from candidate list
    assert len(curated) == 2
    assert curated[0].restaurant_id == "11111111-1111-1111-1111-111111111111"
    assert curated[0].name == "Toscano"
    assert "Ravioli" in curated[0].popular_dishes
    assert curated[0].match_rank == 1


def test_guardrail_rejects_hallucinated_restaurant(sample_preference, sample_candidates):
    """Verify fabricated restaurant ID and name are rejected by the guardrail."""
    fake_output = LLMStructuredOutput(
        recommendations=[
            # Hallucinated restaurant not present in sample_candidates
            LLMRecommendationItem(
                restaurant_id="99999999-9999-9999-9999-999999999999",
                name="Invented Trattoria Non-Existent",
                recommendation_reason="Invented bistro with fantastic pasta.",
                highlighted_dishes=["Fake Pasta"],
                match_highlights=["Budget friendly"],
            ),
            # Legitimate candidate
            LLMRecommendationItem(
                restaurant_id="11111111-1111-1111-1111-111111111111",
                name="Toscano",
                recommendation_reason="Toscano is an authentic dining experience.",
                highlighted_dishes=["Ravioli"],
                match_highlights=["Rs. 900"],
            ),
        ]
    )

    curated = AntiHallucinationGuardrail.validate_and_merge(
        fake_output, sample_candidates, sample_preference
    )

    # Hallucinated restaurant must be stripped
    names = [c.name for c in curated]
    assert "Invented Trattoria Non-Existent" not in names
    # Verified restaurant must be preserved
    assert "Toscano" in names
    # Unrecommended candidate must be backfilled
    assert "Little Italy" in names


def test_guardrail_name_match_id_recovery(sample_preference, sample_candidates):
    """Verify that if LLM misspells UUID but has exact candidate name, UUID is recovered."""
    altered_output = LLMStructuredOutput(
        recommendations=[
            LLMRecommendationItem(
                restaurant_id="wrong-id-format",
                name="Toscano",
                recommendation_reason="Excellent Italian dining.",
                highlighted_dishes=["Ravioli"],
                match_highlights=["4.4 rating"],
            )
        ]
    )

    curated = AntiHallucinationGuardrail.validate_and_merge(
        altered_output, sample_candidates, sample_preference
    )

    assert curated[0].name == "Toscano"
    # Canonical UUID must be restored
    assert curated[0].restaurant_id == "11111111-1111-1111-1111-111111111111"


# -------------------------------------------------------------------------
# 3. Provider Unit Tests: Mock & Fallback Template
# -------------------------------------------------------------------------

def test_deterministic_mock_provider(sample_preference, sample_candidates):
    """Verify DeterministicMockProvider produces grounded, personalized output."""
    provider = DeterministicMockProvider()
    result = provider.generate(sample_preference, sample_candidates)

    assert isinstance(result, LLMStructuredOutput)
    assert len(result.recommendations) == 2
    assert result.recommendations[0].restaurant_id == "11111111-1111-1111-1111-111111111111"
    # Personalized reason should incorporate user's vibe
    assert "cozy romantic candle-light dinner" in result.recommendations[0].recommendation_reason.lower()
    assert result.curation_summary is not None


def test_template_fallback_provider(sample_preference, sample_candidates):
    """Verify TemplateFallbackProvider generates valid attributes from database metadata."""
    provider = TemplateFallbackProvider()
    result = provider.generate(sample_preference, sample_candidates)

    assert isinstance(result, LLMStructuredOutput)
    assert len(result.recommendations) == 2
    for item in result.recommendations:
        assert len(item.recommendation_reason) > 30
        assert "Rs." in item.recommendation_reason


# -------------------------------------------------------------------------
# 4. Error Handling & Resilience
# -------------------------------------------------------------------------

def test_gemini_provider_error_activates_fallback(sample_preference, sample_candidates):
    """Verify that if an LLM provider throws an exception, template fallback activates."""
    failing_provider = MagicMock()
    failing_provider.generate.side_effect = RuntimeError("API rate limit exceeded")

    generator = RecommendationGenerator(provider=failing_provider)
    resp = generator.generate(sample_preference, sample_candidates)

    assert resp.status == "success"
    assert resp.provider_used == "TemplateFallbackProvider"
    assert len(resp.recommendations) == 2
    assert resp.recommendations[0].name == "Toscano"


def test_generator_empty_candidate_pool(sample_preference):
    """Verify empty candidate pool returns clean response without error."""
    generator = RecommendationGenerator(use_mock=True)
    resp = generator.generate(sample_preference, candidates=[])

    assert resp.status == "success"
    assert resp.total_candidates_found == 0
    assert len(resp.recommendations) == 0


# -------------------------------------------------------------------------
# 5. Integration Tests: End-to-End Pipeline & JSON Contract
# -------------------------------------------------------------------------

@pytest.mark.skipif(not CLEAN_DATA_FILE.exists(), reason="Requires Phase 2 clean dataset")
def test_recommendation_generator_e2e_integration():
    """Verify full pipeline: query -> Phase 3 -> Phase 4 -> Phase 5."""
    generator = RecommendationGenerator(use_mock=True)

    query = {
        "location": "koramangala",
        "cuisines": "Italian, Pizza",
        "max_budget": 1000,
        "min_rating": 4.0,
        "vibe_or_notes": "romantic anniversary dinner",
    }

    engine = RecommendationEngine(data_path=CLEAN_DATA_FILE)
    response: Phase5Response = generator.recommend_from_query(query, recommendation_engine=engine, top_k=3)

    assert response.status == "success"
    assert response.query_summary["location"] in ["Koramangala", "Koramangala 5th Block"]
    assert response.query_summary["cluster"] == "Koramangala"
    assert len(response.recommendations) == 3
    assert response.meta["execution_time_ms"] > 0
    assert response.meta["execution_time_ms"] < 600

    # Verify JSON Schema Contract conforms to ARCHITECTURE.md
    first_rec = response.recommendations[0]
    assert first_rec.match_rank == 1
    assert first_rec.restaurant_id
    assert first_rec.name
    assert first_rec.location
    assert first_rec.location_cluster
    assert isinstance(first_rec.cuisines, list)
    assert first_rec.price_for_two <= 1000
    assert first_rec.rating >= 4.0
    assert len(first_rec.recommendation_reason) > 20
    assert "romantic" in first_rec.recommendation_reason.lower()


@pytest.mark.skipif(not CLEAN_DATA_FILE.exists(), reason="Requires Phase 2 clean dataset")
def test_recommendation_generator_relaxed_query():
    """Verify Phase 5 cleanly carries forward Phase 4 progressive relaxation notes."""
    generator = RecommendationGenerator(use_mock=True)

    query = {
        "location": "Indiranagar",
        "cuisines": "Mexican",
        "max_budget": 150,
        "min_rating": 4.8,
    }

    engine = RecommendationEngine(data_path=CLEAN_DATA_FILE)
    response: Phase5Response = generator.recommend_from_query(query, recommendation_engine=engine, top_k=3)

    assert response.status == "success"
    assert response.was_relaxed is True
    assert len(response.relaxation_notes) > 0
    assert len(response.recommendations) > 0


def test_guardrail_total_hallucination_backfill(sample_preference, sample_candidates):
    """Verify that if LLM returns 100% hallucinated entries, all are dropped and candidates backfilled."""
    total_fake_output = LLMStructuredOutput(
        recommendations=[
            LLMRecommendationItem(
                restaurant_id="fake-id-1",
                name="Fake Pizza Palace",
                recommendation_reason="Invented reason.",
            ),
            LLMRecommendationItem(
                restaurant_id="fake-id-2",
                name="Fake Pasta Paradise",
                recommendation_reason="Invented reason.",
            ),
        ]
    )

    curated = AntiHallucinationGuardrail.validate_and_merge(
        total_fake_output, sample_candidates, sample_preference
    )

    assert len(curated) == len(sample_candidates)
    names = [c.name for c in curated]
    assert "Fake Pizza Palace" not in names
    assert "Fake Pasta Paradise" not in names
    assert "Toscano" in names
    assert "Little Italy" in names


def test_json_response_contract_serialization(sample_preference, sample_candidates):
    """Verify Phase5Response serializes to valid JSON matching ARCHITECTURE.md spec."""
    generator = RecommendationGenerator(use_mock=True)
    resp = generator.generate(sample_preference, sample_candidates)

    data = resp.model_dump()
    assert data["status"] == "success"
    assert "query_summary" in data
    assert "total_candidates_found" in data
    assert "recommendations" in data
    assert "meta" in data

    first = data["recommendations"][0]
    expected_fields = [
        "restaurant_id",
        "name",
        "location",
        "cuisines",
        "price_for_two",
        "rating",
        "votes",
        "popular_dishes",
        "recommendation_reason",
        "match_rank",
    ]
    for field in expected_fields:
        assert field in first, f"Missing required field {field} in recommendation"

