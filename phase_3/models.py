"""
Pydantic data models for Phase 3: User Preference Ingestion & Normalization.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class BudgetTier(str, Enum):
    BUDGET = "budget"          # <= ₹500 for two
    MID_RANGE = "mid_range"    # ₹500 - ₹1,500 for two
    PREMIUM = "premium"        # > ₹1,500 for two


class UserPreferenceInput(BaseModel):
    """
    Raw user preference payload as received from frontend UI, query params, or CLI.
    """
    location: str = Field(
        ...,
        min_length=2,
        description="Target dining area, locality, or neighborhood in Bangalore (e.g., 'Koramangala', 'Indiranagar').",
    )
    max_budget: Optional[Union[int, float, str]] = Field(
        default=None,
        description="Maximum budget for two in Rupees (e.g. 1000, '₹1,200') or budget tier string ('budget', 'mid-range', 'premium').",
    )
    cuisines: Optional[Union[List[str], str]] = Field(
        default=None,
        description="Desired cuisines as a list (['Italian', 'Pizza']) or comma-separated string ('Italian, Pizza').",
    )
    min_rating: Optional[Union[float, int, str]] = Field(
        default=None,
        description="Minimum restaurant rating out of 5.0 (e.g. 4.0, '4.2', '4+'). Default is 3.5.",
    )
    vibe_or_notes: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Optional free-text note describing occasion, atmosphere, or dietary preference (e.g., 'cozy date night', 'veg only').",
    )
    online_order_only: bool = Field(
        default=False,
        description="Filter only for restaurants that support online ordering.",
    )
    book_table_only: bool = Field(
        default=False,
        description="Filter only for restaurants that support table booking.",
    )

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Location must be at least 2 characters long.")
        return cleaned

    @field_validator("vibe_or_notes")
    @classmethod
    def sanitize_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None


class NormalizedPreference(BaseModel):
    """
    Fully validated, normalized, and canonicalized user preference structure.
    Used downstream by Phase 4 (Candidate Retrieval) and Phase 5 (LLM Reasoning).
    """
    raw_location: str
    resolved_location: str
    resolved_cluster: str
    location_match_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Fuzzy match confidence score (1.0 = exact match).",
    )
    cuisines: List[str] = Field(
        default_factory=list,
        description="Canonical list of desired cuisines (title-cased). Empty list means any cuisine is accepted.",
    )
    max_budget: int = Field(
        ge=50,
        le=25000,
        description="Normalized maximum price for two in Rupees.",
    )
    budget_tier: BudgetTier
    min_rating: float = Field(
        ge=1.0,
        le=5.0,
        description="Normalized minimum rating floor.",
    )
    vibe_or_notes: Optional[str] = None
    online_order_only: bool = False
    book_table_only: bool = False
    is_relaxed: bool = Field(
        default=False,
        description="Flag indicating if filters were relaxed during processing.",
    )

    def to_sql_filters(self) -> Dict[str, Any]:
        """
        Returns parameters tailored for Phase 4 SQL candidate retrieval query.
        """
        return {
            "resolved_location": self.resolved_location,
            "resolved_cluster": self.resolved_cluster,
            "target_cuisines": self.cuisines,
            "max_budget": self.max_budget,
            "min_rating": self.min_rating,
            "online_order_only": self.online_order_only,
            "book_table_only": self.book_table_only,
        }

    def to_llm_context(self) -> str:
        """
        Returns a concise natural language summary of user preferences for the LLM prompt.
        """
        cuisine_str = ", ".join(self.cuisines) if self.cuisines else "Any / Open to all"
        notes_str = f"Special Vibe/Occasion: '{self.vibe_or_notes}'" if self.vibe_or_notes else "Occasion: General dining"
        return (
            f"Location: {self.resolved_location} ({self.resolved_cluster})\n"
            f"Desired Cuisines: {cuisine_str}\n"
            f"Budget Limit: Up to Rs. {self.max_budget:,} for two ({self.budget_tier.value})\n"
            f"Minimum Rating: {self.min_rating} / 5.0\n"
            f"{notes_str}"
        )
