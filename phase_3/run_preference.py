#!/usr/bin/env python3
"""
CLI entry point for Phase 3: User Preference Processing.

Usage:
    # Test a custom query:
    python phase_3/run_preference.py --location koramangla --cuisines "Italian, Pizza" --budget 1000 --rating 4.0

    # Run automated demo queries:
    python phase_3/run_preference.py --demo

    # Interactive prompt mode:
    python phase_3/run_preference.py
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path so phase_3 can be imported directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_3.models import UserPreferenceInput
from phase_3.normalizer import PreferenceNormalizer


def print_banner():
    print("=" * 70)
    print("   AI RESTAURANT RECOMMENDER - PHASE 3: USER PREFERENCE PROCESSING")
    print("=" * 70)


def display_normalized_result(norm_pref):
    print("\n" + "-" * 70)
    print("NORMALIZATION RESULT:")
    print("-" * 70)
    print(f"  Raw Location:        '{norm_pref.raw_location}'")
    print(f"  Resolved Location:   '{norm_pref.resolved_location}'")
    print(f"  Resolved Cluster:    '{norm_pref.resolved_cluster}'")
    print(f"  Match Confidence:    {norm_pref.location_match_confidence * 100:.0f}%")
    print(f"  Target Cuisines:     {norm_pref.cuisines or 'Any / All'}")
    print(f"  Budget Limit:        Rs. {norm_pref.max_budget:,} for two ({norm_pref.budget_tier.value})")
    print(f"  Rating Floor:        {norm_pref.min_rating} / 5.0")
    if norm_pref.vibe_or_notes:
        print(f"  Vibe / Notes:        '{norm_pref.vibe_or_notes}'")
    print(f"  Online Order Only:   {norm_pref.online_order_only}")
    print(f"  Book Table Only:     {norm_pref.book_table_only}")

    print("\n[Phase 4 Contract] Generated SQL Filters:")
    print(json.dumps(norm_pref.to_sql_filters(), indent=4))

    print("\n[Phase 5 Contract] Generated LLM Prompt Context:")
    for line in norm_pref.to_llm_context().split("\n"):
        print(f"  | {line}")
    print("-" * 70)


def run_demo():
    print("\nRunning automated demonstration suite across diverse user queries...\n")
    normalizer = PreferenceNormalizer()

    sample_queries = [
        {
            "desc": "Query 1: Typo in location and cuisines ('koramangla', 'pizzza')",
            "input": {
                "location": "koramangla",
                "cuisines": "pizzza, itallian",
                "max_budget": "Rs. 1,000",
                "min_rating": "4.0",
                "vibe_or_notes": "romantic candle light dinner",
            }
        },
        {
            "desc": "Query 2: Textual budget tier ('cheap') and alias locality ('HSR')",
            "input": {
                "location": "HSR",
                "cuisines": "South Indian, Fast Food",
                "max_budget": "cheap",
                "min_rating": "3.8",
                "online_order_only": True,
            }
        },
        {
            "desc": "Query 3: Premium fine-dining in Central Bangalore ('church street')",
            "input": {
                "location": "church street",
                "cuisines": "Continental, European",
                "max_budget": "fine_dining",
                "min_rating": "4.5",
                "book_table_only": True,
                "vibe_or_notes": "business meeting lunch with wine",
            }
        },
        {
            "desc": "Query 4: Micro-locality ('Koramangala 5th Block') with defaults",
            "input": {
                "location": "Koramangala 5th Block",
            }
        },
    ]

    for item in sample_queries:
        print(f"\n>>> {item['desc']}")
        print(f"Input: {json.dumps(item['input'], indent=2)}")
        norm = normalizer.normalize(item["input"])
        display_normalized_result(norm)

    print("\nDemo suite completed successfully.")


def interactive_mode():
    print("\n[Interactive Mode] Enter your restaurant preferences below:")
    try:
        location = input("  Location / Neighborhood (e.g. Koramangala, Indiranagar): ").strip()
        if not location:
            print("Location cannot be empty.")
            return

        cuisines = input("  Cuisines (optional, comma-separated, e.g. Italian, North Indian): ").strip()
        budget = input("  Budget for two (optional, e.g. 1000, 'mid-range', default: 1000): ").strip()
        rating = input("  Minimum Rating (optional, e.g. 4.0, default: 3.5): ").strip()
        vibe = input("  Special Vibe / Occasion (optional, e.g. cozy date night): ").strip()

        raw_input = UserPreferenceInput(
            location=location,
            cuisines=cuisines if cuisines else None,
            max_budget=budget if budget else None,
            min_rating=rating if rating else None,
            vibe_or_notes=vibe if vibe else None,
        )

        normalizer = PreferenceNormalizer()
        norm = normalizer.normalize(raw_input)
        display_normalized_result(norm)

    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")


def main():
    parser = argparse.ArgumentParser(description="Process and normalize user restaurant preferences.")
    parser.add_argument("--location", type=str, help="Target location / place (e.g., 'Koramangala', 'Indiranagar').")
    parser.add_argument("--cuisines", type=str, help="Comma-separated cuisines (e.g., 'Italian, Pizza').")
    parser.add_argument("--budget", type=str, help="Max budget for two (e.g., '1000', 'mid-range').")
    parser.add_argument("--rating", type=str, help="Minimum star rating (e.g., '4.0').")
    parser.add_argument("--vibe", type=str, help="Special occasion or atmosphere notes.")
    parser.add_argument("--online-only", action="store_true", help="Online order only.")
    parser.add_argument("--book-table", action="store_true", help="Book table only.")
    parser.add_argument("--demo", action="store_true", help="Run automated demonstration queries.")

    args = parser.parse_args()
    print_banner()

    if args.demo:
        run_demo()
        return

    if args.location:
        raw_input = UserPreferenceInput(
            location=args.location,
            cuisines=args.cuisines,
            max_budget=args.budget,
            min_rating=args.rating,
            vibe_or_notes=args.vibe,
            online_order_only=args.online_only,
            book_table_only=args.book_table,
        )
        normalizer = PreferenceNormalizer()
        norm = normalizer.normalize(raw_input)
        display_normalized_result(norm)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
