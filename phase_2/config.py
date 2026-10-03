"""
Configuration and constants for Phase 2: Data Processing & Preparation.
"""
from pathlib import Path
from typing import Dict, List

# Phase 2 Paths
PHASE_2_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_2_DIR.parent
DATA_DIR = PHASE_2_DIR / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Phase 1 Input Path
RAW_PARQUET_FILE = PROJECT_ROOT / "phase_1" / "data" / "raw" / "zomato_raw.parquet"

# Phase 2 Output Files
PROCESSED_PARQUET_FILE = PROCESSED_DATA_DIR / "zomato_clean.parquet"
PROCESSED_CSV_FILE = PROCESSED_DATA_DIR / "zomato_clean.csv"
PROCESSING_METADATA_FILE = PROCESSED_DATA_DIR / "processing_metadata.json"

# Processed Schema Columns
CLEAN_COLUMNS: List[str] = [
    "restaurant_id",
    "name",
    "address",
    "location",
    "location_cluster",
    "cuisines",
    "cost_for_two",
    "rate",
    "votes",
    "rest_type",
    "dish_liked",
    "sample_reviews",
    "online_order",
    "book_table",
    "is_new",
    "url",
]

# Major Bangalore Locality Clusters for Canonical Normalization
LOCALITY_CLUSTERS: Dict[str, List[str]] = {
    "Koramangala": [
        "koramangala", "koramangala 1st block", "koramangala 2nd block",
        "koramangala 3rd block", "koramangala 4th block", "koramangala 5th block",
        "koramangala 6th block", "koramangala 7th block", "koramangala 8th block", "ejipura"
    ],
    "Indiranagar": [
        "indiranagar", "old airport road", "domlur", "thippasandra", "hal 2nd stage", "hal 3rd stage"
    ],
    "Jayanagar": [
        "jayanagar", "jayanagar 4th block", "jayanagar 3rd block", "jayanagar 9th block",
        "south bangalore", "basavanagudi"
    ],
    "HSR Layout": [
        "hsr", "hsr layout", "hsr layout sector 1", "hsr layout sector 2", "hsr layout sector 3"
    ],
    "Whitefield": [
        "whitefield", "itpl", "brookefield", "marathahalli", "hoodi", "kadugodi"
    ],
    "JP Nagar": [
        "jp nagar", "jp nagar 1st phase", "jp nagar 2nd phase", "jp nagar 3rd phase",
        "jp nagar 6th phase", "jp nagar 7th phase", "bannerghatta road"
    ],
    "MG Road / Central": [
        "mg road", "brigade road", "church street", "residency road", "lavelle road",
        "richmond road", "cunningham road", "central bangalore", "commercial street", "st. marks road"
    ],
    "Malleshwaram": [
        "malleshwaram", "sadashiv nagar", "rajajinagar", "seshadripuram"
    ],
    "BTM Layout": [
        "btm", "btm layout", "btm 1st stage", "btm 2nd stage", "tavarekere"
    ],
    "Electronic City": [
        "electronic city", "electronic city phase 1", "electronic city phase 2"
    ],
    "Bellandur / Sarjapur": [
        "bellandur", "sarjapur road", "sarjapur", "haralur road", "kasavanahalli"
    ],
    "Kalyan Nagar / Kammanahalli": [
        "kalyan nagar", "kammanahalli", "banaswadi", "hennur", "hrbr layout"
    ],
}

# Default Imputation Constants
DEFAULT_MEDIAN_COST = 400
MIN_REVIEWS_TO_KEEP = 3
