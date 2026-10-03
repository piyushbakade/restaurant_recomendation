"""
Fetcher module for downloading, persisting, and validating raw restaurant dataset (Phase 1).
"""
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import requests
from tqdm import tqdm

from phase_1.config import (
    DEFAULT_PARQUET_URLS,
    EXPECTED_COLUMNS,
    EXPECTED_MIN_ROWS,
    HF_CSV_RAW_URL,
    HF_PARQUET_INFO_URL,
    INGESTION_METADATA_FILE,
    RAW_DATA_DIR,
    RAW_PARQUET_FILE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool
    row_count: int
    column_count: int
    missing_columns: List[str]
    null_counts: Dict[str, int]
    errors: List[str]


def calculate_sha256(file_path: Union[str, Path], chunk_size: int = 65536) -> str:
    """Computes SHA-256 hash of a file for integrity tracking."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_parquet_urls(timeout: int = 15) -> List[str]:
    """
    Fetches the latest parquet shard URLs from the Hugging Face dataset API.
    Falls back to hardcoded default shards if the API call fails.
    """
    try:
        response = requests.get(
            HF_PARQUET_INFO_URL,
            headers={"User-Agent": "Restaurant-Recommendation-Agent/1.0"},
            timeout=timeout,
        )
        if response.status_code == 200:
            data = response.json()
            urls = data.get("default", {}).get("train", [])
            if urls:
                logger.info(f"Discovered {len(urls)} parquet shard(s) via Hugging Face API.")
                return urls
    except Exception as exc:
        logger.warning(f"Could not query HF parquet API ({exc}); using fallback shard URLs.")
    
    return DEFAULT_PARQUET_URLS


def download_stream(
    url: str,
    target_path: Path,
    chunk_size: int = 1048576,  # 1MB
    timeout: int = 60,
    desc: Optional[str] = None,
) -> Path:
    """
    Downloads a remote file with streaming chunks and a progress bar.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target_path.with_suffix(target_path.suffix + ".tmp")
    
    headers = {"User-Agent": "Restaurant-Recommendation-Agent/1.0"}
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        
        with open(temp_target, "wb") as f, tqdm(
            desc=desc or target_path.name,
            total=total_size,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    size = f.write(chunk)
                    bar.update(size)

    # Atomic move once download completes
    if temp_target.exists():
        temp_target.replace(target_path)
    
    return target_path


def validate_dataframe(df: pd.DataFrame, min_rows: int = 1) -> ValidationResult:
    """
    Validates that a DataFrame conforms to the expected raw schema.
    """
    actual_columns = set(df.columns)
    missing = [col for col in EXPECTED_COLUMNS if col not in actual_columns]
    errors = []

    if missing:
        errors.append(f"Missing mandatory columns: {missing}")
    if len(df) < min_rows:
        errors.append(f"Row count {len(df)} is below minimum threshold of {min_rows}")

    null_counts = {col: int(df[col].isna().sum()) for col in df.columns if col in EXPECTED_COLUMNS}
    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        row_count=len(df),
        column_count=len(df.columns),
        missing_columns=missing,
        null_counts=null_counts,
        errors=errors,
    )


class DataIngestor:
    """
    Orchestrates the ingestion, persistence, and verification of restaurant data for Phase 1.
    """

    def __init__(self, raw_dir: Path = RAW_DATA_DIR):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch_and_save_parquet(
        self,
        target_file: Optional[Path] = None,
        force: bool = False,
        sample_limit: Optional[int] = None,
    ) -> Tuple[Path, ValidationResult, Dict[str, Any]]:
        """
        Fetches Parquet shards from Hugging Face, consolidates them, and stores the raw dataset.
        """
        output_file = target_file or (self.raw_dir / "zomato_raw.parquet")

        if output_file.exists() and not force:
            logger.info(f"Existing raw dataset found at {output_file}. Skipping download.")
            df = pd.read_parquet(output_file)
            validation = validate_dataframe(df, min_rows=sample_limit or EXPECTED_MIN_ROWS)
            metadata = self._load_or_create_metadata(output_file, df, validation)
            return output_file, validation, metadata

        parquet_urls = get_parquet_urls()
        logger.info(f"Downloading {len(parquet_urls)} shard(s) for consolidated raw dataset...")
        
        dfs: List[pd.DataFrame] = []
        for idx, url in enumerate(parquet_urls):
            shard_name = f"shard_{idx}.parquet"
            temp_shard_path = self.raw_dir / shard_name
            logger.info(f"Fetching shard {idx+1}/{len(parquet_urls)} from {url}")
            download_stream(url, temp_shard_path, desc=f"Shard {idx+1}")
            
            shard_df = pd.read_parquet(temp_shard_path)
            dfs.append(shard_df)
            
            # Clean up temp shard
            if temp_shard_path.exists():
                os.remove(temp_shard_path)

        consolidated_df = pd.concat(dfs, ignore_index=True)

        if sample_limit is not None and sample_limit > 0:
            logger.info(f"Applying sample limit of {sample_limit} rows.")
            consolidated_df = consolidated_df.head(sample_limit)

        # Validate before writing
        validation = validate_dataframe(
            consolidated_df,
            min_rows=sample_limit if sample_limit else EXPECTED_MIN_ROWS,
        )

        if not validation.is_valid:
            logger.error(f"Data validation failed: {validation.errors}")
            raise ValueError(f"Downloaded dataset failed validation: {validation.errors}")

        # Save consolidated Parquet file
        logger.info(f"Persisting consolidated raw dataset to {output_file}...")
        consolidated_df.to_parquet(output_file, index=False, engine="pyarrow", compression="snappy")

        # Generate and save metadata
        metadata = self._generate_metadata(output_file, consolidated_df, validation, parquet_urls)
        logger.info(f"Successfully ingested {validation.row_count} rows across {validation.column_count} columns.")

        return output_file, validation, metadata

    def _generate_metadata(
        self,
        file_path: Path,
        df: pd.DataFrame,
        validation: ValidationResult,
        source_urls: List[str],
    ) -> Dict[str, Any]:
        """Generates ingestion provenance metadata."""
        metadata = {
            "dataset_id": "ManikaSaini/zomato-restaurant-recommendation",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "file_name": file_path.name,
            "file_size_bytes": file_path.stat().st_size,
            "file_size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
            "sha256": calculate_sha256(file_path),
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": list(df.columns),
            "source_urls": source_urls,
            "validation": asdict(validation),
        }

        meta_file = self.raw_dir / "ingestion_metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def _load_or_create_metadata(
        self, file_path: Path, df: pd.DataFrame, validation: ValidationResult
    ) -> Dict[str, Any]:
        meta_file = self.raw_dir / "ingestion_metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self._generate_metadata(file_path, df, validation, DEFAULT_PARQUET_URLS)
