#!/usr/bin/env python3
"""
CLI entry point for Phase 5: LLM Recommendation & Anti-Hallucination Guardrails.

Usage:
    # Run demonstration queries (using high-fidelity mock or Gemini if key set):
    python phase_5/run_generation.py --demo

    # Test custom query:
    python phase_5/run_generation.py --location Koramangala --cuisines "Italian, Pizza" --budget 1000 --rating 4.0 --vibe "romantic candle-light date"

    # Test with live Gemini API key:
    python phase_5/run_generation.py --location Indiranagar --cuisines "Continental" --budget 1500 --api-key YOUR_KEY

    # Output strict standardized JSON contract:
    python phase_5/run_generation.py --location Jayanagar --cuisines "South Indian" --budget 400 --json
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_5.generator import (
    DeterministicMockProvider,
    GeminiProvider,
    RecommendationGenerator,
    TemplateFallbackProvider,
)
from phase_5.models import Phase5Response


def print_banner():
    print("=" * 80)
    print("   AI RESTAURANT RECOMMENDER - PHASE 5: LLM RECOMMENDATION & GUARDRAILS")
    print("=" * 80)


def display_response(resp: Phase5Response, show_json: bool = False):
    if show_json:
        print(json.dumps(resp.model_dump(), indent=2))
        return

    q = resp.query_summary
    print("\n" + "-" * 80)
    print(f"CONCIERGE CURATION SUMMARY: {q.get('location')} ({q.get('cluster')})")
    print(f"  Target Cuisines:   {q.get('cuisines') or 'Open / Any'}")
    print(f"  Target Budget:     Up to Rs. {q.get('max_budget', 0):,} for two")
    print(f"  Rating Floor:      {q.get('min_rating')} / 5.0")
    if q.get("vibe"):
        print(f"  Dining Intent:     \"{q.get('vibe')}\"")
    print(f"  Provider Used:     {resp.provider_used}")
    print(f"  Total Candidates:  {resp.total_candidates_found}")
    print(f"  End-to-End Latency:{resp.meta.get('execution_time_ms', 0)} ms")

    if resp.was_relaxed:
        print("\n[NOTE: Progressive Filter Relaxation Active]")
        for note in resp.relaxation_notes:
            print(f"  ! {note}")

    if resp.meta.get("curation_summary"):
        print(f"\nAI Host Greeting: \"{resp.meta.get('curation_summary')}\"")

    print("\n" + "=" * 80)
    print(f"TOP {len(resp.recommendations)} PERSONALIZED RECOMMENDATIONS (VERIFIED CLOSED-WORLD):")
    print("=" * 80)

    for rec in resp.recommendations:
        rate_str = f"{rec.rating:.1f} / 5.0" if rec.rating is not None else "New / Unrated"
        print(f"\n#{rec.match_rank}. {rec.name.upper()}  [{rate_str} | Rs. {rec.price_for_two:,} for two | {rec.votes:,} votes]")
        print(f"    Location:   {rec.location} ({rec.location_cluster})")
        print(f"    Cuisines:   {', '.join(rec.cuisines)}")
        if rec.popular_dishes:
            print(f"    Signatures: {', '.join(rec.popular_dishes[:4])}")
        print(f"    Score:      {rec.composite_score:.3f} | [Anti-Hallucination Verified]")
        print(f"\n    [AI Personalized Reason]:")
        print(f"    \"{rec.recommendation_reason}\"")

    print("\n" + "-" * 80)
    print("[Standardized JSON Contract Snippet (First Recommendation)]:")
    if resp.recommendations:
        sample_card = resp.recommendations[0].model_dump()
        print(json.dumps(sample_card, indent=2))
    print("=" * 80)


def run_demo():
    print("\nExecuting multi-scenario Phase 5 demonstration...\n")
    generator = RecommendationGenerator(use_mock=True)

    demo_scenarios = [
        {
            "desc": "Scenario 1: Romantic Italian date night in Koramangala under Rs. 1000",
            "query": {
                "location": "Koramangala",
                "cuisines": "Italian, Pizza",
                "max_budget": 1000,
                "min_rating": 4.0,
                "vibe_or_notes": "romantic anniversary dinner with wine and pasta",
            },
        },
        {
            "desc": "Scenario 2: Authentic quick South Indian breakfast in Jayanagar under Rs. 400",
            "query": {
                "location": "Jayanagar",
                "cuisines": "South Indian",
                "max_budget": "budget",
                "min_rating": 4.0,
                "vibe_or_notes": "crispy dosa and filter coffee for morning breakfast",
            },
        },
        {
            "desc": "Scenario 3: Relaxed query with strict Mexican constraint in Indiranagar",
            "query": {
                "location": "Indiranagar",
                "cuisines": "Mexican",
                "max_budget": 150,
                "min_rating": 4.8,
                "vibe_or_notes": "fast casual tacos with friends",
            },
        },
    ]

    for sc in demo_scenarios:
        print(f"\n>>> {sc['desc']}")
        resp = generator.recommend_from_query(sc["query"], top_k=3)
        display_response(resp)

    print("\nPhase 5 Demo suite completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Generate personalized AI restaurant recommendations.")
    parser.add_argument("--location", type=str, help="Target location (e.g. Koramangala, Indiranagar).")
    parser.add_argument("--cuisines", type=str, help="Comma-separated cuisines (e.g. Italian, South Indian).")
    parser.add_argument("--budget", type=str, help="Maximum budget for two in Rupees (e.g. 1000).")
    parser.add_argument("--rating", type=str, help="Minimum star rating (e.g. 4.0).")
    parser.add_argument("--vibe", type=str, help="Dining intent, occasion, or atmosphere notes.")
    parser.add_argument("--provider", choices=["gemini", "mock", "template"], default=None, help="LLM Provider.")
    parser.add_argument("--api-key", type=str, help="Gemini API Key.")
    parser.add_argument("--top-k", type=int, default=3, help="Number of recommendations to curate (default: 3).")
    parser.add_argument("--json", action="store_true", help="Output raw standardized JSON response.")
    parser.add_argument("--demo", action="store_true", help="Run automated demonstration queries.")

    args = parser.parse_args()
    if not args.json:
        print_banner()

    if args.demo:
        run_demo()
        return

    if not args.location:
        print("Please provide a location via --location or use --demo to run demonstration scenarios.")
        print("Example: python phase_5/run_generation.py --location Koramangala --cuisines Italian --budget 1000")
        sys.exit(1)

    # Initialize provider
    if args.provider == "mock":
        provider = DeterministicMockProvider()
    elif args.provider == "template":
        provider = TemplateFallbackProvider()
    elif args.provider == "gemini":
        provider = GeminiProvider(api_key=args.api_key)
    else:
        provider = None  # Automatic resolution

    generator = RecommendationGenerator(provider=provider, api_key=args.api_key)

    query = {
        "location": args.location,
        "cuisines": args.cuisines,
        "max_budget": args.budget,
        "min_rating": args.rating,
        "vibe_or_notes": args.vibe,
    }

    resp = generator.recommend_from_query(query, top_k=args.top_k)
    display_response(resp, show_json=args.json)


if __name__ == "__main__":
    main()
