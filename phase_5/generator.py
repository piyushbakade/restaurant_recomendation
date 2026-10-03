"""
LLM Recommendation Generator for Phase 5.
Supports Google Gemini (via google-genai SDK and REST API), deterministic mock provider,
and template fallback with anti-hallucination guardrail validation.
"""
import abc
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

import requests
from pydantic import ValidationError

from phase_3.models import NormalizedPreference
from phase_4.engine import RecommendationEngine
from phase_4.models import CandidateRestaurant, RecommendationResponse, ScoredRestaurant
from phase_5.config import (
    API_KEY_ENV_VARS,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_TEMPERATURE,
    ENABLE_ANTI_HALLUCINATION_GUARDRAILS,
    ENABLE_TEMPLATE_FALLBACK_ON_ERROR,
    MAX_CANDIDATES_FOR_LLM,
    REQUEST_TIMEOUT_SECONDS,
)
from phase_5.guardrails import AntiHallucinationGuardrail, extract_candidate_restaurant
from phase_5.models import FinalCuratedRestaurant, LLMRecommendationItem, LLMStructuredOutput, Phase5Response
from phase_5.prompt import SYSTEM_INSTRUCTION, build_user_prompt

logger = logging.getLogger(__name__)


class BaseLLMProvider(abc.ABC):
    """Abstract base class for recommendation reasoning providers."""

    @abc.abstractmethod
    def generate(
        self,
        preference: NormalizedPreference,
        candidates: List[Union[CandidateRestaurant, ScoredRestaurant]],
    ) -> LLMStructuredOutput:
        """Emits structured recommendation reasoning matching LLMStructuredOutput schema."""
        pass


class GeminiProvider(BaseLLMProvider):
    """
    Calls Google Gemini using the official google-genai SDK or direct REST API
    with strict JSON Schema enforcement.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_GEMINI_MODEL):
        self.api_key = api_key or self._resolve_api_key()
        self.model = model
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize google-genai Client: {e}. Falling back to REST.")

    @staticmethod
    def _resolve_api_key() -> Optional[str]:
        for var in API_KEY_ENV_VARS:
            val = os.environ.get(var)
            if val:
                return val.strip()
        return None

    def has_credentials(self) -> bool:
        return bool(self.api_key)

    def generate(
        self,
        preference: NormalizedPreference,
        candidates: List[Union[CandidateRestaurant, ScoredRestaurant]],
    ) -> LLMStructuredOutput:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY / GOOGLE_API_KEY is not set.")

        prompt = build_user_prompt(preference, candidates)

        # 1. Try google-genai SDK if available
        if self._client is not None:
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        "system_instruction": SYSTEM_INSTRUCTION,
                        "temperature": DEFAULT_TEMPERATURE,
                        "response_mime_type": "application/json",
                        "response_schema": LLMStructuredOutput,
                    },
                )
                if response.text:
                    return LLMStructuredOutput.model_validate_json(response.text)
            except Exception as e:
                logger.warning(f"google-genai SDK call failed: {e}. Attempting REST fallback...")

        # 2. Direct HTTP REST endpoint fallback
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": DEFAULT_TEMPERATURE,
                "response_mime_type": "application/json",
                "response_schema": LLMStructuredOutput.model_json_schema(),
            },
        }

        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()

        candidates_resp = data.get("candidates", [])
        if not candidates_resp:
            raise RuntimeError(f"No response candidates returned from Gemini API: {data}")

        parts = candidates_resp[0].get("content", {}).get("parts", [])
        raw_text = parts[0].get("text", "") if parts else ""
        return LLMStructuredOutput.model_validate_json(raw_text)


class DeterministicMockProvider(BaseLLMProvider):
    """
    Deterministic mock provider generating high-fidelity, grounded personalized recommendations
    based on candidate metadata and user dining notes. Ideal for tests and offline usage.
    """

    def generate(
        self,
        preference: NormalizedPreference,
        candidates: List[Union[CandidateRestaurant, ScoredRestaurant]],
    ) -> LLMStructuredOutput:
        recommendations: List[LLMRecommendationItem] = []

        vibe = preference.vibe_or_notes.strip() if preference.vibe_or_notes else ""

        for cand in candidates:
            c = extract_candidate_restaurant(cand)
            common_cuisines = [
                x for x in c.cuisines
                if any(t.lower() in x.lower() for t in preference.cuisines)
            ]
            primary_cuisine = common_cuisines[0] if common_cuisines else (c.cuisines[0] if c.cuisines else "Dining")
            
            # Sentence 1: Venue match & cuisine
            s1 = (
                f"{c.name} in {c.location} is an outstanding choice for {primary_cuisine.lower()} lovers, "
                f"aligning with your search in {c.location_cluster}."
            )

            # Sentence 2: Budget & Rating
            budget_str = f"priced comfortably at Rs. {c.cost_for_two:,} for two"
            if c.cost_for_two <= preference.max_budget:
                budget_str += f" (within your Rs. {preference.max_budget:,} budget)"
            rate_str = f"impressive {c.rate:.1f} rating ({c.votes:,} votes)" if c.rate else "promising profile"
            s2 = f"It boasts an {rate_str} and is {budget_str}."

            # Sentence 3: Vibe or signature dish connection
            if vibe:
                s3 = (
                    f"Its warm ambiance and popular dishes like {', '.join(c.dish_liked[:2]) if c.dish_liked else primary_cuisine} "
                    f"make it ideally suited for your {vibe.lower()}."
                )
            elif c.dish_liked:
                s3 = f"Diners frequently praise their signature {', '.join(c.dish_liked[:3])}."
            else:
                s3 = "A highly dependable spot with consistent food quality and prompt service."

            reason = f"{s1} {s2} {s3}"

            highlights = [
                f"Rs. {c.cost_for_two:,} for two",
                f"{c.rate:.1f} stars" if c.rate else "Unrated",
                c.location,
            ]

            recommendations.append(
                LLMRecommendationItem(
                    restaurant_id=c.restaurant_id,
                    name=c.name,
                    recommendation_reason=reason,
                    highlighted_dishes=c.dish_liked[:3] if c.dish_liked else c.cuisines[:2],
                    match_highlights=highlights,
                )
            )

        summary = (
            f"Here are the top curated {', '.join(preference.cuisines) if preference.cuisines else 'dining'} "
            f"recommendations for {preference.resolved_location} matching your budget."
        )

        return LLMStructuredOutput(
            recommendations=recommendations,
            curation_summary=summary,
        )


class TemplateFallbackProvider(BaseLLMProvider):
    """Template-based synthesizer used during unexpected API errors or missing credentials."""

    def generate(
        self,
        preference: NormalizedPreference,
        candidates: List[Union[CandidateRestaurant, ScoredRestaurant]],
    ) -> LLMStructuredOutput:
        items = [
            AntiHallucinationGuardrail.generate_fallback_reasoning(
                extract_candidate_restaurant(c), preference
            )
            for c in candidates
        ]
        return LLMStructuredOutput(
            recommendations=items,
            curation_summary="Generated verified recommendations from catalog attributes.",
        )


class RecommendationGenerator:
    """
    Coordinates end-to-end Phase 5 recommendation generation:
    1. Accepts user preferences and candidate restaurants (from Phase 4 or raw dict).
    2. Invokes appropriate LLM provider (Gemini, Mock, or Template).
    3. Runs anti-hallucination guardrail validation.
    4. Serializes into the standardized Phase 5/Phase 7 response schema.
    """

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        api_key: Optional[str] = None,
        use_mock: bool = False,
    ):
        if provider:
            self.provider = provider
            self.provider_name = provider.__class__.__name__
        elif use_mock:
            self.provider = DeterministicMockProvider()
            self.provider_name = "DeterministicMockProvider"
        else:
            gemini = GeminiProvider(api_key=api_key)
            if gemini.has_credentials():
                self.provider = gemini
                self.provider_name = "GeminiProvider"
            else:
                logger.info(
                    "No GEMINI_API_KEY found; defaulting to DeterministicMockProvider for offline operation."
                )
                self.provider = DeterministicMockProvider()
                self.provider_name = "DeterministicMockProvider"

    def generate(
        self,
        preference: NormalizedPreference,
        candidates: List[Union[CandidateRestaurant, ScoredRestaurant]],
        was_relaxed: bool = False,
        relaxation_notes: Optional[List[str]] = None,
        total_candidates_found: Optional[int] = None,
    ) -> Phase5Response:
        """
        Generates personalized recommendations for given candidates and normalized preference.
        """
        start_time = time.perf_counter()
        relaxation_notes = relaxation_notes or []
        total_found = total_candidates_found if total_candidates_found is not None else len(candidates)

        # Slice to max allowed candidates for LLM prompt context window
        llm_candidate_pool = candidates[:MAX_CANDIDATES_FOR_LLM]

        if not llm_candidate_pool:
            return Phase5Response(
                status="success",
                query_summary={
                    "location": preference.resolved_location,
                    "cluster": preference.resolved_cluster,
                    "cuisines": preference.cuisines,
                    "max_budget": preference.max_budget,
                    "min_rating": preference.min_rating,
                    "vibe": preference.vibe_or_notes,
                },
                total_candidates_found=0,
                recommendations=[],
                was_relaxed=was_relaxed,
                relaxation_notes=relaxation_notes,
                provider_used=self.provider_name,
                meta={"execution_time_ms": round((time.perf_counter() - start_time) * 1000, 2)},
            )

        # Generate LLM reasoning with error fallback
        actual_provider_used = self.provider_name
        try:
            llm_output = self.provider.generate(preference, llm_candidate_pool)
        except Exception as e:
            logger.error(f"LLM Provider {self.provider_name} failed: {e}.")
            if ENABLE_TEMPLATE_FALLBACK_ON_ERROR:
                logger.info("Engaging TemplateFallbackProvider as safety net.")
                fallback = TemplateFallbackProvider()
                llm_output = fallback.generate(preference, llm_candidate_pool)
                actual_provider_used = "TemplateFallbackProvider"
            else:
                raise e

        # Anti-hallucination guardrail validation
        if ENABLE_ANTI_HALLUCINATION_GUARDRAILS:
            curated_restaurants = AntiHallucinationGuardrail.validate_and_merge(
                llm_output=llm_output,
                candidates=candidates,
                preference=preference,
            )
        else:
            # Fallback merge without strict validation
            curated_restaurants = [
                FinalCuratedRestaurant(
                    restaurant_id=item.restaurant_id,
                    name=item.name,
                    location=preference.resolved_location,
                    location_cluster=preference.resolved_cluster,
                    cuisines=preference.cuisines,
                    price_for_two=preference.max_budget,
                    rating=preference.min_rating,
                    votes=0,
                    popular_dishes=item.highlighted_dishes,
                    recommendation_reason=item.recommendation_reason,
                    match_rank=idx,
                    composite_score=1.0,
                )
                for idx, item in enumerate(llm_output.recommendations, start=1)
            ]

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return Phase5Response(
            status="success",
            query_summary={
                "location": preference.resolved_location,
                "cluster": preference.resolved_cluster,
                "cuisines": preference.cuisines,
                "max_budget": preference.max_budget,
                "min_rating": preference.min_rating,
                "vibe": preference.vibe_or_notes,
            },
            total_candidates_found=total_found,
            recommendations=curated_restaurants,
            was_relaxed=was_relaxed,
            relaxation_notes=relaxation_notes,
            provider_used=actual_provider_used,
            meta={
                "execution_time_ms": elapsed_ms,
                "curation_summary": llm_output.curation_summary,
            },
        )

    def recommend_from_query(
        self,
        query: Union[Dict[str, Any], NormalizedPreference],
        recommendation_engine: Optional[RecommendationEngine] = None,
        top_k: int = 5,
    ) -> Phase5Response:
        """
        Convenience end-to-end entrypoint: Takes raw search dict -> Phase 3 Normalization ->
        Phase 4 Candidate Retrieval & Ranking -> Phase 5 LLM Generation & Anti-Hallucination.
        """
        engine = recommendation_engine or RecommendationEngine()
        phase4_resp: RecommendationResponse = engine.recommend(query, top_k=top_k)

        # Retrieve normalized preference from engine
        if isinstance(query, NormalizedPreference):
            pref = query
        else:
            pref = engine.normalizer.normalize(query)

        return self.generate(
            preference=pref,
            candidates=phase4_resp.top_recommendations,
            was_relaxed=phase4_resp.was_relaxed,
            relaxation_notes=phase4_resp.relaxation_notes,
            total_candidates_found=phase4_resp.total_candidates_found,
        )
