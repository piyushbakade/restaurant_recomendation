#!/usr/bin/env python3
"""
Launcher script to run Phase 6 Interactive Web UI and API server.

Usage:
    python phase_6/run_ui.py
    python phase_6/run_ui.py --port 8080 --no-browser
"""
import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_6.config import SERVER_HOST, SERVER_PORT
from phase_6.server import run_server


def open_browser(url: str, delay: float = 1.0):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Launch GourmetAI Interactive Web UI & API.")
    parser.add_argument("--host", type=str, default=SERVER_HOST, help="Host to bind to (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help="Port to listen on (default: 8000).")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser.")

    args = parser.parse_args()
    url = f"http://{args.host}:{args.port}/"

    if not args.no_browser:
        threading.Thread(target=open_browser, args=(url, 1.2), daemon=True).start()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
