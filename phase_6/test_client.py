#!/usr/bin/env python3
"""
CLI test client for Phase 6 REST API endpoints.

Usage:
    # Test health check:
    python phase_6/test_client.py --health

    # Test metadata:
    python phase_6/test_client.py --metadata

    # Test recommendations query:
    python phase_6/test_client.py --location Koramangala --cuisines "Italian, Pizza" --budget 1000
"""
import argparse
import json
import sys
from pathlib import Path
import requests

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_6.config import SERVER_HOST, SERVER_PORT


def main():
    parser = argparse.ArgumentParser(description="Test GourmetAI REST API endpoints.")
    parser.add_argument("--url", type=str, default=f"http://{SERVER_HOST}:{SERVER_PORT}", help="Base URL of server.")
    parser.add_argument("--health", action="store_true", help="Call GET /api/health.")
    parser.add_argument("--metadata", action="store_true", help="Call GET /api/metadata.")
    parser.add_argument("--location", type=str, default="Koramangala", help="Target location.")
    parser.add_argument("--cuisines", type=str, default="Italian, Pizza", help="Cuisines.")
    parser.add_argument("--budget", type=int, default=1000, help="Budget.")
    parser.add_argument("--rating", type=float, default=4.0, help="Rating floor.")
    parser.add_argument("--vibe", type=str, default="cozy date night", help="Dining vibe notes.")

    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    if args.health:
        resp = requests.get(f"{base_url}/api/health", timeout=5)
        print(f"GET /api/health -> Status {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
        return

    if args.metadata:
        resp = requests.get(f"{base_url}/api/metadata", timeout=5)
        print(f"GET /api/metadata -> Status {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
        return

    payload = {
        "location": args.location,
        "cuisines": [c.strip() for c in args.cuisines.split(",") if c.strip()],
        "max_budget": args.budget,
        "min_rating": args.rating,
        "vibe_or_notes": args.vibe,
        "top_k": 3,
    }

    print(f"POST {base_url}/api/recommendations ...")
    resp = requests.post(f"{base_url}/api/recommendations", json=payload, timeout=10)
    print(f"Response Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    main()
