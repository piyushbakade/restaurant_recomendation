"""
Unified Recommendation Engine orchestrator for Phase 4.
Coordinates Preference Normalization, Candidate Retrieval, and Heuristic Ranking.
"""
import time
from typing import Any, Dict, Optional, Union

from phase_3.models import NormalizedPreference, UserPreferenceInput
from phase_3.normalizer import PreferenceNormalizer
from phase_4.config import (
    CLEAN_DATA_FILE,
    DEFAULT_CANDIDATE_POOL_LIMIT,
    DEFAULT_TOP_K_RECOMMENDATIONS,
)
from phase_4.models import RecommendationResponse
from phase_4.ranker import HeuristicRankingEngine
from phase_4.retriever import CandidateRetriever


class RecommendationEngine:
    """
    Main engine orchestrating the retrieval and ranking of restaurants.
    """

    def __init__(self, data_path=CLEAN_DATA_FILE):
        self.normalizer = PreferenceNormalizer()
        self.retriever = CandidateRetriever(data_path=data_path)
        self.ranker = HeuristicRankingEngine()

    def recommend(
        self,
        preference_input: Union[NormalizedPreference, UserPreferenceInput, Dict[str, Any]],
        top_k: int = DEFAULT_TOP_K_RECOMMENDATIONS,
        pool_limit: int = DEFAULT_CANDIDATE_POOL_LIMIT,
    ) -> RecommendationResponse:
        """
        Executes end-to-end recommendation workflow:
        1. Normalizes user preferences (Phase 3 integration)
        2. Filters and retrieves candidate pool (Phase 4A)
        3. Ranks candidates using multi-factor heuristic scoring (Phase 4B)
        4. Emits structured RecommendationResponse ready for Phase 5 LLM reasoning
        """
        start_time = time.perf_counter()

        # Step 1: Ensure preferences are normalized
        if isinstance(preference_input, NormalizedPreference):
            norm_pref = preference_input
        else:
            norm_pref = self.normalizer.normalize(preference_input)

        # Step 2: Retrieve candidate pool with fallback relaxation
        candidates, was_relaxed, relaxation_notes = self.retriever.retrieve(
            preference=norm_pref,
            pool_limit=pool_limit,
        )

        # Step 3: Heuristic ranking and top-k selection
        top_recommendations = self.ranker.rank(
            candidates=candidates,
            preference=norm_pref,
            top_k=top_k,
        )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return RecommendationResponse(
            query_location=norm_pref.resolved_location,
            query_cluster=norm_pref.resolved_cluster,
            query_cuisines=norm_pref.cuisines,
            query_budget=norm_pref.max_budget,
            query_rating=norm_pref.min_rating,
            total_candidates_found=len(candidates),
            was_relaxed=was_relaxed,
            relaxation_notes=relaxation_notes,
            top_recommendations=top_recommendations,
            execution_time_ms=elapsed_ms,
        )
