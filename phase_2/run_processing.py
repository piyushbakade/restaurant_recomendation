#!/usr/bin/env python3
"""
CLI entry point for Phase 2: Data Processing & Preparation.

Usage:
    # Full dataset processing:
    python phase_2/run_processing.py

    # Fast sample processing (e.g. 1,000 records for rapid testing):
    python phase_2/run_processing.py --sample 1000

    # Verify existing cleaned dataset:
    python phase_2/run_processing.py --verify-only

    # Force re-processing:
    python phase_2/run_processing.py --force
"""
import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path so phase_2 can be imported directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from phase_2.cleaner import DataProcessor
from phase_2.config import (
    CLEAN_COLUMNS,
    PROCESSED_CSV_FILE,
    PROCESSED_PARQUET_FILE,
    RAW_PARQUET_FILE,
)


def print_banner():
    print("=" * 70)
    print("   AI RESTAURANT RECOMMENDER - PHASE 2: DATA PROCESSING")
    print("=" * 70)


def verify_processed_dataset(file_path: Path):
    print(f"\n[Mode: Verify Only] Checking processed dataset at: {file_path}")
    if not file_path.exists():
        print(f"Error: Processed file not found at {file_path}. Run processing first.")
        sys.exit(1)

    df = pd.read_parquet(file_path)
    print("\nDataset Verification Summary:")
    print(f"  Total Cleaned Records: {len(df):,}")
    print(f"  Total Columns:         {len(df.columns)}")
    
    missing = [c for c in CLEAN_COLUMNS if c not in df.columns]
    if missing:
        print(f"  FAILED: Missing expected columns: {missing}")
        sys.exit(1)
    else:
        print("  Schema Check:          PASSED (all 16 columns present)")

    # Data Quality Metrics
    null_rates = df["rate"].isna().sum()
    null_costs = (df["cost_for_two"] <= 0).sum()
    null_names = (df["name"].str.strip() == "").sum()
    duplicates = df.duplicated(subset=["name", "location"]).sum()

    print(f"  Empty Names:           {null_names} (must be 0)")
    print(f"  Invalid Costs (<=0):   {null_costs} (must be 0)")
    print(f"  Rated Restaurants:     {df['rate'].notna().sum():,} ({round(df['rate'].notna().mean()*100, 1)}%)")
    print(f"  Unrated / New:         {null_rates:,} ({round(null_rates/len(df)*100, 1)}%)")
    print(f"  Duplicate (name, loc): {duplicates} ({round(duplicates/len(df)*100, 2)}%)")

    if null_names == 0 and null_costs == 0 and len(df) > 0:
        print("\nAll data quality integrity checks PASSED.")
        sys.exit(0)
    else:
        print("\nData quality integrity checks FAILED.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Process and clean restaurant dataset.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-processing even if processed data already exists.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Limit number of raw records to process (for rapid testing).",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip readable CSV export to save disk I/O.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the integrity of existing processed dataset without re-running.",
    )

    args = parser.parse_args()
    print_banner()

    if args.verify_only:
        verify_processed_dataset(PROCESSED_PARQUET_FILE)

    if not RAW_PARQUET_FILE.exists():
        print(f"Error: Raw dataset not found at {RAW_PARQUET_FILE}.")
        print("Please run Phase 1 first: python phase_1/run_ingestion.py")
        sys.exit(1)

    print(f"Source Raw File:        {RAW_PARQUET_FILE}")
    print(f"Target Processed File:  {PROCESSED_PARQUET_FILE}")
    if args.sample:
        print(f"Sample Limit:           {args.sample:,} rows")

    processor = DataProcessor(raw_path=RAW_PARQUET_FILE)

    # Ensure UTF-8 stdout on Windows if supported
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        df_clean, report = processor.process_and_save(
            force=args.force,
            sample_limit=args.sample,
            export_csv=not args.no_csv,
        )

        print("\n" + "-" * 70)
        print("PHASE 2 PROCESSING COMPLETED SUCCESSFULLY!")
        print("-" * 70)
        print(f"  Raw Records Ingested:       {report.raw_row_count:,}")
        print(f"  Duplicates Removed:         {report.deduplicated_removed:,} ({round(report.deduplicated_removed/report.raw_row_count*100, 1)}%)")
        print(f"  Clean Unique Restaurants:   {report.cleaned_row_count:,}")
        print(f"  Processed File Size:        {report.file_size_mb} MB")
        print(f"  Execution Time:             {report.execution_time_seconds}s")
        print("\nQuality & Normalization Metrics:")
        print(f"  Rated Restaurants:          {report.rated_count:,} ({round(report.rated_count/report.cleaned_row_count*100, 1)}%)")
        print(f"  Unrated / New Restaurants:  {report.unrated_count:,} (is_new: {report.new_restaurants_count})")
        print(f"  Imputed Costs:              {report.imputed_costs:,}")
        print(f"  Imputed Cuisines:           {report.imputed_cuisines:,}")
        
        print("\nCost & Rating Benchmarks:")
        min_rate = df_clean['rate'].min() if df_clean['rate'].notna().any() else 0.0
        max_rate = df_clean['rate'].max() if df_clean['rate'].notna().any() else 0.0
        med_rate = df_clean['rate'].median() if df_clean['rate'].notna().any() else 0.0
        print(f"  Rating Range:               {min_rate:.1f} to {max_rate:.1f} / 5.0 (Median: {med_rate:.1f})")
        print(f"  Cost for Two Range:         Rs. {df_clean['cost_for_two'].min():,} to Rs. {df_clean['cost_for_two'].max():,} (Median: Rs. {df_clean['cost_for_two'].median():,})")
        
        print("\nTop 5 Locality Clusters:")
        top_clusters = df_clean["location_cluster"].value_counts().head(5)
        for loc, count in top_clusters.items():
            print(f"  * {loc:<25} {count:,} venues")

        print("-" * 70)
        print("Phase 2 verified and ready for Phase 3 (User Preference Processing).")
        print("=" * 70)

    except Exception as exc:
        print(f"\nProcessing failed with error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
