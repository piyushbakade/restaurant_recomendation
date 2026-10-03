"""
Configuration and scoring weights for Phase 4: Restaurant Retrieval & Recommendation Engine.
"""
from pathlib import Path

# Paths
PHASE_4_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_4_DIR.parent
CLEAN_DATA_FILE = PROJECT_ROOT / "phase_2" / "data" / "processed" / "zomato_clean.parquet"

# Candidate Pool & Recommendation Limits
DEFAULT_CANDIDATE_POOL_LIMIT = 30
DEFAULT_TOP_K_RECOMMENDATIONS = 5
MIN_CANDIDATES_BEFORE_RELAXATION = 3

# Multi-Attribute Scoring Weights (Sum = 1.0)
WEIGHT_CUISINE = 0.35
WEIGHT_RATING = 0.30
WEIGHT_PRICE = 0.20
WEIGHT_POPULARITY = 0.15

# Baseline Benchmarks for Normalization
DEFAULT_NEUTRAL_RATING = 3.5  # Assumed for unrated/new venues in scoring
GLOBAL_MAX_VOTES = 17000      # Normalization ceiling based on dataset max (~16,832)

# Relaxation Factors for Edge Cases
BUDGET_RELAXATION_MULTIPLIER = 1.25  # +25% budget expansion
RATING_RELAXATION_STEP = 0.4         # -0.4 star threshold lowering
