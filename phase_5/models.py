"""
Pydantic data models and schemas for Phase 5: LLM Recommendation & Anti-Hallucination Guardrails.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LLMRecommendationItem(BaseModel):
    """
    Schema for a single recommendation emitted by the LLM.
    Strictly constrained to attributes provided in candidate metadata.
    """
    restaurant_id: str = Field(..., description="Exact restaurant UUID from candidate list")
    name: str = Field(..., description="Exact restaurant name from candidate list")
    recommendation_reason: str = Field(
        ...,
        description="Persuasive 2-3 sentence explanation of why this restaurant matches the user's specific request",
    )
    highlighted_dishes: List[str] = Field(
        default_factory=list,
        description="1 to 4 signature dishes explicitly mentioned in candidate popular dishes or reviews",
    )
    match_highlights: List[str] = Field(
        default_factory=list,
        description="Key value points e.g. ['₹600 for two (under ₹1,000 budget)', 'High 4.4★ rating', 'Authentic Italian pizza']",
    )


class LLMStructuredOutput(BaseModel):
    """
    Root JSON schema requested from the LLM.
    """
    recommendations: List[LLMRecommendationItem] = Field(
        ...,
        description="Ranked list of curated recommendations strictly selected from candidate list",
    )
    curation_summary: Optional[str] = Field(
        default=None,
        description="A warm, concise 1-sentence overview of the curated selections for the user",
    )


class FinalCuratedRestaurant(BaseModel):
    """
    Complete recommendation card combining verified catalog data with LLM personalization.
    Conforms to the standardized ARCHITECTURE.md JSON contract.
    """
    restaurant_id: str
    name: str
    location: str
    location_cluster: str
    cuisines: List[str]
    price_for_two: int
    rating: Optional[float] = None
    votes: int = 0
    popular_dishes: List[str] = Field(default_factory=list)
    recommendation_reason: str
    match_rank: int
    composite_score: float
    url: Optional[str] = None


class Phase5Response(BaseModel):
    """
    End-to-end response object for Phase 5, matching the standardized system architecture contract.
    """
    status: str = "success"
    query_summary: Dict[str, Any]
    total_candidates_found: int
    recommendations: List[FinalCuratedRestaurant]
    was_relaxed: bool = False
    relaxation_notes: List[str] = Field(default_factory=list)
    provider_used: str = "gemini"
    meta: Dict[str, Any] = Field(default_factory=dict)
