"""
CLI Runner and Manual Testing Tool for Phase 7 Output Layer.
Provides interactive manual querying, schema validation against files, and demonstration scenarios.
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from phase_7.formatter import ResponseFormatter
from phase_7.service import OutputService
from phase_7.validator import ContractValidator


def run_demo():
    """Executes 3 representative dining queries and demonstrates contract formatting & validation."""
    print("=" * 80)
    print(" GOURMET AI - PHASE 7 OUTPUT LAYER DEMO")
    print(" Validating Standardized JSON Contracts & Formatting")
    print("=" * 80)

    service = OutputService()

    scenarios = [
        {
            "name": "Scenario 1: ARCHITECTURE.md Standard Contract (Koramangala Italian, ₹1000, 4.0★)",
            "params": {
                "location": "Koramangala",
                "cuisines": ["Italian", "Pizza"],
                "max_budget": 1000,
                "min_rating": 4.0,
                "vibe_or_notes": "romantic candle-light date night",
                "top_k": 3,
            },
        },
        {
            "name": "Scenario 2: Casual Afternoon Cafe (Indiranagar, ₹700, 4.1★)",
            "params": {
                "location": "Indiranagar",
                "cuisines": ["Cafe", "Desserts"],
                "max_budget": 700,
                "min_rating": 4.1,
                "vibe_or_notes": "quiet spot for reading and filter coffee",
                "top_k": 2,
            },
        },
        {
            "name": "Scenario 3: Budget Biryani Hub (Whitefield, ₹500, 3.8★)",
            "params": {
                "location": "Whitefield",
                "cuisines": ["Biryani", "North Indian"],
                "max_budget": 500,
                "min_rating": 3.8,
                "vibe_or_notes": "quick office team lunch",
                "top_k": 3,
            },
        },
    ]

    for idx, sc in enumerate(scenarios, 1):
        print(f"\n[{idx}/3] {sc['name']}")
        print("-" * 80)

        response = service.generate_recommendations(**sc["params"])
        resp_dict = response.model_dump()

        # Validate against ContractValidator
        report = ContractValidator.validate_success_response(resp_dict)
        etag = service.compute_etag(response)

        print(f"Contract Validation : {'✅ PASSED' if report.is_valid else '❌ FAILED'}")
        if report.errors:
            print(f"  Errors  : {report.errors}")
        if report.warnings:
            print(f"  Warnings: {report.warnings}")

        print(f"Status              : {response.status}")
        print(f"Candidates Found    : {response.total_candidates_found}")
        print(f"Curated Matches     : {len(response.recommendations)}")
        print(f"Execution Latency   : {response.meta.execution_time_ms} ms")
        print(f"Computed ETag       : {etag}")

        print("\n--- JSON OUTPUT PREVIEW (First Recommendation) ---")
        first_rec_preview = {
            "status": response.status,
            "query_summary": response.query_summary.model_dump(),
            "total_candidates_found": response.total_candidates_found,
            "recommendations": [response.recommendations[0].model_dump()] if response.recommendations else [],
            "meta": response.meta.model_dump(),
        }
        print(json.dumps(first_rec_preview, indent=2))

    print("\n" + "=" * 80)
    print(" ✅ All Phase 7 demonstration scenarios completed successfully.")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 7 Output Layer CLI & Contract Validation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--demo", action="store_true", help="Run automated demonstration scenarios")
    parser.add_argument("--location", "-l", type=str, default="Koramangala", help="Target Bangalore locality")
    parser.add_argument("--cuisines", "-c", type=str, default="Italian", help="Comma-separated cuisines (e.g. Italian,Pizza)")
    parser.add_argument("--budget", "-b", type=int, default=1000, help="Max budget for two (INR)")
    parser.add_argument("--rating", "-r", type=float, default=4.0, help="Minimum rating (1.0 to 5.0)")
    parser.add_argument("--notes", "-n", type=str, default="cozy date night", help="Occasion or dining vibe notes")
    parser.add_argument("--top-k", "-k", type=int, default=3, help="Number of recommendations to return")
    parser.add_argument(
        "--format",
        "-f",
        choices=["pretty", "json", "markdown"],
        default="pretty",
        help="Output presentation format",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "template", "gemini"],
        default="mock",
        help="Recommendation generation provider",
    )
    parser.add_argument("--validate-file", type=str, help="Validate an existing JSON file against Phase 7 contract")
    parser.add_argument("--save", type=str, help="Save output to the specified file path")

    args = parser.parse_args()

    if args.demo:
        run_demo()
        return

    if args.validate_file:
        file_path = Path(args.validate_file)
        if not file_path.exists():
            print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
            sys.exit(1)

        raw_content = file_path.read_text(encoding="utf-8")
        report = ContractValidator.validate_json_string(raw_content)

        print(f"File Validation Result for '{file_path}':")
        print(f"  Valid   : {report.is_valid}")
        print(f"  Errors  : {report.errors}")
        print(f"  Warnings: {report.warnings}")
        sys.exit(0 if report.is_valid else 1)

    # Run query
    service = OutputService()
    cuisines_list = [c.strip() for c in args.cuisines.split(",") if c.strip()]

    response = service.generate_recommendations(
        location=args.location,
        cuisines=cuisines_list,
        max_budget=args.budget,
        min_rating=args.rating,
        vibe_or_notes=args.notes,
        top_k=args.top_k,
        provider_override=args.provider,
    )

    if args.format == "json":
        output_str = ResponseFormatter.to_json(response)
    elif args.format == "markdown":
        output_str = ResponseFormatter.to_markdown(response)
    else:
        output_str = ResponseFormatter.to_pretty_json(response)

    print(output_str)

    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(output_str, encoding="utf-8")
        print(f"\n[Saved output to {save_path}]", file=sys.stderr)


if __name__ == "__main__":
    main()
