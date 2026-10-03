"""
Configuration and constants for Phase 1: Data Ingestion.
"""
from pathlib import Path
from typing import List

# Paths for Phase 1
PHASE_1_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_1_DIR.parent
DATA_DIR = PHASE_1_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"

# Hugging Face Dataset Details
HF_DATASET_ID = "ManikaSaini/zomato-restaurant-recommendation"
HF_DATASET_INFO_URL = f"https://datasets-server.huggingface.co/info?dataset={HF_DATASET_ID}"
HF_PARQUET_INFO_URL = f"https://huggingface.co/api/datasets/{HF_DATASET_ID}/parquet"
HF_CSV_RAW_URL = f"https://huggingface.co/datasets/{HF_DATASET_ID}/resolve/main/zomato.csv"

# Fallback direct Parquet shard URLs (Hugging Face default split)
DEFAULT_PARQUET_URLS = [
    f"https://huggingface.co/api/datasets/{HF_DATASET_ID}/parquet/default/train/0.parquet",
    f"https://huggingface.co/api/datasets/{HF_DATASET_ID}/parquet/default/train/1.parquet"
]

# Output file destinations
RAW_PARQUET_FILE = RAW_DATA_DIR / "zomato_raw.parquet"
RAW_CSV_FILE = RAW_DATA_DIR / "zomato_raw.csv"
INGESTION_METADATA_FILE = RAW_DATA_DIR / "ingestion_metadata.json"

# Mandatory schema columns from Zomato dataset
EXPECTED_COLUMNS: List[str] = [
    "url",
    "address",
    "name",
    "online_order",
    "book_table",
    "rate",
    "votes",
    "phone",
    "location",
    "rest_type",
    "dish_liked",
    "cuisines",
    "approx_cost(for two people)",
    "reviews_list",
    "menu_item",
    "listed_in(type)",
    "listed_in(city)"
]

# Expected minimum records in the complete dataset
EXPECTED_MIN_ROWS = 50000
