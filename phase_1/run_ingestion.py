#!/usr/bin/env python3
"""
CLI entry point for Phase 1: Data Ingestion.

Usage:
    # Full dataset ingestion:
    python phase_1/run_ingestion.py

    # Fast sample ingestion (e.g. 1,000 records for fast verification):
    python phase_1/run_ingestion.py --sample 1000

    # Verify existing downloaded dataset:
    python phase_1/run_ingestion.py --verify-only

    # Force re-download:
    python phase_1/run_ingestion.py --force
"""
import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path so phase_1 can be imported directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from phase_1.config import EXPECTED_COLUMNS, RAW_PARQUET_FILE
from phase_1.fetcher import DataIngestor, validate_dataframe


def print_banner():
    print("=" * 70)
    print("   AI RESTAURANT RECOMMENDER - PHASE 1: DATA INGESTION")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Ingest restaurant dataset from Hugging Face.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if data already exists locally.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Optional limit on row count (for fast testing / verification).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the integrity of existing raw dataset without downloading.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Custom output parquet file path.",
    )

    args = parser.parse_args()
    print_banner()

    target_file = Path(args.out) if args.out else RAW_PARQUET_FILE
    ingestor = DataIngestor()

    if args.verify_only:
        print(f"\n[Mode: Verify Only] Checking dataset at: {target_file}")
        if not target_file.exists():
            print(f"Error: File not found at {target_file}. Run ingestion first.")
            sys.exit(1)

        df = pd.read_parquet(target_file)
        validation = validate_dataframe(df, min_rows=1)
        print(f"\nValidation Result:")
        print(f"  Valid: {validation.is_valid}")
        print(f"  Total Rows: {validation.row_count:,}")
        print(f"  Total Columns: {validation.column_count}")
        print(f"  Missing Expected Columns: {validation.missing_columns or 'None'}")
        
        if validation.is_valid:
            print("\nDataset integrity check PASSED.")
            sys.exit(0)
        else:
            print(f"\nDataset integrity check FAILED: {validation.errors}")
            sys.exit(1)

    start_time = time.time()
    try:
        print(f"Destination: {target_file}")
        if args.sample:
            print(f"Sample Limit: {args.sample:,} rows")
        if args.force:
            print("Force mode enabled: existing files will be overwritten.")

        file_path, validation, metadata = ingestor.fetch_and_save_parquet(
            target_file=target_file,
            force=args.force,
            sample_limit=args.sample,
        )

        elapsed = round(time.time() - start_time, 2)
        print("\n" + "-" * 70)
        print("INGESTION COMPLETED SUCCESSFULLY!")
        print("-" * 70)
        print(f"  Saved File:     {file_path}")
        print(f"  File Size:      {metadata['file_size_mb']} MB ({metadata['file_size_bytes']:,} bytes)")
        print(f"  SHA-256:        {metadata['sha256']}")
        print(f"  Total Rows:     {validation.row_count:,}")
        print(f"  Total Columns:  {validation.column_count}")
        print(f"  Elapsed Time:   {elapsed}s")
        print("\nColumns Verified:")
        for idx, col in enumerate(EXPECTED_COLUMNS, 1):
            null_count = validation.null_counts.get(col, 0)
            null_pct = round((null_count / validation.row_count) * 100, 1) if validation.row_count else 0
            print(f"  {idx:2d}. {col:<28} (Nulls: {null_count:,} - {null_pct}%)")

        print("-" * 70)
        print("Phase 1 verified and ready for Phase 2 (Data Cleaning & Preparation).")
        print("=" * 70)

    except Exception as exc:
        print(f"\nIngestion failed with error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
