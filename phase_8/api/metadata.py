"""
Vercel Serverless Function: GET /api/metadata
Returns static metadata, popular locations, and cuisine presets for the frontend UI.
"""
from http.server import BaseHTTPRequestHandler
import json
import sys
from pathlib import Path

# Bootstrap project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_6.config import POPULAR_CUISINES, POPULAR_LOCATIONS


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Metadata Function."""

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        payload = {
            "popular_locations": POPULAR_LOCATIONS,
            "popular_cuisines": POPULAR_CUISINES,
            "default_budget": 1000,
            "min_budget": 200,
            "max_budget": 4000,
            "default_rating": 4.0,
        }

        resp_bytes = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp_bytes)))
        # Metadata is static and can be cached by Vercel Edge CDN for 1 hour
        self.send_header("Cache-Control", "public, s-maxage=3600, stale-while-revalidate=86400")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(resp_bytes)
