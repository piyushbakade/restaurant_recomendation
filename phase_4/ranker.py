"""
Heuristic ranking module for Phase 4.
Scores and ranks candidate restaurants using a multi-attribute composite formula
combining cuisine relevance, rating, price proximity, and popularity.
"""
import math
from typing import List, Optional

from phase_3.models import NormalizedPreference
from phase_4.config import (
    DEFAULT_NEUTRAL_RATING,
    DEFAULT_TOP_K_RECOMMENDATIONS,
    GLOBAL_MAX_VOTES,
    WEIGHT_CUISINE,
    WEIGHT_POPULARITY,
    WEIGHT_PRICE,
    WEIGHT_RATING,
)
from phase_4.models import CandidateRestaurant, ScoreBreakdown, ScoredRestaurant


class HeuristicRankingEngine:
    """
    Ranks candidate restaurants using deterministic multi-factor scoring.
    """

    def __init__(
        self,
        weight_cuisine: float = WEIGHT_CUISINE,
        weight_rating: float = WEIGHT_RATING,
        weight_price: float = WEIGHT_PRICE,
        weight_pop: float = WEIGHT_POPULARITY,
    ):
        self.w_cuisine = weight_cuisine
        self.w_rating = weight_rating
        self.w_price = weight_price
        self.w_pop = weight_pop

        # Validate weight normalization
        total_w = self.w_cuisine + self.w_rating + self.w_price + self.w_pop
        if not math.isclose(total_w, 1.0, rel_tol=1e-3):
            # Normalize weights if sum != 1.0
            self.w_cuisine /= total_w
            self.w_rating /= total_w
            self.w_price /= total_w
            self.w_pop /= total_w

    def score_cuisine(self, restaurant_cuisines: List[str], target_cuisines: List[str]) -> float:
        """
        Calculates cuisine match score using Jaccard similarity.
        Returns 1.0 if user did not specify any cuisine preference.
        """
        if not target_cuisines:
            return 1.0  # Open preference matches any cuisine

        rest_set = {c.lower().strip() for c in restaurant_cuisines if c.strip()}
        target_set = {c.lower().strip() for c in target_cuisines if c.strip()}

        if not rest_set or not target_set:
            return 0.2

        intersection = rest_set.intersection(target_set)
        union = rest_set.union(target_set)
        jaccard = len(intersection) / len(union) if union else 0.0

        # Check for substring matches (e.g., 'pizza' in 'italian, pizza')
        has_partial = any(
            any(t in r or r in t for r in rest_set) for t in target_set
        )

        if intersection:
            score = 0.5 + (0.5 * jaccard)
        elif has_partial:
            score = 0.4
        else:
            score = 0.1

        return round(min(1.0, max(0.0, score)), 3)

    def score_rating(self, rate: Optional[float], is_new: bool = False) -> float:
        """
        Normalizes rating to 0.0 - 1.0 scale.
        Unrated / new restaurants receive a neutral benchmark score.
        """
        if rate is not None and not math.isnan(rate):
            normalized = rate / 5.0
        else:
            normalized = DEFAULT_NEUTRAL_RATING / 5.0

        return round(min(1.0, max(0.0, normalized)), 3)

    def score_price(self, cost_for_two: int, target_budget: int) -> float:
        """
        Scores price proximity. Venues close to the target budget score highest.
        """
        if target_budget <= 0:
            return 0.5

        deviation = abs(cost_for_two - target_budget)
        proximity = 1.0 - (deviation / target_budget)
        return round(min(1.0, max(0.0, proximity)), 3)

    def score_popularity(self, votes: int, max_votes: int = GLOBAL_MAX_VOTES) -> float:
        """
        Computes log-damped popularity score based on customer vote count.
        """
        safe_votes = max(0, votes)
        log_v = math.log(1 + safe_votes)
        log_max = math.log(1 + max(max_votes, safe_votes))
        score = log_v / log_max if log_max > 0 else 0.0
        return round(min(1.0, max(0.0, score)), 3)

    def calculate_score(
        self,
        candidate: CandidateRestaurant,
        preference: NormalizedPreference,
    ) -> ScoreBreakdown:
        """
        Computes the complete ScoreBreakdown for a single candidate restaurant.
        """
        s_cuisine = self.score_cuisine(candidate.cuisines, preference.cuisines)
        s_rating = self.score_rating(candidate.rate, candidate.is_new)
        s_price = self.score_price(candidate.cost_for_two, preference.max_budget)
        s_pop = self.score_popularity(candidate.votes)

        final = (
            (self.w_cuisine * s_cuisine)
            + (self.w_rating * s_rating)
            + (self.w_price * s_price)
            + (self.w_pop * s_pop)
        )

        return ScoreBreakdown(
            cuisine_score=s_cuisine,
            rating_score=s_rating,
            price_score=s_price,
            popularity_score=s_pop,
            final_score=round(min(1.0, max(0.0, final)), 4),
        )

    def rank(
        self,
        candidates: List[CandidateRestaurant],
        preference: NormalizedPreference,
        top_k: int = DEFAULT_TOP_K_RECOMMENDATIONS,
    ) -> List[ScoredRestaurant]:
        """
        Ranks candidate restaurants, sorts by final score descending, and returns top K.
        """
        scored_list: List[ScoredRestaurant] = []

        for candidate in candidates:
            breakdown = self.calculate_score(candidate, preference)
            scored_list.append(
                ScoredRestaurant(
                    restaurant=candidate,
                    scores=breakdown,
                    rank=1,  # Temporary placeholder, assigned after sorting
                )
            )

        # Sort descending by final_score, breaking ties with rating and votes
        scored_list.sort(
            key=lambda x: (
                x.scores.final_score,
                x.restaurant.rate or 0.0,
                x.restaurant.votes,
            ),
            reverse=True,
        )

        # Slicing and assigning 1-indexed ranks
        top_recommendations = scored_list[:top_k]
        for idx, item in enumerate(top_recommendations, start=1):
            item.rank = idx

        return top_recommendations
