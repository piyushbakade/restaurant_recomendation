"""
Configuration settings for Phase 6: Interactive Web UI & API Layer.
"""
import os
from pathlib import Path

# Paths
PHASE_6_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_6_DIR.parent
STATIC_DIR = PHASE_6_DIR / "static"
TEMPLATES_DIR = PHASE_6_DIR / "templates"

# Server Network Settings
SERVER_HOST = os.environ.get("HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("PORT", "8000"))

# Quick-Select Presets for Interactive UI
POPULAR_LOCATIONS = [
    "Koramangala",
    "Indiranagar",
    "HSR Layout",
    "Whitefield",
    "MG Road",
    "Jayanagar",
    "BTM Layout",
    "Church Street",
]

POPULAR_CUISINES = [
    {"name": "Italian", "icon": "🍕"},
    {"name": "North Indian", "icon": "🍛"},
    {"name": "South Indian", "icon": "🍲"},
    {"name": "Chinese", "icon": "🥢"},
    {"name": "Biryani", "icon": "🥘"},
    {"name": "Continental", "icon": "🥗"},
    {"name": "Cafe", "icon": "☕"},
    {"name": "Desserts", "icon": "🍰"},
    {"name": "Fast Food", "icon": "🍔"},
]

DEFAULT_BUDGET_FOR_TWO = 1000
MIN_BUDGET_FOR_TWO = 200
MAX_BUDGET_FOR_TWO = 4000
BUDGET_STEP = 50
