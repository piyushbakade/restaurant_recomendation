"""
Candidate retrieval module for Phase 4.
Filters the clean restaurant catalog based on location, budget, rating, and cuisine,
with automatic progressive fallback relaxation when candidate pools are small.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from phase_3.models import NormalizedPreference
from phase_4.config import (
    BUDGET_RELAXATION_MULTIPLIER,
    CLEAN_DATA_FILE,
    DEFAULT_CANDIDATE_POOL_LIMIT,
    MIN_CANDIDATES_BEFORE_RELAXATION,
    RATING_RELAXATION_STEP,
)
from phase_4.models import CandidateRestaurant

logger = logging.getLogger(__name__)


class CandidateRetriever:
    """
    Executes fast structured filtering over the processed restaurant catalog.
    """

    def __init__(self, data_path: Path = CLEAN_DATA_FILE):
        self.data_path = Path(data_path)
        self._df: Optional[pd.DataFrame] = None

    def _get_dataframe(self) -> pd.DataFrame:
        """Loads and caches the cleaned dataset in memory."""
        if self._df is None:
            if not self.data_path.exists():
                raise FileNotFoundError(
                    f"Cleaned restaurant catalog not found at {self.data_path}. "
                    f"Please run Phase 2 processing first: python phase_2/run_processing.py"
                )
            logger.info(f"Loading restaurant catalog into memory from {self.data_path}...")
            self._df = pd.read_parquet(self.data_path)
            logger.info(f"Loaded {len(self._df):,} clean restaurant records.")
        return self._df

    def retrieve(
        self,
        preference: NormalizedPreference,
        pool_limit: int = DEFAULT_CANDIDATE_POOL_LIMIT,
    ) -> Tuple[List[CandidateRestaurant], bool, List[str]]:
        """
        Retrieves candidate restaurants matching normalized user preferences.
        Applies progressive filter relaxation if fewer than MIN_CANDIDATES_BEFORE_RELAXATION are found.
        """
        df = self._get_dataframe()
        was_relaxed = False
        relaxation_notes: List[str] = []

        # Current working filter parameters
        active_cluster = preference.resolved_cluster
        active_location = preference.resolved_location
        active_budget = preference.max_budget
        active_rating = preference.min_rating
        active_cuisines = list(preference.cuisines)

        # -------------------------------------------------------------
        # Filter Helper Function
        # -------------------------------------------------------------
        def apply_filter(
            loc_cluster: str,
            loc_micro: str,
            budget: int,
            rating: float,
            cuisines: List[str],
            citywide: bool = False,
        ) -> pd.DataFrame:
            # 1. Location Condition
            if citywide:
                loc_mask = pd.Series(True, index=df.index)
            else:
                loc_mask = (df["location_cluster"].str.lower() == loc_cluster.lower()) | (
                    df["location"].str.contains(loc_micro, case=False, na=False)
                )

            # 2. Budget Condition
            budget_mask = df["cost_for_two"] <= budget

            # 3. Rating Condition (allow unrated if rating threshold is low <= 3.5 or is_new)
            if rating <= 3.5:
                rating_mask = (df["rate"] >= rating) | df["rate"].isna()
            else:
                rating_mask = df["rate"] >= rating

            # 4. Cuisine Overlap Condition
            if cuisines:
                target_lowers = [c.lower() for c in cuisines]
                cuisine_mask = df["cuisines"].apply(
                    lambda c_list: any(
                        any(t in str(item).lower() for t in target_lowers) for item in c_list
                    ) if hasattr(c_list, "__iter__") and not isinstance(c_list, (str, bytes)) else False
                )
            else:
                cuisine_mask = pd.Series(True, index=df.index)

            # 5. Optional flags
            online_mask = df["online_order"] if preference.online_order_only else pd.Series(True, index=df.index)
            book_mask = df["book_table"] if preference.book_table_only else pd.Series(True, index=df.index)

            combined_mask = loc_mask & budget_mask & rating_mask & cuisine_mask & online_mask & book_mask
            return df[combined_mask].copy()

        # -------------------------------------------------------------
        # Step 1: Strict Execution
        # -------------------------------------------------------------
        matches = apply_filter(
            active_cluster, active_location, active_budget, active_rating, active_cuisines
        )

        # -------------------------------------------------------------
        # Step 2: Progressive Relaxation (if candidates < threshold)
        # -------------------------------------------------------------
        # Relaxation Round 1: Expand budget (+35%) and soften rating (-0.4) for requested cuisine in area
        if len(matches) < MIN_CANDIDATES_BEFORE_RELAXATION:
            was_relaxed = True
            new_budget = int(active_budget * 1.35)
            new_rating = round(max(3.2, active_rating - RATING_RELAXATION_STEP), 1)
            relaxation_notes.append(
                f"Expanded budget to Rs. {new_budget:,} (+35%) and adjusted rating floor to {new_rating} stars for {active_cuisines or 'requested'} dining in {active_cluster}."
            )
            active_budget = new_budget
            active_rating = new_rating
            matches = apply_filter(
                active_cluster, active_location, active_budget, active_rating, active_cuisines
            )

        # Relaxation Round 2: City-wide search for the requested cuisines
        if len(matches) < MIN_CANDIDATES_BEFORE_RELAXATION and active_cuisines:
            was_relaxed = True
            relaxation_notes.append(
                f"Expanded search radius to highly-rated {', '.join(active_cuisines)} venues across all Bangalore neighborhoods."
            )
            matches = apply_filter(
                active_cluster,
                active_location,
                active_budget,
                active_rating,
                active_cuisines,
                citywide=True,
            )

        # Relaxation Round 3: Broaden cuisine filter in the user's preferred neighborhood
        if len(matches) < MIN_CANDIDATES_BEFORE_RELAXATION and active_cuisines:
            was_relaxed = True
            relaxation_notes.append(
                f"Broadened cuisine filter to include top-rated alternative dining spots in {active_cluster}."
            )
            active_cuisines = []
            matches = apply_filter(
                active_cluster, active_location, active_budget, active_rating, active_cuisines
            )

        # Relaxation Round 4: Guaranteed fallback - top overall venues in target neighborhood
        if len(matches) < MIN_CANDIDATES_BEFORE_RELAXATION:
            was_relaxed = True
            relaxation_notes.append(
                f"Showing top-rated signature restaurants in {active_cluster}."
            )
            matches = apply_filter(
                active_cluster,
                active_location,
                budget=5000,
                rating=3.5,
                cuisines=[],
                citywide=False,
            )

        # -------------------------------------------------------------
        # Step 3: Prioritize & Slice Candidate Pool
        # -------------------------------------------------------------
        # Sort by rate descending (nulls last) and votes descending
        matches = matches.sort_values(
            by=["rate", "votes"],
            ascending=[False, False],
            na_position="last",
        ).head(pool_limit)

        candidates: List[CandidateRestaurant] = []
        for _, row in matches.iterrows():
            candidates.append(
                CandidateRestaurant(
                    restaurant_id=str(row["restaurant_id"]),
                    name=str(row["name"]),
                    address=str(row["address"]),
                    location=str(row["location"]),
                    location_cluster=str(row["location_cluster"]),
                    cuisines=[str(c) for c in row["cuisines"]] if hasattr(row["cuisines"], "__iter__") and not isinstance(row["cuisines"], (str, bytes)) else [str(row["cuisines"])],
                    cost_for_two=int(row["cost_for_two"]),
                    rate=float(row["rate"]) if pd.notna(row["rate"]) else None,
                    votes=int(row["votes"]),
                    rest_type=str(row["rest_type"]),
                    dish_liked=[str(d) for d in row["dish_liked"]] if hasattr(row["dish_liked"], "__iter__") and not isinstance(row["dish_liked"], (str, bytes)) else [],
                    sample_reviews=[str(r) for r in row["sample_reviews"]] if hasattr(row["sample_reviews"], "__iter__") and not isinstance(row["sample_reviews"], (str, bytes)) else [],
                    online_order=bool(row["online_order"]),
                    book_table=bool(row["book_table"]),
                    is_new=bool(row["is_new"]),
                    url=str(row["url"]),
                )
            )

        logger.info(
            f"Retrieved {len(candidates)} candidates for {active_cluster} "
            f"(Relaxed: {was_relaxed})."
        )
        return candidates, was_relaxed, relaxation_notes
