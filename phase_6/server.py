"""
HTTP Server for Phase 6: Interactive Web UI & API Layer.
Provides high-performance serving for static assets, HTML templates,
and REST endpoints (/api/recommendations, /api/health, /api/metadata).
"""
import http.server
import json
import logging
import mimetypes
import socketserver
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Optional
from urllib.parse import urlparse

from pydantic import ValidationError

from phase_6.api import (
    handle_health_endpoint,
    handle_metadata_endpoint,
    handle_recommendations_endpoint,
)
from phase_6.config import SERVER_HOST, SERVER_PORT, STATIC_DIR, TEMPLATES_DIR

logger = logging.getLogger(__name__)


class RecommendationRequestHandler(http.server.BaseHTTPRequestHandler):
    """Custom HTTP request handler serving Web UI and API endpoints."""

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json_response(self, status_code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. API: Health Check
        if path == "/api/health":
            self._send_json_response(200, handle_health_endpoint())
            return

        # 2. API: Metadata
        if path == "/api/metadata":
            self._send_json_response(200, handle_metadata_endpoint())
            return

        # 3. Static Assets: /static/...
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            file_path = STATIC_DIR / rel_path
            if file_path.is_file():
                mime_type, _ = mimetypes.guess_type(str(file_path))
                mime_type = mime_type or "application/octet-stream"
                try:
                    content = file_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self._set_cors_headers()
                    self.end_headers()
                    self.wfile.write(content)
                    return
                except Exception as e:
                    self._send_json_response(500, {"detail": f"Error reading file: {e}"})
                    return
            else:
                self._send_json_response(404, {"detail": f"Static asset not found: {path}"})
                return

        # 4. Frontend Root: / or /index.html
        if path in ["/", "/index.html"]:
            index_path = TEMPLATES_DIR / "index.html"
            if index_path.is_file():
                content = index_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self._send_json_response(500, {"detail": "Template index.html missing."})
                return

        # Unrecognized endpoint
        self._send_json_response(404, {"detail": f"Endpoint not found: {path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. API: Recommendations
        if path == "/api/recommendations":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_json_response(400, {"detail": "Request body cannot be empty."})
                return

            try:
                body_raw = self.rfile.read(content_length)
                data = json.loads(body_raw.decode("utf-8"))
            except Exception as e:
                self._send_json_response(400, {"detail": f"Invalid JSON payload: {e}"})
                return

            try:
                result = handle_recommendations_endpoint(data)
                self._send_json_response(200, result)
            except ValidationError as ve:
                self._send_json_response(422, {"detail": "Validation error", "errors": ve.errors()})
            except Exception as e:
                logger.exception("Error executing recommendations endpoint")
                self._send_json_response(500, {"detail": f"Internal server error: {e}"})
            return

        self._send_json_response(404, {"detail": f"POST endpoint not found: {path}"})

    def log_message(self, format, *args):
        """Custom concise logging format."""
        logger.info(f"{self.address_string()} - {format % args}")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Multithreaded HTTP server capable of serving concurrent browser requests."""
    daemon_threads = True
    allow_reuse_address = True


def create_server(host: str = SERVER_HOST, port: int = SERVER_PORT) -> ThreadedHTTPServer:
    """Factory creating configured HTTP server."""
    return ThreadedHTTPServer((host, port), RecommendationRequestHandler)


def run_server(host: str = SERVER_HOST, port: int = SERVER_PORT):
    """Starts the HTTP server and listens continuously."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    server = create_server(host, port)
    print("=" * 75)
    print(f"   GourmetAI - Interactive Web UI & API Server running at:")
    print(f"   >>> http://{host}:{port}/")
    print("=" * 75)
    print(f"   API Endpoints:")
    print(f"     POST http://{host}:{port}/api/recommendations")
    print(f"     GET  http://{host}:{port}/api/health")
    print(f"     GET  http://{host}:{port}/api/metadata")
    print("=" * 75)
    print("   Press Ctrl+C to stop the server.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        server.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else SERVER_PORT
    run_server(port=port)
