#!/usr/bin/env python3
"""
CLI entry point for Phase 4: Restaurant Retrieval & Recommendation Engine.

Usage:
    # Test a custom query:
    python phase_4/run_recommendation.py --location Koramangala --cuisines "Italian, Pizza" --budget 1000 --rating 4.0

    # Run demonstration queries:
    python phase_4/run_recommendation.py --demo

    # Test an edge-case query that triggers relaxation:
    python phase_4/run_recommendation.py --location Indiranagar --budget 150 --rating 4.9
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path so phase_4 can be imported directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_4.engine import RecommendationEngine


def print_banner():
    print("=" * 75)
    print("   AI RESTAURANT RECOMMENDER - PHASE 4: RETRIEVAL & RANKING ENGINE")
    print("=" * 75)


def display_results(resp):
    print("\n" + "-" * 75)
    print(f"SEARCH SUMMARY: {resp.query_location} ({resp.query_cluster})")
    print(f"  Target Cuisines:    {resp.query_cuisines or 'Any / All'}")
    print(f"  Target Budget:      Up to Rs. {resp.query_budget:,} for two")
    print(f"  Rating Floor:       {resp.query_rating} / 5.0")
    print(f"  Candidates Found:   {resp.total_candidates_found}")
    print(f"  Execution Latency:  {resp.execution_time_ms} ms")

    if resp.was_relaxed:
        print("\n[NOTE: Query Relaxation Triggered]")
        for note in resp.relaxation_notes:
            print(f"  ! {note}")

    print("\n" + "=" * 75)
    print(f"TOP {len(resp.top_recommendations)} RANKED RECOMMENDATIONS:")
    print("=" * 75)

    for rec in resp.top_recommendations:
        r = rec.restaurant
        s = rec.scores
        rate_str = f"{r.rate:.1f} / 5.0" if r.rate is not None else "New / Unrated"
        
        print(f"\n#{rec.rank}. {r.name.upper()}  [{rate_str} | Rs. {r.cost_for_two:,} for two | {r.votes:,} votes]")
        print(f"    Location:   {r.location} ({r.location_cluster})")
        print(f"    Cuisines:   {', '.join(r.cuisines)}")
        if r.dish_liked:
            print(f"    Popular:    {', '.join(r.dish_liked[:4])}")
        
        # Transparent Score Breakdown
        print(f"    Scores:     Final={s.final_score:.3f} | Cuisine={s.cuisine_score:.2f} | Rating={s.rating_score:.2f} | Price={s.price_score:.2f} | Popularity={s.popularity_score:.2f}")

    print("-" * 75)
    if resp.top_recommendations:
        sample_llm_payload = resp.top_recommendations[0].to_llm_candidate_dict()
        print("\n[Phase 5 Contract Sample Payload for Top Restaurant]:")
        print(json.dumps(sample_llm_payload, indent=2))
    print("=" * 75)


def run_demo():
    print("\nExecuting multi-scenario demonstration across Bangalore neighborhoods...\n")
    engine = RecommendationEngine()

    test_scenarios = [
        {
            "desc": "Scenario 1: High-rated Italian in Koramangala under Rs. 1000",
            "input": {
                "location": "Koramangala",
                "cuisines": "Italian, Pizza",
                "max_budget": 1000,
                "min_rating": 4.0,
            }
        },
        {
            "desc": "Scenario 2: Budget South Indian in Jayanagar under Rs. 400",
            "input": {
                "location": "Jayanagar",
                "cuisines": "South Indian",
                "max_budget": "budget",
                "min_rating": 3.8,
            }
        },
        {
            "desc": "Scenario 3: Overly restrictive query forcing progressive fallback relaxation",
            "input": {
                "location": "Indiranagar",
                "cuisines": "Mexican",
                "max_budget": 150,  # Highly constrained budget
                "min_rating": 4.8,  # Highly constrained rating
            }
        },
        {
            "desc": "Scenario 4: Premium Continental dining in Central Bangalore (Church Street)",
            "input": {
                "location": "Church Street",
                "cuisines": "Continental, European",
                "max_budget": 2500,
                "min_rating": 4.2,
                "book_table_only": True,
            }
        },
    ]

    for sc in test_scenarios:
        print(f"\n>>> {sc['desc']}")
        resp = engine.recommend(sc["input"], top_k=3)
        display_results(resp)

    print("\nDemo suite completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Retrieve and rank restaurants matching user preferences.")
    parser.add_argument("--location", type=str, help="Target location (e.g. Koramangala, Indiranagar).")
    parser.add_argument("--cuisines", type=str, help="Comma-separated cuisines (e.g. Italian, Pizza).")
    parser.add_argument("--budget", type=str, help="Maximum budget for two in Rupees (e.g. 1000).")
    parser.add_argument("--rating", type=str, help="Minimum star rating (e.g. 4.0).")
    parser.add_argument("--vibe", type=str, help="Special occasion or atmosphere notes.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of recommendations to return (default: 5).")
    parser.add_argument("--online-only", action="store_true", help="Online order only.")
    parser.add_argument("--book-table", action="store_true", help="Book table only.")
    parser.add_argument("--demo", action="store_true", help="Run automated demonstration scenarios.")

    args = parser.parse_args()
    print_banner()

    if args.demo:
        run_demo()
        return

    if not args.location:
        print("Please provide a location via --location or use --demo to run test scenarios.")
        print("Example: python phase_4/run_recommendation.py --location Koramangala --cuisines Italian --budget 1000")
        sys.exit(1)

    engine = RecommendationEngine()
    payload = {
        "location": args.location,
        "cuisines": args.cuisines,
        "max_budget": args.budget,
        "min_rating": args.rating,
        "vibe_or_notes": args.vibe,
        "online_order_only": args.online_only,
        "book_table_only": args.book_table,
    }

    resp = engine.recommend(payload, top_k=args.top_k)
    display_results(resp)


if __name__ == "__main__":
    main()
