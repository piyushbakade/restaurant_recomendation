"""
Configuration, constants, and canonical taxonomy reference for Phase 3: User Preference Processing.
"""
from pathlib import Path
from typing import Dict, List, Set

PHASE_3_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_3_DIR.parent
CLEAN_DATA_PARQUET = PROJECT_ROOT / "phase_2" / "data" / "processed" / "zomato_clean.parquet"

# Default Preference Constraints
DEFAULT_MIN_RATING = 3.5
DEFAULT_MAX_BUDGET = 1000
MIN_ALLOWED_RATING = 1.0
MAX_ALLOWED_RATING = 5.0
MIN_ALLOWED_BUDGET = 50
MAX_ALLOWED_BUDGET = 25000

# Budget Tier Definitions (Mapped to Maximum Costs)
BUDGET_TIER_MAP: Dict[str, int] = {
    "budget": 500,
    "cheap": 500,
    "low": 500,
    "mid": 1200,
    "mid-range": 1200,
    "moderate": 1200,
    "medium": 1200,
    "premium": 2500,
    "fine_dining": 2500,
    "expensive": 2500,
    "luxury": 3500,
}

# Major Canonical Locality Clusters in Bangalore
PRIMARY_CLUSTERS: List[str] = [
    "Koramangala",
    "Indiranagar",
    "HSR Layout",
    "Whitefield",
    "JP Nagar",
    "Jayanagar",
    "BTM Layout",
    "Electronic City",
    "MG Road / Central",
    "Bellandur / Sarjapur",
    "Kalyan Nagar / Kammanahalli",
    "Malleshwaram",
    "Rajajinagar",
    "Marathahalli",
    "Bannerghatta Road",
    "Basavanagudi",
    "New BEL Road",
    "Frazer Town",
    "Ulsoor",
    "Commercial Street",
    "Brigade Road",
    "Church Street",
    "Residency Road",
    "Lavelle Road",
    "Richmond Town",
    "Domlur",
    "Old Airport Road",
    "Brookefield",
    "Sarjapur Road",
]

# Popular Cuisines Baseline Taxonomy
POPULAR_CUISINES: List[str] = [
    "North Indian",
    "Chinese",
    "South Indian",
    "Fast Food",
    "Biryani",
    "Desserts",
    "Continental",
    "Cafe",
    "Italian",
    "Pizza",
    "Beverages",
    "Bakery",
    "Street Food",
    "Andhra",
    "Burger",
    "Mughlai",
    "Rolls",
    "Momos",
    "Ice Cream",
    "Asian",
    "Thai",
    "Mexican",
    "Kebab",
    "Seafood",
    "Salad",
    "Healthy Food",
    "BBQ",
    "European",
    "American",
    "Japanese",
    "Sushi",
    "Arabian",
    "Middle Eastern",
]


def load_taxonomies_from_dataset() -> Dict[str, Set[str]]:
    """
    Dynamically extracts available locations, clusters, and cuisines from Phase 2 clean data.
    Falls back to baseline taxonomies if clean dataset is not yet generated.
    """
    locations: Set[str] = set()
    clusters: Set[str] = set(PRIMARY_CLUSTERS)
    cuisines: Set[str] = set(POPULAR_CUISINES)

    if CLEAN_DATA_PARQUET.exists():
        try:
            import pandas as pd
            df = pd.read_parquet(CLEAN_DATA_PARQUET, columns=["location", "location_cluster", "cuisines"])
            locations.update(df["location"].dropna().unique())
            clusters.update(df["location_cluster"].dropna().unique())
            for sublist in df["cuisines"].dropna():
                if isinstance(sublist, (list, tuple)):
                    cuisines.update(sublist)
        except Exception:
            pass

    return {
        "locations": locations or set(PRIMARY_CLUSTERS),
        "clusters": clusters,
        "cuisines": cuisines,
    }
