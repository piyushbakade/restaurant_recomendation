"""
Pydantic contracts and data models for Phase 7 Output Layer.
Implements the exact JSON response contract defined in ARCHITECTURE.md line 283-310.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuerySummaryContract(BaseModel):
    """Normalized query parameters summarized in the response."""
    model_config = ConfigDict(extra="ignore")

    location: str = Field(..., description="Target locality or neighborhood")
    cuisines: List[str] = Field(default_factory=list, description="Requested cuisine list")
    max_budget: int = Field(..., ge=0, description="Budget ceiling in INR for two")
    min_rating: float = Field(..., ge=0.0, le=5.0, description="Minimum star rating filter")
    cluster: Optional[str] = Field(default=None, description="Macro neighborhood cluster")
    vibe_or_notes: Optional[str] = Field(default=None, description="Occasion / dining atmosphere notes")


class RestaurantOutputContract(BaseModel):
    """Individual restaurant recommendation item in the response payload."""
    model_config = ConfigDict(extra="ignore")

    restaurant_id: str = Field(..., description="Unique UUID identifier of the restaurant")
    name: str = Field(..., description="Official verified restaurant name")
    location: str = Field(..., description="Specific restaurant address / micro-locality")
    cuisines: List[str] = Field(default_factory=list, description="Array of offered cuisines")
    price_for_two: int = Field(..., ge=0, description="Approximate dining cost in INR for two people")
    rating: Optional[float] = Field(default=None, ge=0.0, le=5.0, description="Verified diner rating (out of 5.0)")
    votes: int = Field(default=0, ge=0, description="Total verified customer review count")
    popular_dishes: List[str] = Field(default_factory=list, description="Verified signature dishes")
    recommendation_reason: str = Field(
        ...,
        min_length=10,
        description="Personalized 2-3 sentence explanation grounded in diner preferences and catalog facts",
    )
    # Optional metadata enrichments
    url: Optional[str] = Field(default=None, description="Zomato web URL for the restaurant")
    match_rank: Optional[int] = Field(default=None, ge=1, description="Ranking index (1-based)")
    location_cluster: Optional[str] = Field(default=None, description="Broad geographic cluster")

    @field_validator("rating")
    @classmethod
    def round_rating(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            return round(v, 1)
        return None


class MetaContract(BaseModel):
    """Performance telemetry and system execution metadata."""
    model_config = ConfigDict(extra="ignore")

    execution_time_ms: int = Field(..., ge=0, description="Total processing latency in milliseconds")
    timestamp: Optional[str] = Field(default=None, description="ISO-8601 formatted response timestamp")
    provider: Optional[str] = Field(default=None, description="AI provider or heuristic engine name")
    engine_version: str = Field(default="1.0.0", description="Semantic version of the recommendation engine")


class StandardSuccessResponse(BaseModel):
    """
    Standardized Success JSON Response Contract conforming to ARCHITECTURE.md Phase 7.
    """
    model_config = ConfigDict(extra="ignore")

    status: str = Field(default="success", description="Response status flag ('success')")
    query_summary: QuerySummaryContract = Field(..., description="Echo of user search parameters")
    total_candidates_found: int = Field(..., ge=0, description="Count of candidate venues matching criteria")
    recommendations: List[RestaurantOutputContract] = Field(
        ...,
        description="Ranked list of curated personalized recommendations",
    )
    was_relaxed: bool = Field(default=False, description="Whether search filters were broadened")
    relaxation_notes: List[str] = Field(default_factory=list, description="Details of broadened criteria")
    meta: MetaContract = Field(..., description="Latency and execution telemetry")


class StandardErrorResponse(BaseModel):
    """
    Standardized Error JSON Response Contract for edge cases and failures.
    """
    model_config = ConfigDict(extra="ignore")

    status: str = Field(default="error", description="Response status flag ('error')")
    error_code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable description of the error")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional diagnostic details")
    meta: MetaContract = Field(..., description="Execution telemetry")
