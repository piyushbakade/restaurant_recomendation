"""
Preference normalizer module for Phase 3.
Validates, normalizes, and enriches user inputs into structured query parameters.
"""
import difflib
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from phase_2.config import LOCALITY_CLUSTERS
from phase_3.config import (
    BUDGET_TIER_MAP,
    DEFAULT_MAX_BUDGET,
    DEFAULT_MIN_RATING,
    MAX_ALLOWED_BUDGET,
    MAX_ALLOWED_RATING,
    MIN_ALLOWED_BUDGET,
    MIN_ALLOWED_RATING,
    POPULAR_CUISINES,
    PRIMARY_CLUSTERS,
    load_taxonomies_from_dataset,
)
from phase_3.models import BudgetTier, NormalizedPreference, UserPreferenceInput

logger = logging.getLogger(__name__)


class PreferenceNormalizer:
    """
    Normalizes user preferences by performing fuzzy location matching,
    cuisine taxonomy resolution, and budget tier mapping.
    """

    def __init__(self):
        # Load known taxonomies from clean dataset or fallbacks
        taxonomies = load_taxonomies_from_dataset()
        self.known_locations: Set[str] = taxonomies["locations"]
        self.known_clusters: Set[str] = taxonomies["clusters"]
        self.known_cuisines: Set[str] = taxonomies["cuisines"]

        # Build reverse alias index for fast lookups
        self.alias_to_cluster: Dict[str, str] = {}
        for cluster_name, aliases in LOCALITY_CLUSTERS.items():
            for alias in aliases:
                self.alias_to_cluster[alias.lower().strip()] = cluster_name
        # Add primary clusters as self-aliases only if not already mapped
        for cluster in PRIMARY_CLUSTERS:
            cluster_key = cluster.lower().strip()
            if cluster_key not in self.alias_to_cluster:
                self.alias_to_cluster[cluster_key] = cluster

    def resolve_location(self, raw_location: str) -> Tuple[str, str, float]:
        """
        Resolves raw location input to a canonical micro-location and macro-cluster with a confidence score.
        Returns: (resolved_location, resolved_cluster, confidence_score)
        """
        loc_clean = raw_location.strip()
        loc_lower = loc_clean.lower()

        # 1. Exact alias match (confidence = 1.0)
        if loc_lower in self.alias_to_cluster:
            cluster = self.alias_to_cluster[loc_lower]
            return loc_clean.title(), cluster, 1.0

        # 2. Check exact match in known micro-locations (confidence = 1.0)
        for known_loc in self.known_locations:
            if loc_lower == known_loc.lower():
                cluster = self._find_cluster_for_location(known_loc)
                return known_loc, cluster, 1.0

        # 3. Substring containment in aliases (e.g. 'hsr' in 'hsr layout') (confidence = 0.9)
        for alias, cluster in self.alias_to_cluster.items():
            if loc_lower == alias or (len(loc_lower) >= 3 and loc_lower in alias.split()):
                return cluster, cluster, 0.9

        # 4. Substring containment in known micro-locations (confidence = 0.85)
        for known_loc in self.known_locations:
            if loc_lower in known_loc.lower() or known_loc.lower() in loc_lower:
                cluster = self._find_cluster_for_location(known_loc)
                return known_loc, cluster, 0.85

        # 5. Fuzzy match against aliases and clusters using difflib
        all_candidates = list(self.alias_to_cluster.keys()) + [c.lower() for c in self.known_clusters]
        matches = difflib.get_close_matches(loc_lower, all_candidates, n=1, cutoff=0.55)
        if matches:
            best_match = matches[0]
            cluster = self.alias_to_cluster.get(best_match, best_match.title())
            similarity = difflib.SequenceMatcher(None, loc_lower, best_match).ratio()
            return cluster, cluster, round(similarity, 2)

        # 6. Fallback: return cleaned title-cased location with lower confidence
        return loc_clean.title(), loc_clean.title(), 0.5

    def _find_cluster_for_location(self, location_name: str) -> str:
        """Helper to find the parent cluster for a known location."""
        loc_lower = location_name.lower().strip()
        for cluster, aliases in LOCALITY_CLUSTERS.items():
            if loc_lower in aliases:
                return cluster
            for alias in aliases:
                if alias in loc_lower:
                    return cluster
        return location_name.title()

    def resolve_cuisines(self, raw_cuisines: Optional[Union[List[str], str]]) -> List[str]:
        """
        Normalizes cuisine inputs into a canonical title-cased list.
        """
        if not raw_cuisines:
            return []

        # Split string by comma or treat list
        if isinstance(raw_cuisines, str):
            tokens = [c.strip() for c in raw_cuisines.split(",") if c.strip()]
        elif isinstance(raw_cuisines, (list, tuple, set)):
            tokens = [str(c).strip() for c in raw_cuisines if str(c).strip()]
        else:
            tokens = []

        resolved: List[str] = []
        known_lower_map = {c.lower(): c for c in self.known_cuisines}

        for token in tokens:
            token_clean = re.sub(r"[^\w\s-]", "", token).strip()
            token_lower = token_clean.lower()

            if not token_clean:
                continue

            # Exact match
            if token_lower in known_lower_map:
                resolved.append(known_lower_map[token_lower])
                continue

            # Fuzzy match against known cuisines
            matches = difflib.get_close_matches(token_lower, list(known_lower_map.keys()), n=1, cutoff=0.6)
            if matches:
                resolved.append(known_lower_map[matches[0]])
            else:
                # Retain title-cased custom cuisine
                resolved.append(token_clean.title())

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for c in resolved:
            if c.lower() not in seen:
                seen.add(c.lower())
                deduped.append(c)

        return deduped

    def resolve_budget(self, raw_budget: Optional[Union[int, float, str]]) -> Tuple[int, BudgetTier]:
        """
        Normalizes budget input into an integer amount and assigns the appropriate BudgetTier.
        """
        if raw_budget is None or str(raw_budget).strip() == "":
            budget = DEFAULT_MAX_BUDGET
        elif isinstance(raw_budget, (int, float)):
            budget = int(raw_budget)
        else:
            budget_str = str(raw_budget).strip().lower()

            # Check textual tier mapping (e.g. 'budget', 'mid-range', 'fine_dining')
            if budget_str in BUDGET_TIER_MAP:
                budget = BUDGET_TIER_MAP[budget_str]
            else:
                # Extract numeric digits
                digits = re.sub(r"[^\d]", "", budget_str)
                if digits:
                    budget = int(digits)
                else:
                    budget = DEFAULT_MAX_BUDGET

        # Clamp to bounds
        budget = max(MIN_ALLOWED_BUDGET, min(budget, MAX_ALLOWED_BUDGET))

        # Assign tier
        if budget <= 500:
            tier = BudgetTier.BUDGET
        elif budget <= 1500:
            tier = BudgetTier.MID_RANGE
        else:
            tier = BudgetTier.PREMIUM

        return budget, tier

    def resolve_rating(self, raw_rating: Optional[Union[float, int, str]]) -> float:
        """
        Normalizes minimum rating input to a float clamped between 1.0 and 5.0.
        """
        if raw_rating is None or str(raw_rating).strip() == "":
            return DEFAULT_MIN_RATING

        if isinstance(raw_rating, (float, int)):
            val = float(raw_rating)
        else:
            # Match numeric float from string like '4.0', '4+', '4.5 stars'
            match = re.search(r"(\d+\.?\d*)", str(raw_rating).strip())
            if match:
                try:
                    val = float(match.group(1))
                except ValueError:
                    val = DEFAULT_MIN_RATING
            else:
                val = DEFAULT_MIN_RATING

        # Clamp between 1.0 and 5.0
        return round(max(MIN_ALLOWED_RATING, min(val, MAX_ALLOWED_RATING)), 1)

    def normalize(self, user_input: Union[UserPreferenceInput, Dict[str, Any]]) -> NormalizedPreference:
        """
        End-to-end normalization of a user preference input into a NormalizedPreference object.
        """
        if isinstance(user_input, dict):
            validated_input = UserPreferenceInput(**user_input)
        else:
            validated_input = user_input

        # Resolve location
        res_loc, res_cluster, confidence = self.resolve_location(validated_input.location)

        # Resolve cuisines
        res_cuisines = self.resolve_cuisines(validated_input.cuisines)

        # Resolve budget
        budget, tier = self.resolve_budget(validated_input.max_budget)

        # Resolve rating
        rating = self.resolve_rating(validated_input.min_rating)

        return NormalizedPreference(
            raw_location=validated_input.location,
            resolved_location=res_loc,
            resolved_cluster=res_cluster,
            location_match_confidence=confidence,
            cuisines=res_cuisines,
            max_budget=budget,
            budget_tier=tier,
            min_rating=rating,
            vibe_or_notes=validated_input.vibe_or_notes,
            online_order_only=validated_input.online_order_only,
            book_table_only=validated_input.book_table_only,
            is_relaxed=False,
        )
