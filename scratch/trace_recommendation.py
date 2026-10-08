import json
import logging
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from phase_3.models import UserPreferenceInput
from phase_3.normalizer import PreferenceNormalizer
from phase_4.engine import RecommendationEngine
from phase_4.retriever import CandidateRetriever
from phase_4.ranker import HeuristicRankingEngine
from phase_5.generator import RecommendationGenerator, GeminiProvider
from phase_5.prompt import SYSTEM_INSTRUCTION, build_user_prompt
from phase_7.formatter import ResponseFormatter

def run_trace():
    print("=" * 80)
    print("AI RESTAURANT RECOMMENDATION: STEP-BY-STEP EXECUTION TRACE & LOGS")
    print("=" * 80)

    # ---------------------------------------------------------
    # STEP 1: USER INPUT & NORMALIZATION (PHASE 3)
    # ---------------------------------------------------------
    print("\n[STEP 1] USER INPUT RECEIVED & PREFERENCE NORMALIZATION (PHASE 3)")
    raw_input = {
        "location": "koramangla", # intentional typo to demonstrate fuzzy matching
        "cuisines": ["Italian", "Pizza"],
        "max_budget": 1000,
        "min_rating": 4.0,
        "vibe_or_notes": "romantic outdoor dinner with authentic pasta",
        "top_k": 5
    }
    print(f"--> Raw User Input Received from UI:")
    print(json.dumps(raw_input, indent=4))

    normalizer = PreferenceNormalizer()
    validated_input = UserPreferenceInput(**raw_input)
    normalized = normalizer.normalize(validated_input)
    
    print("\n--> Output of Phase 3 Normalization:")
    print(f"    - Original Location: '{raw_input['location']}' -> Fuzzy Match: '{normalized.resolved_location}'")
    print(f"    - Macro-Cluster Mapped: '{normalized.resolved_cluster}'")
    print(f"    - Cuisines Cleaned & Standardized: {normalized.cuisines}")
    print(f"    - Budget Clamped & Validated: Rs. {normalized.max_budget:,} (Tier: {normalized.budget_tier.value})")
    print(f"    - Minimum Rating Floor: {normalized.min_rating} / 5.0")
    print(f"    - Occasion / Vibe Notes: '{normalized.vibe_or_notes}'")

    # ---------------------------------------------------------
    # STEP 2: DATABASE RETRIEVAL (PHASE 4A)
    # ---------------------------------------------------------
    print("\n" + "=" * 80)
    print("[STEP 2] FAST DATABASE RETRIEVAL & HARD/SOFT CONSTRAINT FILTERING (PHASE 4A)")
    retriever = CandidateRetriever()
    t0 = time.perf_counter()
    candidates, was_relaxed, relaxation_notes = retriever.retrieve(normalized, pool_limit=25)
    t_retrieval = (time.perf_counter() - t0) * 1000

    print(f"--> Retrieval completed in: {t_retrieval:.2f} ms")
    print(f"--> Total Candidates Retrieved: {len(candidates)}")
    print(f"--> Filter Relaxation Applied: {was_relaxed}")
    if relaxation_notes:
        print(f"--> Relaxation Notes: {relaxation_notes}")
    
    print("\n--> Sample Candidate Pool (Top 4 retrieved from DB):")
    for i, c in enumerate(candidates[:4], 1):
        print(f"    [{i}] {c.name}")
        print(f"        Location: {c.location} | Cost for Two: Rs. {c.cost_for_two}")
        print(f"        Rating: {c.rate} ★ ({c.votes} votes) | Cuisines: {', '.join(c.cuisines[:3])}")
        print(f"        Signature Dishes: {', '.join(c.dish_liked[:4]) if c.dish_liked else 'N/A'}")

    # ---------------------------------------------------------
    # STEP 3: HEURISTIC RANKING (PHASE 4B)
    # ---------------------------------------------------------
    print("\n" + "=" * 80)
    print("[STEP 3] MULTI-FACTOR HEURISTIC SCORING & DETERMINISTIC RANKING (PHASE 4B)")
    print("--> Mathematical Scoring Formula:")
    print("    Score = (0.35 * Cuisine_Jaccard) + (0.30 * Rating_Score) + (0.20 * Price_Score) + (0.15 * Popularity_Score)")
    
    ranker = HeuristicRankingEngine()
    scored = ranker.rank(candidates=candidates, preference=normalized, top_k=5)
    
    print(f"\n--> Top {len(scored)} Ranked Restaurants:")
    for r in scored:
        b = r.scores
        rest = r.restaurant
        print(f"    Rank #{r.rank}: {rest.name} -> Composite Match Score: {b.final_score:.4f}")
        print(f"        * Cuisine Overlap (35% wt): {b.cuisine_score:.2f} -> contribution: {0.35 * b.cuisine_score:.4f}")
        print(f"        * Rating Quality  (30% wt): {b.rating_score:.2f} -> contribution: {0.30 * b.rating_score:.4f}")
        print(f"        * Price Proximity (20% wt): {b.price_score:.2f} -> contribution: {0.20 * b.price_score:.4f}")
        print(f"        * Popularity/Log  (15% wt): {b.popularity_score:.2f} -> contribution: {0.15 * b.popularity_score:.4f}")

    # ---------------------------------------------------------
    # STEP 4: PROMPT ENGINEERING & GUARDRAILS (PHASE 5)
    # ---------------------------------------------------------
    print("\n" + "=" * 80)
    print("[STEP 4] GROUNDED LLM PROMPT SYNTHESIS & ANTI-HALLUCINATION GUARDRAILS (PHASE 5)")
    prompt = build_user_prompt(normalized, scored[:3])
    print("--> Grounded Prompt passed to LLM (Showing Structure & XML Tags):")
    prompt_lines = prompt.splitlines()
    for line in prompt_lines[:15]:
        print(f"    {line}")
    print("    ...")
    for line in prompt_lines[-10:]:
        print(f"    {line}")

    # ---------------------------------------------------------
    # STEP 5: LLM INFERENCE (GEMINI CALL)
    # ---------------------------------------------------------
    print("\n" + "=" * 80)
    print("[STEP 5] EXECUTING LLM REASONING LAYER (PHASE 5)")
    generator = RecommendationGenerator()
    print(f"--> Active Model Provider: {generator.provider_name}")
    
    t1 = time.perf_counter()
    phase5_res = generator.generate(preference=normalized, candidates=scored[:3])
    t_llm = (time.perf_counter() - t1) * 1000

    print(f"--> LLM Rationale Generation Latency: {t_llm:.2f} ms")
    print(f"--> AI Recommendations Generated: {len(phase5_res.recommendations)}")
    
    for i, rec in enumerate(phase5_res.recommendations, 1):
        print(f"\n    [Match #{i}] {rec.name}")
        print(f"    Location: {rec.location} | Rating: {rec.rating} ★ | Cost: Rs. {rec.price_for_two}")
        print(f"    Popular Dishes: {', '.join(rec.popular_dishes[:4])}")
        print(f"    AI Personalized Rationale:")
        print(f"    \"{rec.recommendation_reason}\"")

    # ---------------------------------------------------------
    # STEP 6: CONTRACT FORMATTING & API RESPONSE (PHASE 7)
    # ---------------------------------------------------------
    print("\n" + "=" * 80)
    print("[STEP 6] STANDARDIZED RESPONSE CONTRACT & METADATA ENVELOPE (PHASE 7)")
    formatted = ResponseFormatter.from_phase5_response(phase5_res, provider_name=generator.provider_name)
    envelope = formatted.model_dump()
    
    print("--> Clean Response Contract Envelope delivered to Frontend:")
    print(f"    Status: {envelope['status']}")
    print(f"    Total Found: {envelope['total_candidates_found']}")
    print(f"    Query Summary: {json.dumps(envelope['query_summary'])}")
    print(f"    Execution Latency: {envelope['meta']['execution_time_ms']} ms")
    print(f"    Provider: {envelope['meta']['provider']}")
    print("=" * 80)
    print("TRACE COMPLETED SUCCESSFULLY.")
    print("=" * 80)

if __name__ == "__main__":
    run_trace()
