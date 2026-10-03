"""
Phase 1: Data Ingestion Package.
"""
from phase_1.config import (
    EXPECTED_COLUMNS,
    EXPECTED_MIN_ROWS,
    HF_DATASET_ID,
    RAW_DATA_DIR,
    RAW_PARQUET_FILE,
)
from phase_1.fetcher import DataIngestor, ValidationResult, validate_dataframe

__all__ = [
    "DataIngestor",
    "ValidationResult",
    "validate_dataframe",
    "EXPECTED_COLUMNS",
    "EXPECTED_MIN_ROWS",
    "HF_DATASET_ID",
    "RAW_DATA_DIR",
    "RAW_PARQUET_FILE",
]
