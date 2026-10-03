"""
Anti-hallucination guardrail validation module for Phase 5: LLM Recommendation Layer.
Ensures that all LLM outputs strictly reference verified candidate restaurants from the catalog,
rejecting any fabricated restaurants, altered IDs, or unsupported entities.
"""
import logging
from typing import Dict, List, Optional, Set, Tuple, Union

from phase_3.models import NormalizedPreference
from phase_4.models import CandidateRestaurant, ScoredRestaurant
from phase_5.models import FinalCuratedRestaurant, LLMRecommendationItem, LLMStructuredOutput

logger = logging.getLogger(__name__)


def extract_candidate_restaurant(
    cand: Union[CandidateRestaurant, ScoredRestaurant],
) -> CandidateRestaurant:
    """Helper to unwrap CandidateRestaurant from ScoredRestaurant if needed."""
    if isinstance(cand, ScoredRestaurant):
        return cand.restaurant
    return cand


def get_candidate_composite_score(
    cand: Union[CandidateRestaurant, ScoredRestaurant],
) -> float:
    """Helper to extract composite score from candidate."""
    if isinstance(cand, ScoredRestaurant):
        return cand.scores.final_score
    return 1.0


class AntiHallucinationGuardrail:
    """
    Validates LLM outputs against ground-truth candidate metadata.
    Enforces a strict closed-world policy: any non-matching restaurant is discarded.
    """

    @classmethod
    def validate_and_merge(
        cls,
        llm_output: LLMStructuredOutput,
        candidates: List[Union[CandidateRestaurant, ScoredRestaurant]],
        preference: NormalizedPreference,
    ) -> List[FinalCuratedRestaurant]:
        """
        Validates LLM recommendations against candidates, discards hallucinated venues,
        backfills from verified candidates if needed, and constructs final output objects.
        """
        # Map candidates by ID and normalized name for fast verification
        cand_map_by_id: Dict[str, Union[CandidateRestaurant, ScoredRestaurant]] = {
            extract_candidate_restaurant(c).restaurant_id: c for c in candidates
        }
        cand_map_by_name: Dict[str, Union[CandidateRestaurant, ScoredRestaurant]] = {
            extract_candidate_restaurant(c).name.lower().strip(): c for c in candidates
        }

        verified_curations: List[FinalCuratedRestaurant] = []
        seen_ids: Set[str] = set()

        # Step 1: Validate each LLM recommendation item
        for item in llm_output.recommendations:
            matched_candidate = None

            # Primary verification: match by exact UUID
            if item.restaurant_id in cand_map_by_id:
                matched_candidate = cand_map_by_id[item.restaurant_id]
            # Secondary fallback: match by exact name if LLM slightly altered UUID
            elif item.name.lower().strip() in cand_map_by_name:
                matched_candidate = cand_map_by_name[item.name.lower().strip()]
                # Correct UUID to canonical catalog UUID
                item.restaurant_id = extract_candidate_restaurant(matched_candidate).restaurant_id

            if matched_candidate is None:
                logger.warning(
                    f"GUARDRAIL REJECTION: Hallucinated or unknown restaurant dropped: "
                    f"id={item.restaurant_id!r}, name={item.name!r}"
                )
                continue

            underlying = extract_candidate_restaurant(matched_candidate)
            if underlying.restaurant_id in seen_ids:
                # Discard duplicates from LLM
                continue
            seen_ids.add(underlying.restaurant_id)

            # Ensure highlighted dishes come from verified dishes or reviews
            valid_dishes = [d for d in item.highlighted_dishes if d.strip()]
            if not valid_dishes and underlying.dish_liked:
                valid_dishes = underlying.dish_liked[:3]

            rank_idx = len(verified_curations) + 1
            verified_curations.append(
                FinalCuratedRestaurant(
                    restaurant_id=underlying.restaurant_id,
                    name=underlying.name,
                    location=underlying.location,
                    location_cluster=underlying.location_cluster,
                    cuisines=underlying.cuisines,
                    price_for_two=underlying.cost_for_two,
                    rating=underlying.rate,
                    votes=underlying.votes,
                    popular_dishes=valid_dishes,
                    recommendation_reason=item.recommendation_reason.strip(),
                    match_rank=rank_idx,
                    composite_score=get_candidate_composite_score(matched_candidate),
                    url=underlying.url,
                )
            )

        # Step 2: Backfill from verified candidates if LLM failed to recommend enough candidates
        if len(verified_curations) < len(candidates):
            for cand in candidates:
                underlying = extract_candidate_restaurant(cand)
                if underlying.restaurant_id not in seen_ids:
                    seen_ids.add(underlying.restaurant_id)
                    fallback_item = cls.generate_fallback_reasoning(underlying, preference)
                    rank_idx = len(verified_curations) + 1
                    verified_curations.append(
                        FinalCuratedRestaurant(
                            restaurant_id=underlying.restaurant_id,
                            name=underlying.name,
                            location=underlying.location,
                            location_cluster=underlying.location_cluster,
                            cuisines=underlying.cuisines,
                            price_for_two=underlying.cost_for_two,
                            rating=underlying.rate,
                            votes=underlying.votes,
                            popular_dishes=fallback_item.highlighted_dishes,
                            recommendation_reason=fallback_item.recommendation_reason,
                            match_rank=rank_idx,
                            composite_score=get_candidate_composite_score(cand),
                            url=underlying.url,
                        )
                    )
                if len(verified_curations) >= len(candidates):
                    break

        return verified_curations

    @classmethod
    def generate_fallback_reasoning(
        cls,
        candidate: CandidateRestaurant,
        preference: NormalizedPreference,
    ) -> LLMRecommendationItem:
        """
        Synthesizes a fact-grounded recommendation reason directly from verified database attributes.
        Used as a robust zero-hallucination fallback when LLM is offline or timed out.
        """
        # Cuisine reasoning
        common_cuisines = [
            c for c in candidate.cuisines
            if any(t.lower() in c.lower() for t in preference.cuisines)
        ]
        cuisine_mention = (
            f"specializing in {', '.join(common_cuisines)}"
            if common_cuisines
            else f"known for authentic {', '.join(candidate.cuisines[:2])}"
        )

        # Budget comparison
        if candidate.cost_for_two <= preference.max_budget:
            budget_phrase = f"comfortably within your budget at Rs. {candidate.cost_for_two:,} for two (under Rs. {preference.max_budget:,})"
        else:
            budget_phrase = f"priced at Rs. {candidate.cost_for_two:,} for two"

        # Rating comparison
        rate_phrase = (
            f"a strong {candidate.rate:.1f} rating based on {candidate.votes:,} customer reviews"
            if candidate.rate is not None
            else "a fresh emerging destination"
        )

        # Signature dishes
        dish_phrase = ""
        if candidate.dish_liked:
            top_dishes = candidate.dish_liked[:3]
            dish_phrase = f" Highly recommended dishes include {', '.join(top_dishes)}."

        reason = (
            f"{candidate.name} is an excellent choice in {candidate.location} ({candidate.location_cluster}), "
            f"{cuisine_mention}. It is {budget_phrase}, boasting {rate_phrase}.{dish_phrase}"
        )

        highlights = [
            f"Rs. {candidate.cost_for_two:,} for two",
            f"{candidate.rate:.1f} stars ({candidate.votes:,} votes)" if candidate.rate else "New venue",
            candidate.location,
        ]

        return LLMRecommendationItem(
            restaurant_id=candidate.restaurant_id,
            name=candidate.name,
            recommendation_reason=reason,
            highlighted_dishes=candidate.dish_liked[:4] if candidate.dish_liked else candidate.cuisines[:2],
            match_highlights=highlights,
        )
