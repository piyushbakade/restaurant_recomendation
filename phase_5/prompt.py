"""
Prompt engineering and template builder for Phase 5: LLM Recommendation Layer.
Implements strict anti-hallucination guardrails and closed-world XML context enclosure.
"""
import json
from typing import Any, Dict, List, Union

from phase_3.models import NormalizedPreference
from phase_4.models import CandidateRestaurant, ScoredRestaurant

SYSTEM_INSTRUCTION = """You are an expert culinary concierge. You will receive a user's dining preferences and a verified list of candidate restaurants retrieved from the database.

CRITICAL CONSTRAINTS:
1. CLOSED-WORLD RULE: Only recommend from the provided candidate list. Never invent, halluncinate, or recommend external restaurants.
2. ATTRIBUTE INTEGRITY: Do not fabricate or alter any restaurant details (price, rating, location, cuisine, dishes).
3. FACT-GROUNDED REASONING: Base your reasoning exclusively on the provided attributes, popular dishes, and review snippets.
4. CONCISE PERSONALIZATION: Write a vivid, persuasive, and concise explanation (2-3 sentences) for each restaurant, explicitly connecting its strengths, signature dishes, or vibe to the user's requested budget, cuisine, and dining intent.
5. STRICT OUTPUT SYNTAX: Provide your response strictly conforming to the required JSON schema."""


def build_candidates_payload(
    candidates: List[Union[CandidateRestaurant, ScoredRestaurant]],
) -> List[Dict[str, Any]]:
    """
    Serializes CandidateRestaurant or ScoredRestaurant instances into clean JSON-serializable dictionaries.
    """
    serialized = []
    for rank_idx, cand in enumerate(candidates, start=1):
        if isinstance(cand, ScoredRestaurant):
            payload = cand.to_llm_candidate_dict()
        elif hasattr(cand, "to_llm_candidate_dict"):
            payload = cand.to_llm_candidate_dict()
        else:
            # Fallback direct serialization for raw CandidateRestaurant
            payload = {
                "restaurant_id": cand.restaurant_id,
                "name": cand.name,
                "location": cand.location,
                "area_cluster": cand.location_cluster,
                "cuisines": cand.cuisines,
                "cost_for_two": cand.cost_for_two,
                "rating": cand.rate,
                "votes": cand.votes,
                "popular_dishes": cand.dish_liked[:5],
                "review_highlights": cand.sample_reviews[:3],
                "match_rank": rank_idx,
            }
        serialized.append(payload)
    return serialized


def build_user_prompt(
    preference: NormalizedPreference,
    candidates: List[Union[CandidateRestaurant, ScoredRestaurant]],
) -> str:
    """
    Constructs the structured user prompt enclosing candidate metadata inside explicit XML tags.
    """
    candidates_data = build_candidates_payload(candidates)
    candidates_json_str = json.dumps(candidates_data, indent=2)

    cuisines_str = ", ".join(preference.cuisines) if preference.cuisines else "Any / Open to suggestions"
    notes_str = preference.vibe_or_notes if preference.vibe_or_notes else "General dining"
    
    preferences_section = f"""USER PREFERENCES:
- Target Location: {preference.resolved_location} (Area Cluster: {preference.resolved_cluster})
- Desired Cuisines: {cuisines_str}
- Budget for Two: Up to Rs. {preference.max_budget:,}
- Minimum Rating Target: {preference.min_rating} / 5.0
- Special Occasion / Notes: {notes_str}"""

    if preference.online_order_only:
        preferences_section += "\n- Preference: Online Delivery Available"
    if preference.book_table_only:
        preferences_section += "\n- Preference: Table Reservation / Dine-in Available"

    prompt = f"""{preferences_section}

VERIFIED RESTAURANT CANDIDATES:
<verified_restaurants>
{candidates_json_str}
</verified_restaurants>

Please review the verified restaurants above. Select and curate the top choices that best satisfy the user's preferences. For each recommendation:
1. Provide the exact restaurant_id and name matching the candidate data.
2. Write a clear, 2-3 sentence personalized recommendation_reason highlighting why it's a great match.
3. List 1 to 4 highlighted_dishes from the candidate's popular dishes or reviews.
4. List 2 to 3 concise match_highlights (e.g., 'Within budget at Rs. 600 for two', '4.4 rating with 1,500+ votes')."""

    return prompt
