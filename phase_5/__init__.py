"""
Phase 5: LLM Recommendation Layer with Anti-Hallucination Guardrails.
"""
from phase_5.generator import (
    BaseLLMProvider,
    DeterministicMockProvider,
    GeminiProvider,
    RecommendationGenerator,
    TemplateFallbackProvider,
)
from phase_5.guardrails import AntiHallucinationGuardrail
from phase_5.models import (
    FinalCuratedRestaurant,
    LLMRecommendationItem,
    LLMStructuredOutput,
    Phase5Response,
)
from phase_5.prompt import SYSTEM_INSTRUCTION, build_user_prompt

__all__ = [
    "BaseLLMProvider",
    "GeminiProvider",
    "DeterministicMockProvider",
    "TemplateFallbackProvider",
    "RecommendationGenerator",
    "AntiHallucinationGuardrail",
    "LLMRecommendationItem",
    "LLMStructuredOutput",
    "FinalCuratedRestaurant",
    "Phase5Response",
    "SYSTEM_INSTRUCTION",
    "build_user_prompt",
]
