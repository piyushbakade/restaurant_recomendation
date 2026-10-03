"""
Automated Test Suite for Phase 3: User Preference Processing.

Covers:
- Pydantic models and field validators
- Fuzzy location matching and alias resolution
- Cuisine string splitting, deduplication, and typo correction
- Budget parsing, currency stripping, and budget tier mapping
- Rating floor parsing, clamping, and default fallbacks
- Phase 4 SQL filter generation contract
- Phase 5 LLM prompt context formatting contract
"""
import pytest
from pydantic import ValidationError

from phase_3.models import BudgetTier, NormalizedPreference, UserPreferenceInput
from phase_3.normalizer import PreferenceNormalizer


@pytest.fixture
def normalizer() -> PreferenceNormalizer:
    return PreferenceNormalizer()


# -------------------------------------------------------------------------
# Unit Tests: Pydantic Input Validation
# -------------------------------------------------------------------------

def test_user_preference_input_valid():
    """Verify that a valid preference dictionary instantiates properly."""
    payload = {
        "location": "Koramangala",
        "cuisines": ["Italian", "Pizza"],
        "max_budget": 1000,
        "min_rating": 4.0,
        "vibe_or_notes": "romantic dinner",
        "online_order_only": True,
        "book_table_only": False,
    }
    pref = UserPreferenceInput(**payload)
    assert pref.location == "Koramangala"
    assert pref.max_budget == 1000
    assert pref.min_rating == 4.0
    assert pref.online_order_only is True


def test_user_preference_input_empty_location():
    """Verify that empty or whitespace-only location raises validation error."""
    with pytest.raises(ValidationError):
        UserPreferenceInput(location="   ")

    with pytest.raises(ValidationError):
        UserPreferenceInput(location="a")


def test_user_preference_input_notes_sanitization():
    """Verify whitespace in notes is stripped."""
    pref = UserPreferenceInput(location="Indiranagar", vibe_or_notes="  cozy cafe  ")
    assert pref.vibe_or_notes == "cozy cafe"

    pref_blank = UserPreferenceInput(location="Indiranagar", vibe_or_notes="   ")
    assert pref_blank.vibe_or_notes is None


# -------------------------------------------------------------------------
# Unit Tests: Location Resolution & Fuzzy Matching
# -------------------------------------------------------------------------

def test_location_exact_match(normalizer):
    """Verify exact locality names resolve with 1.0 confidence."""
    loc, cluster, conf = normalizer.resolve_location("Koramangala")
    assert cluster == "Koramangala"
    assert conf == 1.0

    loc, cluster, conf = normalizer.resolve_location("Indiranagar")
    assert cluster == "Indiranagar"
    assert conf == 1.0


def test_location_aliases_and_acronyms(normalizer):
    """Verify colloquial abbreviations and sub-zones resolve correctly."""
    loc, cluster, conf = normalizer.resolve_location("HSR")
    assert cluster == "HSR Layout"
    assert conf >= 0.9

    loc, cluster, conf = normalizer.resolve_location("BTM")
    assert cluster == "BTM Layout"
    assert conf >= 0.9

    loc, cluster, conf = normalizer.resolve_location("church street")
    assert cluster == "MG Road / Central"
    assert conf >= 0.9

    loc, cluster, conf = normalizer.resolve_location("domlur")
    assert cluster == "Indiranagar"
    assert conf >= 0.9


def test_location_fuzzy_typo_correction(normalizer):
    """Verify common typos in Bangalore localities are resolved."""
    loc, cluster, conf = normalizer.resolve_location("koramangla")
    assert cluster == "Koramangala"
    assert conf >= 0.7

    loc, cluster, conf = normalizer.resolve_location("indranagar")
    assert cluster == "Indiranagar"
    assert conf >= 0.7

    loc, cluster, conf = normalizer.resolve_location("whitefeild")
    assert cluster == "Whitefield"
    assert conf >= 0.7

    loc, cluster, conf = normalizer.resolve_location("jayanagr")
    assert cluster == "Jayanagar"
    assert conf >= 0.7


# -------------------------------------------------------------------------
# Unit Tests: Cuisine Parsing & Normalization
# -------------------------------------------------------------------------

def test_cuisine_resolution_list(normalizer):
    """Verify list of cuisines is normalized."""
    cuisines = normalizer.resolve_cuisines(["italian", "PIZZA", "north indian"])
    assert "Italian" in cuisines
    assert "Pizza" in cuisines
    assert "North Indian" in cuisines


def test_cuisine_resolution_comma_string(normalizer):
    """Verify comma-separated string input is split and title-cased."""
    cuisines = normalizer.resolve_cuisines("Italian, Mexican, Chinese")
    assert cuisines == ["Italian", "Mexican", "Chinese"]


def test_cuisine_fuzzy_typos(normalizer):
    """Verify minor typos in popular cuisines resolve to canonical form."""
    cuisines = normalizer.resolve_cuisines(["pizzza", "biryany"])
    assert "Pizza" in cuisines
    assert "Biryani" in cuisines


def test_cuisine_empty_handling(normalizer):
    """Verify empty cuisine input returns empty list."""
    assert normalizer.resolve_cuisines(None) == []
    assert normalizer.resolve_cuisines("") == []
    assert normalizer.resolve_cuisines([]) == []


# -------------------------------------------------------------------------
# Unit Tests: Budget Parsing & Tier Mapping
# -------------------------------------------------------------------------

def test_budget_numeric_and_tier_mapping(normalizer):
    """Verify numeric budget parsing and tier assignment."""
    budget, tier = normalizer.resolve_budget(450)
    assert budget == 450
    assert tier == BudgetTier.BUDGET

    budget, tier = normalizer.resolve_budget(1200)
    assert budget == 1200
    assert tier == BudgetTier.MID_RANGE

    budget, tier = normalizer.resolve_budget(2500)
    assert budget == 2500
    assert tier == BudgetTier.PREMIUM


def test_budget_string_formatting(normalizer):
    """Verify currency symbols and commas are stripped."""
    budget, tier = normalizer.resolve_budget("₹1,200")
    assert budget == 1200
    assert tier == BudgetTier.MID_RANGE

    budget, tier = normalizer.resolve_budget("Rs. 400 for two")
    assert budget == 400
    assert tier == BudgetTier.BUDGET


def test_budget_textual_tiers(normalizer):
    """Verify textual tier descriptions map to budget amounts."""
    budget, tier = normalizer.resolve_budget("cheap")
    assert budget == 500
    assert tier == BudgetTier.BUDGET

    budget, tier = normalizer.resolve_budget("mid-range")
    assert budget == 1200
    assert tier == BudgetTier.MID_RANGE

    budget, tier = normalizer.resolve_budget("fine_dining")
    assert budget == 2500
    assert tier == BudgetTier.PREMIUM


def test_budget_clamping(normalizer):
    """Verify budget is bounded within reasonable min and max limits."""
    budget, _ = normalizer.resolve_budget(10)
    assert budget == 50  # MIN_ALLOWED_BUDGET

    budget, _ = normalizer.resolve_budget(50000)
    assert budget == 25000  # MAX_ALLOWED_BUDGET


# -------------------------------------------------------------------------
# Unit Tests: Rating Normalization
# -------------------------------------------------------------------------

def test_rating_resolution(normalizer):
    """Verify rating parsing from float, int, and string."""
    assert normalizer.resolve_rating(4.2) == 4.2
    assert normalizer.resolve_rating(4) == 4.0
    assert normalizer.resolve_rating("4.0") == 4.0
    assert normalizer.resolve_rating("4+") == 4.0
    assert normalizer.resolve_rating("4.5 stars") == 4.5
    assert normalizer.resolve_rating(None) == 3.5  # Default


def test_rating_clamping(normalizer):
    """Verify rating bounds between 1.0 and 5.0."""
    assert normalizer.resolve_rating(0.5) == 1.0
    assert normalizer.resolve_rating(6.0) == 5.0


# -------------------------------------------------------------------------
# Integration Tests: End-to-End Normalization & Phase Contracts
# -------------------------------------------------------------------------

def test_end_to_end_normalization(normalizer):
    """Verify complete conversion from UserPreferenceInput to NormalizedPreference."""
    raw_input = UserPreferenceInput(
        location="koramangla",
        cuisines="Italian, Pizza",
        max_budget="Rs. 1,000",
        min_rating="4+",
        vibe_or_notes="cozy rooftop date night",
        online_order_only=True,
    )

    norm: NormalizedPreference = normalizer.normalize(raw_input)

    assert norm.raw_location == "koramangla"
    assert norm.resolved_cluster == "Koramangala"
    assert norm.location_match_confidence >= 0.7
    assert "Italian" in norm.cuisines
    assert "Pizza" in norm.cuisines
    assert norm.max_budget == 1000
    assert norm.budget_tier == BudgetTier.MID_RANGE
    assert norm.min_rating == 4.0
    assert norm.vibe_or_notes == "cozy rooftop date night"
    assert norm.online_order_only is True
    assert norm.book_table_only is False

    # Test Phase 4 SQL filter export contract
    sql_params = norm.to_sql_filters()
    assert sql_params["resolved_cluster"] == "Koramangala"
    assert sql_params["max_budget"] == 1000
    assert sql_params["min_rating"] == 4.0
    assert "Italian" in sql_params["target_cuisines"]

    # Test Phase 5 LLM prompt context contract
    llm_context = norm.to_llm_context()
    assert "Koramangala" in llm_context
    assert "Italian" in llm_context
    assert "Rs. 1,000" in llm_context
    assert "cozy rooftop date night" in llm_context
