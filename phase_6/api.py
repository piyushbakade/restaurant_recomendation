"""
API Request Handler and Route Controllers for Phase 6.
Provides schema validation and connects HTTP endpoints to Phase 3-5 recommendation engine.
"""
import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator

from phase_4.engine import RecommendationEngine
from phase_5.generator import (
    DeterministicMockProvider,
    GeminiProvider,
    RecommendationGenerator,
    TemplateFallbackProvider,
)
from phase_6.config import POPULAR_CUISINES, POPULAR_LOCATIONS

logger = logging.getLogger(__name__)


class RecommendationRequest(BaseModel):
    """Schema for POST /api/recommendations request body."""
    location: str = Field(..., min_length=1, description="Target location or neighborhood in Bangalore")
    cuisines: Optional[Union[List[str], str]] = Field(default=None, description="Preferred cuisines")
    max_budget: Optional[Union[int, str]] = Field(default=1000, description="Budget ceiling in Rupees for two")
    min_rating: Optional[float] = Field(default=3.8, ge=1.0, le=5.0, description="Minimum star rating (1.0 - 5.0)")
    vibe_or_notes: Optional[str] = Field(default=None, max_length=500, description="Dining occasion or atmosphere notes")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of recommendations to return")
    online_order_only: Optional[bool] = Field(default=False, description="Filter for online delivery support")
    book_table_only: Optional[bool] = Field(default=False, description="Filter for table reservation support")
    provider: Optional[str] = Field(default=None, description="Optional override: 'gemini', 'mock', 'template'")

    @field_validator("location")
    @classmethod
    def validate_location_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Location cannot be empty.")
        return s


# Shared singleton instances for fast in-memory execution
_default_engine: Optional[RecommendationEngine] = None
_default_generator: Optional[RecommendationGenerator] = None


def get_engine() -> RecommendationEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = RecommendationEngine()
    return _default_engine


def get_generator(provider_override: Optional[str] = None) -> RecommendationGenerator:
    global _default_generator
    if provider_override == "mock":
        return RecommendationGenerator(provider=DeterministicMockProvider())
    elif provider_override == "template":
        return RecommendationGenerator(provider=TemplateFallbackProvider())
    elif provider_override == "gemini":
        return RecommendationGenerator(provider=GeminiProvider())

    if _default_generator is None:
        _default_generator = RecommendationGenerator()
    return _default_generator


def handle_recommendations_endpoint(
    data: Dict[str, Any],
    generator: Optional[RecommendationGenerator] = None,
    engine: Optional[RecommendationEngine] = None,
) -> Dict[str, Any]:
    """
    Executes the POST /api/recommendations flow with validation and structured response.
    """
    # 1. Validate payload
    req = RecommendationRequest(**data)

    rec_engine = engine or get_engine()
    rec_generator = generator or get_generator(req.provider)

    query_payload = {
        "location": req.location,
        "cuisines": req.cuisines,
        "max_budget": req.max_budget,
        "min_rating": req.min_rating,
        "vibe_or_notes": req.vibe_or_notes,
        "online_order_only": req.online_order_only,
        "book_table_only": req.book_table_only,
    }

    # 2. Execute end-to-end recommendation pipeline (Phase 3 -> 4 -> 5)
    response = rec_generator.recommend_from_query(
        query=query_payload,
        recommendation_engine=rec_engine,
        top_k=req.top_k or 5,
    )

    from phase_7.formatter import ResponseFormatter
    formatted = ResponseFormatter.from_phase5_response(
        response,
        provider_name=rec_generator.provider_name,
    )
    return formatted.model_dump()


def handle_health_endpoint() -> Dict[str, Any]:
    """Handles GET /api/health."""
    rec_engine = get_engine()
    catalog_count = len(rec_engine.retriever._get_dataframe()) if rec_engine.retriever.data_path.exists() else 0

    return {
        "status": "healthy",
        "service": "AI-Restaurant-Recommendation-API",
        "version": "1.0.0",
        "catalog_size": catalog_count,
        "endpoints": [
            "POST /api/recommendations",
            "GET /api/health",
            "GET /api/metadata",
        ],
    }


def handle_metadata_endpoint() -> Dict[str, Any]:
    """Handles GET /api/metadata for populating UI presets."""
    return {
        "popular_locations": POPULAR_LOCATIONS,
        "popular_cuisines": POPULAR_CUISINES,
        "default_budget": 1000,
        "min_budget": 200,
        "max_budget": 4000,
    }
