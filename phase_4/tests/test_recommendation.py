"""
Automated Test Suite for Phase 4: Restaurant Retrieval & Recommendation Engine.

Covers:
- Heuristic scoring mathematical components (cuisine Jaccard, rating, price proximity, popularity)
- Ranking sort order, tie-breaking, and rank indexing
- Candidate retrieval and filtering logic
- Progressive fallback relaxation on overly restrictive queries
- RecommendationEngine end-to-end pipeline execution
- Phase 5 LLM payload serialization contract
"""
import math
import pytest

from phase_3.models import BudgetTier, NormalizedPreference
from phase_4.config import (
    CLEAN_DATA_FILE,
    DEFAULT_NEUTRAL_RATING,
    WEIGHT_CUISINE,
    WEIGHT_POPULARITY,
    WEIGHT_PRICE,
    WEIGHT_RATING,
)
from phase_4.engine import RecommendationEngine
from phase_4.models import CandidateRestaurant, RecommendationResponse, ScoredRestaurant
from phase_4.ranker import HeuristicRankingEngine
from phase_4.retriever import CandidateRetriever


@pytest.fixture
def ranker() -> HeuristicRankingEngine:
    return HeuristicRankingEngine()


@pytest.fixture
def sample_preference() -> NormalizedPreference:
    return NormalizedPreference(
        raw_location="koramangla",
        resolved_location="Koramangala 5th Block",
        resolved_cluster="Koramangala",
        location_match_confidence=0.95,
        cuisines=["Italian", "Pizza"],
        max_budget=1000,
        budget_tier=BudgetTier.MID_RANGE,
        min_rating=4.0,
        vibe_or_notes="cozy dinner",
    )


@pytest.fixture
def sample_candidates() -> list[CandidateRestaurant]:
    return [
        CandidateRestaurant(
            restaurant_id="r1",
            name="Toscano",
            address="Koramangala",
            location="Koramangala 5th Block",
            location_cluster="Koramangala",
            cuisines=["Italian", "Pizza", "Desserts"],
            cost_for_two=900,
            rate=4.4,
            votes=1500,
            dish_liked=["Ravioli", "Tiramisu"],
            sample_reviews=["Authentic Italian pasta."],
        ),
        CandidateRestaurant(
            restaurant_id="r2",
            name="Empire",
            address="Koramangala",
            location="Koramangala 5th Block",
            location_cluster="Koramangala",
            cuisines=["North Indian", "Biryani"],
            cost_for_two=800,
            rate=4.1,
            votes=3000,
            dish_liked=["Ghee Rice", "Kebab"],
            sample_reviews=["Late night eats."],
        ),
        CandidateRestaurant(
            restaurant_id="r3",
            name="Little Italy",
            address="Koramangala",
            location="Koramangala 1st Block",
            location_cluster="Koramangala",
            cuisines=["Italian", "Pizza"],
            cost_for_two=1000,
            rate=4.2,
            votes=900,
            dish_liked=["Wood fired pizza"],
            sample_reviews=["Great veg Italian."],
        ),
    ]


# -------------------------------------------------------------------------
# Unit Tests: Ranking Mathematical Formulas
# -------------------------------------------------------------------------

def test_heuristic_ranking_weights(ranker):
    """Verify ranking weights sum to 1.0."""
    total = ranker.w_cuisine + ranker.w_rating + ranker.w_price + ranker.w_pop
    assert math.isclose(total, 1.0, rel_tol=1e-3)


def test_score_cuisine_jaccard(ranker):
    """Verify cuisine similarity scoring."""
    # High overlap
    score_high = ranker.score_cuisine(["Italian", "Pizza", "Desserts"], ["Italian", "Pizza"])
    assert score_high >= 0.75

    # Partial/zero overlap
    score_zero = ranker.score_cuisine(["North Indian", "Biryani"], ["Italian", "Pizza"])
    assert score_zero <= 0.2

    # Open preference (no target cuisines) gives full score
    score_open = ranker.score_cuisine(["North Indian"], [])
    assert score_open == 1.0


def test_score_rating(ranker):
    """Verify rating normalization."""
    assert ranker.score_rating(5.0) == 1.0
    assert ranker.score_rating(4.0) == 0.8
    assert ranker.score_rating(3.0) == 0.6

    # Unrated receives neutral baseline
    assert ranker.score_rating(None, is_new=True) == round(DEFAULT_NEUTRAL_RATING / 5.0, 3)


def test_score_price(ranker):
    """Verify price proximity scoring."""
    # Exact match
    assert ranker.score_price(1000, 1000) == 1.0

    # Near match (within 10%)
    score_near = ranker.score_price(900, 1000)
    assert score_near == 0.9

    # Moderate deviation
    score_dev = ranker.score_price(500, 1000)
    assert score_dev == 0.5


def test_score_popularity(ranker):
    """Verify log-damped popularity scoring."""
    # Zero votes
    assert ranker.score_popularity(0) == 0.0

    # Moderate votes
    score_mid = ranker.score_popularity(500)
    assert 0.5 <= score_mid <= 0.8

    # High votes
    score_high = ranker.score_popularity(15000)
    assert score_high >= 0.9


def test_ranking_sort_order(ranker, sample_candidates, sample_preference):
    """Verify candidates are sorted in descending order of final composite score."""
    ranked = ranker.rank(sample_candidates, sample_preference, top_k=3)
    assert len(ranked) == 3

    # Toscano and Little Italy (Italian match) should rank higher than Empire (North Indian) for Italian query
    assert ranked[0].restaurant.name in ["Toscano", "Little Italy"]
    assert ranked[2].restaurant.name == "Empire"

    # Ranks must be 1, 2, 3
    assert [r.rank for r in ranked] == [1, 2, 3]

    # Scores must be in strictly non-increasing order
    assert ranked[0].scores.final_score >= ranked[1].scores.final_score
    assert ranked[1].scores.final_score >= ranked[2].scores.final_score


# -------------------------------------------------------------------------
# Integration Tests: Candidate Retrieval & Fallback Relaxation
# -------------------------------------------------------------------------

@pytest.mark.skipif(not CLEAN_DATA_FILE.exists(), reason="Requires Phase 2 clean dataset")
def test_retriever_standard_query(sample_preference):
    """Verify candidate retriever returns valid matches for a standard query."""
    retriever = CandidateRetriever(data_path=CLEAN_DATA_FILE)
    candidates, was_relaxed, notes = retriever.retrieve(sample_preference, pool_limit=20)

    assert len(candidates) > 0
    assert len(candidates) <= 20
    assert was_relaxed is False

    # Check candidates meet budget criteria
    for c in candidates:
        assert c.cost_for_two <= sample_preference.max_budget
        assert c.location_cluster == "Koramangala"


@pytest.mark.skipif(not CLEAN_DATA_FILE.exists(), reason="Requires Phase 2 clean dataset")
def test_retriever_progressive_relaxation():
    """Verify impossible/hyper-strict query triggers relaxation notes."""
    retriever = CandidateRetriever(data_path=CLEAN_DATA_FILE)

    # Restrictive query: Mexican food under Rs. 100 with 4.9 rating in Indiranagar
    strict_pref = NormalizedPreference(
        raw_location="Indiranagar",
        resolved_location="Indiranagar",
        resolved_cluster="Indiranagar",
        location_match_confidence=1.0,
        cuisines=["Mexican"],
        max_budget=100,
        budget_tier=BudgetTier.BUDGET,
        min_rating=4.9,
    )

    candidates, was_relaxed, notes = retriever.retrieve(strict_pref, pool_limit=5)
    assert was_relaxed is True
    assert len(notes) > 0


# -------------------------------------------------------------------------
# Integration Tests: End-to-End Recommendation Engine
# -------------------------------------------------------------------------

@pytest.mark.skipif(not CLEAN_DATA_FILE.exists(), reason="Requires Phase 2 clean dataset")
def test_recommendation_engine_e2e():
    """Verify RecommendationEngine executes end-to-end with raw input dict."""
    engine = RecommendationEngine(data_path=CLEAN_DATA_FILE)

    query = {
        "location": "koramangla",
        "cuisines": "Italian, Pizza",
        "max_budget": 1000,
        "min_rating": 4.0,
        "vibe_or_notes": "romantic dinner",
    }

    response: RecommendationResponse = engine.recommend(query, top_k=3)

    assert response.query_cluster == "Koramangala"
    assert response.total_candidates_found > 0
    assert len(response.top_recommendations) == 3
    assert response.execution_time_ms > 0
    assert response.execution_time_ms < 500  # Sub-second execution

    top_rec: ScoredRestaurant = response.top_recommendations[0]
    assert top_rec.rank == 1
    assert top_rec.scores.final_score > 0.0

    # Verify Phase 5 LLM contract serialization
    llm_dict = top_rec.to_llm_candidate_dict()
    assert "restaurant_id" in llm_dict
    assert "name" in llm_dict
    assert "location" in llm_dict
    assert "cuisines" in llm_dict
    assert "cost_for_two" in llm_dict
    assert "rating" in llm_dict
    assert "popular_dishes" in llm_dict
    assert "review_highlights" in llm_dict
    assert "match_rank" in llm_dict


@pytest.mark.skipif(not CLEAN_DATA_FILE.exists(), reason="Requires Phase 2 clean dataset")
def test_retriever_booking_filter():
    """Verify retriever respects book_table_only filter."""
    retriever = CandidateRetriever(data_path=CLEAN_DATA_FILE)
    pref = NormalizedPreference(
        raw_location="Indiranagar",
        resolved_location="Indiranagar",
        resolved_cluster="Indiranagar",
        location_match_confidence=1.0,
        cuisines=["Continental"],
        max_budget=2000,
        budget_tier=BudgetTier.PREMIUM,
        min_rating=4.0,
        book_table_only=True,
    )
    candidates, _, _ = retriever.retrieve(pref, pool_limit=10)
    for c in candidates:
        assert c.book_table is True


def test_ranking_tie_breaking(ranker):
    """Verify tie-breaking prioritizes higher rate, then higher votes."""
    c1 = CandidateRestaurant(
        restaurant_id="r1",
        name="Place A",
        address="Koramangala",
        location="Koramangala 5th Block",
        location_cluster="Koramangala",
        cuisines=["Italian"],
        cost_for_two=1000,
        rate=4.5,
        votes=500,
    )
    c2 = CandidateRestaurant(
        restaurant_id="r2",
        name="Place B",
        address="Koramangala",
        location="Koramangala 5th Block",
        location_cluster="Koramangala",
        cuisines=["Italian"],
        cost_for_two=1000,
        rate=4.2,
        votes=500,
    )
    pref = NormalizedPreference(
        raw_location="Koramangala",
        resolved_location="Koramangala 5th Block",
        resolved_cluster="Koramangala",
        location_match_confidence=1.0,
        cuisines=["Italian"],
        max_budget=1000,
        budget_tier=BudgetTier.MID_RANGE,
        min_rating=4.0,
    )
    ranked = ranker.rank([c2, c1], pref, top_k=2)
    assert ranked[0].restaurant.name == "Place A"
    assert ranked[1].restaurant.name == "Place B"


@pytest.mark.skipif(not CLEAN_DATA_FILE.exists(), reason="Requires Phase 2 clean dataset")
def test_recommendation_engine_fallback_location():
    """Verify engine handles imprecise/fuzzy location input smoothly."""
    engine = RecommendationEngine(data_path=CLEAN_DATA_FILE)
    query = {
        "location": "near MG road area",
        "cuisines": "Cafe, Bakery",
        "max_budget": 600,
        "min_rating": 3.8,
    }
    response = engine.recommend(query, top_k=3)
    assert response.query_cluster in ["MG Road / Central", "Brigade / MG Road", "Central Bangalore", "Residency Road", "Church Street"]
    assert len(response.top_recommendations) > 0
    assert response.top_recommendations[0].rank == 1

