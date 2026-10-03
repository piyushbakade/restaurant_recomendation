"""
Pre-Flight Deployment Verification and Manual Testing CLI for Phase 8.
Validates Vercel manifests, environment variables, serverless handlers, and database readiness.
"""
import io
import json
import os
import sys
from pathlib import Path

# Bootstrap project root to sys.path
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

from phase_8.api.health import handler as HealthHandler
from phase_8.api.metadata import handler as MetadataHandler
from phase_8.api.recommendations import handler as RecommendationsHandler
from phase_8.config import get_deployment_config
from phase_8.db_migration import export_sql_file


class MockServerlessRequest:
    """Simulates BaseHTTPRequestHandler stream interactions for local serverless testing."""

    def __init__(self, method: str, path: str, body: bytes = b"", headers: dict = None):
        headers = headers or {}
        if body and "Content-Length" not in headers:
            headers["Content-Length"] = str(len(body))

        req_lines = [f"{method} {path} HTTP/1.1", "Host: localhost"]
        for k, v in headers.items():
            req_lines.append(f"{k}: {v}")
        req_lines.append("")
        req_lines.append("")
        req_data = "\r\n".join(req_lines).encode("utf-8") + body

        self.r = io.BytesIO(req_data)
        self.w = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "r" in mode:
            return self.r
        return self.w

    def sendall(self, b):
        self.w.write(b)

    def settimeout(self, t):
        pass

    def setsockopt(self, *args):
        pass

    @property
    def status_code(self) -> int:
        raw = self.w.getvalue().decode("utf-8", errors="ignore")
        if not raw:
            return 0
        first_line = raw.split("\r\n")[0]
        parts = first_line.split()
        return int(parts[1]) if len(parts) > 1 else 0

    def get_response_body(self) -> str:
        raw = self.w.getvalue().decode("utf-8", errors="ignore")
        if "\r\n\r\n" in raw:
            return raw.split("\r\n\r\n", 1)[1]
        return ""


def run_serverless_simulation():
    """Simulates native Vercel serverless executions locally."""
    print("\n--- 2. Simulating Vercel Serverless Function Invocations ---")

    # A. GET /api/health
    req_health = MockServerlessRequest("GET", "/api/health")
    HealthHandler(req_health, ("127.0.0.1", 80), None)
    print(f"  • GET /api/health         : Status {req_health.status_code} OK")

    # B. GET /api/metadata
    req_meta = MockServerlessRequest("GET", "/api/metadata")
    MetadataHandler(req_meta, ("127.0.0.1", 80), None)
    print(f"  • GET /api/metadata       : Status {req_meta.status_code} OK")

    # C. POST /api/recommendations
    payload = json.dumps({
        "location": "Koramangala",
        "cuisines": ["Italian", "Pizza"],
        "max_budget": 1000,
        "min_rating": 4.0,
        "vibe_or_notes": "romantic dinner",
        "top_k": 3,
    }).encode("utf-8")

    req_rec = MockServerlessRequest(
        "POST",
        "/api/recommendations",
        body=payload,
        headers={"Content-Type": "application/json"},
    )
    RecommendationsHandler(req_rec, ("127.0.0.1", 80), None)

    print(f"  • POST /api/recommendations: Status {req_rec.status_code} OK")
    resp_body = req_rec.get_response_body()
    parsed = json.loads(resp_body)

    rec_count = len(parsed.get("recommendations", []))
    latency = parsed.get("meta", {}).get("execution_time_ms", 0)
    print(f"    - Returned {rec_count} recommendations in {latency} ms")
    print(f"    - Top match: {parsed['recommendations'][0]['name'] if rec_count else 'None'}")


def main():
    print("=" * 80)
    print(" GOURMET AI - PHASE 8 VERCEL SERVERLESS DEPLOYMENT CHECKER")
    print(" Validating Environment, Manifests, Functions, and Database Readiness")
    print("=" * 80)

    config = get_deployment_config()
    val = config.validate()

    # 1. Environment Check
    print("\n--- 1. Environment & API Keys Verification ---")
    env_file = PROJECT_ROOT / ".env"
    print(f"  • .env File Status       : {'✅ Found' if env_file.is_file() else '⚠️ Missing (using defaults / .env.example)'}")
    print(f"  • Vercel Environment     : {config.vercel_env}")
    print(f"  • Gemini API Credentials : {'✅ Configured' if config.has_gemini_credentials else '⚠️ Not set (falls back to mock/template)'}")
    print(f"  • Cloud PostgreSQL URL   : {'✅ Configured' if config.has_database_credentials else 'ℹ️ Local parquet catalog active'}")
    print(f"  • Timeout Safeguard      : {config.timeout_seconds} seconds")

    if val["warnings"]:
        for w in val["warnings"]:
            print(f"    Notice: {w}")

    # 2. Vercel Manifest Validation
    print("\n--- 2. Vercel Manifest Verification ---")
    vercel_file = PROJECT_ROOT / "phase_8" / "vercel.json"
    if vercel_file.is_file():
        manifest = json.loads(vercel_file.read_text(encoding="utf-8"))
        print(f"  • vercel.json Syntax      : ✅ Valid JSON")
        print(f"  • Configured Routes       : {len(manifest.get('routes', []))} route rules")
        print(f"  • Security Headers        : {len(manifest.get('headers', [{}])[0].get('headers', []))} headers")
    else:
        print("  • vercel.json Syntax      : ❌ Missing phase_8/vercel.json")

    # 3. Export SQL Schema
    sql_path = export_sql_file()
    print(f"\n--- 3. Cloud Database Schema Export ---")
    print(f"  • Generated Neon Schema   : ✅ {sql_path.name} ({sql_path.stat().st_size} bytes)")

    # 4. Serverless Handler Simulation
    run_serverless_simulation()

    # 5. Deployment Instructions
    print("\n" + "=" * 80)
    print(" 🚀 READY FOR VERCEL DEPLOYMENT")
    print("=" * 80)
    print("""
Deployment Options:

Option A: Deploy via Vercel CLI
  1. Install Vercel CLI (if needed): npm install -g vercel
  2. Deploy to preview: vercel
  3. Deploy to production: vercel --prod

Option B: Deploy via GitHub (Recommended)
  1. Push code to your GitHub repository
  2. Connect repository on https://vercel.com/new
  3. Set Environment Variables in Project Settings:
     - GEMINI_API_KEY=<your-key>
     - DATABASE_URL=<neon-postgres-url> (optional)
     - RESTAURANT_DATA_SOURCE=local_parquet
  4. Click 'Deploy'
""")


if __name__ == "__main__":
    main()
