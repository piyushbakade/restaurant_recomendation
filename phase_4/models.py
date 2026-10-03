"""
Data models for Phase 4: Restaurant Retrieval & Recommendation Engine.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CandidateRestaurant(BaseModel):
    """
    Representation of a candidate restaurant retrieved from the database/catalog.
    """
    restaurant_id: str
    name: str
    address: str
    location: str
    location_cluster: str
    cuisines: List[str]
    cost_for_two: int
    rate: Optional[float] = None
    votes: int = 0
    rest_type: str = "Casual Dining"
    dish_liked: List[str] = Field(default_factory=list)
    sample_reviews: List[str] = Field(default_factory=list)
    online_order: bool = False
    book_table: bool = False
    is_new: bool = False
    url: str = ""


class ScoreBreakdown(BaseModel):
    """
    Detailed audit of individual heuristic component scores (all normalized between 0.0 and 1.0).
    """
    cuisine_score: float = Field(ge=0.0, le=1.0)
    rating_score: float = Field(ge=0.0, le=1.0)
    price_score: float = Field(ge=0.0, le=1.0)
    popularity_score: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)


class ScoredRestaurant(BaseModel):
    """
    A candidate restaurant with its calculated ranking score and rank index.
    """
    restaurant: CandidateRestaurant
    scores: ScoreBreakdown
    rank: int = Field(ge=1)

    def to_llm_candidate_dict(self) -> Dict[str, Any]:
        """
        Produces clean dictionary representation suitable for prompt injection into Phase 5 LLM.
        """
        return {
            "restaurant_id": self.restaurant.restaurant_id,
            "name": self.restaurant.name,
            "location": self.restaurant.location,
            "area_cluster": self.restaurant.location_cluster,
            "cuisines": self.restaurant.cuisines,
            "cost_for_two": self.restaurant.cost_for_two,
            "rating": self.restaurant.rate if self.restaurant.rate is not None else "New / Unrated",
            "votes": self.restaurant.votes,
            "popular_dishes": self.restaurant.dish_liked[:4] if self.restaurant.dish_liked else ["Chef's Specials"],
            "review_highlights": self.restaurant.sample_reviews[:2] if self.restaurant.sample_reviews else [],
            "match_rank": self.rank,
        }


class RecommendationResponse(BaseModel):
    """
    Standardized response from the Phase 4 Recommendation Engine.
    """
    query_location: str
    query_cluster: str
    query_cuisines: List[str]
    query_budget: int
    query_rating: float
    total_candidates_found: int
    was_relaxed: bool = False
    relaxation_notes: List[str] = Field(default_factory=list)
    top_recommendations: List[ScoredRestaurant]
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
