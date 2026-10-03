"""
Data processing and normalization engine for Phase 2.
Cleans raw Zomato dataset into a query-optimized, deduplicated catalog.
"""
import ast
import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from phase_2.config import (
    CLEAN_COLUMNS,
    DEFAULT_MEDIAN_COST,
    LOCALITY_CLUSTERS,
    MIN_REVIEWS_TO_KEEP,
    PROCESSED_CSV_FILE,
    PROCESSED_DATA_DIR,
    PROCESSED_PARQUET_FILE,
    PROCESSING_METADATA_FILE,
    RAW_PARQUET_FILE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ProcessingReport:
    raw_row_count: int
    cleaned_row_count: int
    deduplicated_removed: int
    imputed_costs: int
    imputed_cuisines: int
    rated_count: int
    unrated_count: int
    new_restaurants_count: int
    execution_time_seconds: float
    output_parquet: str
    output_csv: str
    file_size_mb: float


def parse_rate(rate_val: Any) -> Tuple[Optional[float], bool]:
    """
    Parses rate strings like '4.1/5', '3.8 /5', 'NEW', '-', or NaN.
    Returns: (rate_as_float, is_new_boolean)
    """
    if rate_val is None or pd.isna(rate_val):
        return None, False

    rate_str = str(rate_val).strip()
    if rate_str.upper() == "NEW":
        return None, True
    if rate_str == "-" or rate_str == "":
        return None, False

    match = re.search(r"(\d+\.?\d*)", rate_str)
    if match:
        try:
            val = float(match.group(1))
            if 1.0 <= val <= 5.0:
                return round(val, 1), False
        except ValueError:
            pass

    return None, False


def parse_cost(cost_val: Any, default: int = DEFAULT_MEDIAN_COST) -> Tuple[int, bool]:
    """
    Parses approx_cost(for two people) strings like '1,200', '800', or NaN.
    Returns: (cleaned_integer_cost, was_imputed_boolean)
    """
    if cost_val is None or pd.isna(cost_val):
        return default, True

    cleaned_str = re.sub(r"[^\d]", "", str(cost_val))
    if cleaned_str.isdigit():
        val = int(cleaned_str)
        if 50 <= val <= 25000:  # Reasonable sanity bounds
            return val, False

    return default, True


def parse_cuisines(cuisines_val: Any) -> Tuple[List[str], bool]:
    """
    Parses comma-separated cuisine string into a cleaned list of strings.
    Returns: (list_of_cuisines, was_imputed_boolean)
    """
    if cuisines_val is None or pd.isna(cuisines_val):
        return ["Multi-Cuisine"], True

    raw_items = str(cuisines_val).split(",")
    cleaned = [c.strip().title() for c in raw_items if c.strip()]
    if not cleaned:
        return ["Multi-Cuisine"], True

    return cleaned, False


def parse_dishes(dish_val: Any) -> List[str]:
    """
    Parses comma-separated dish_liked string into a cleaned list of dishes.
    """
    if dish_val is None or pd.isna(dish_val):
        return []

    raw_items = str(dish_val).split(",")
    return [d.strip() for d in raw_items if d.strip()]


def parse_boolean(val: Any) -> bool:
    """
    Converts 'Yes'/'No', boolean, or string representations into bool.
    """
    if val is None or pd.isna(val):
        return False
    return str(val).strip().lower() in ("yes", "true", "1")


def cluster_location(location_val: Any) -> Tuple[str, str]:
    """
    Resolves micro-locality and maps it to a canonical macro-cluster.
    Returns: (micro_location, macro_cluster)
    """
    if location_val is None or pd.isna(location_val):
        return "Bangalore", "Bangalore"

    loc_str = str(location_val).strip()
    loc_lower = loc_str.lower()

    for cluster_name, aliases in LOCALITY_CLUSTERS.items():
        if loc_lower in aliases:
            return loc_str, cluster_name
        for alias in aliases:
            if alias in loc_lower:
                return loc_str, cluster_name

    # Fallback: clean title of the locality itself
    clean_title = loc_str.title()
    return clean_title, clean_title


def parse_reviews(reviews_val: Any, max_reviews: int = MIN_REVIEWS_TO_KEEP) -> List[str]:
    """
    Extracts clean textual excerpts from the raw reviews_list string.
    """
    if reviews_val is None or pd.isna(reviews_val):
        return []

    text = str(reviews_val).strip()
    if not text or text == "[]":
        return []

    reviews: List[str] = []

    # Attempt structured parsing via ast
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    raw_text = str(item[1])
                    cleaned = re.sub(r"^RATED\s*", "", raw_text, flags=re.IGNORECASE).strip()
                    cleaned = re.sub(r"\s+", " ", cleaned)
                    if len(cleaned) >= 15:
                        reviews.append(cleaned)
                        if len(reviews) >= max_reviews:
                            break
    except Exception:
        # Fallback regex extraction if ast fails on malformed quotes
        matches = re.findall(r"RATED\s*\\?n?\s*([^'\"\(\)]+)", text)
        for m in matches:
            cleaned = re.sub(r"\s+", " ", m).strip()
            if len(cleaned) >= 15:
                reviews.append(cleaned)
                if len(reviews) >= max_reviews:
                    break

    return reviews


def generate_restaurant_id(name: str, address: str, location: str) -> str:
    """
    Generates a deterministic UUID based on name and address for idempotent identification.
    """
    key = f"{name.strip().lower()}||{address.strip().lower()}||{location.strip().lower()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


class DataProcessor:
    """
    Executes the Phase 2 data cleaning, deduplication, and feature preparation.
    """

    def __init__(self, raw_path: Path = RAW_PARQUET_FILE, output_dir: Path = PROCESSED_DATA_DIR):
        self.raw_path = Path(raw_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_and_save(
        self,
        force: bool = False,
        sample_limit: Optional[int] = None,
        export_csv: bool = True,
    ) -> Tuple[pd.DataFrame, ProcessingReport]:
        """
        Executes end-to-end cleaning and saves the processed dataset.
        """
        start_time = time.time()

        if not self.raw_path.exists():
            raise FileNotFoundError(
                f"Raw dataset not found at {self.raw_path}. Run Phase 1 ingestion first."
            )

        logger.info(f"Loading raw dataset from {self.raw_path}...")
        df_raw = pd.read_parquet(self.raw_path)
        raw_count = len(df_raw)
        logger.info(f"Loaded {raw_count:,} raw records.")

        if sample_limit is not None and sample_limit > 0:
            logger.info(f"Applying sample limit of {sample_limit:,} rows for processing.")
            df_raw = df_raw.head(sample_limit)

        logger.info("Normalizing fields, handling nulls, and standardizing schemas...")
        clean_records: List[Dict[str, Any]] = []
        imputed_cost_count = 0
        imputed_cuisine_count = 0
        new_count = 0

        # Sort by votes descending so highest-voted duplicate is prioritized
        if "votes" in df_raw.columns:
            df_raw["votes_numeric"] = pd.to_numeric(df_raw["votes"], errors="coerce").fillna(0).astype(int)
            df_raw = df_raw.sort_values(by="votes_numeric", ascending=False).reset_index(drop=True)
        else:
            df_raw["votes_numeric"] = 0

        for _, row in df_raw.iterrows():
            name = str(row.get("name", "")).strip()
            if not name or name.lower() == "nan":
                continue  # Discard rows without restaurant name

            address = str(row.get("address", "")).strip()
            raw_loc = row.get("location")
            if pd.isna(raw_loc) or not str(raw_loc).strip():
                raw_loc = row.get("listed_in(city)", "Bangalore")

            loc_micro, loc_cluster = cluster_location(raw_loc)
            rate_val, is_new = parse_rate(row.get("rate"))
            if is_new:
                new_count += 1

            cost_val, was_cost_imp = parse_cost(row.get("approx_cost(for two people)"))
            if was_cost_imp:
                imputed_cost_count += 1

            cuisines_val, was_cuis_imp = parse_cuisines(row.get("cuisines"))
            if was_cuis_imp:
                imputed_cuisine_count += 1

            dishes = parse_dishes(row.get("dish_liked"))
            reviews = parse_reviews(row.get("reviews_list"))
            online = parse_boolean(row.get("online_order"))
            book = parse_boolean(row.get("book_table"))
            votes = int(row.get("votes_numeric", 0))
            rest_type = str(row.get("rest_type", "Casual Dining")).strip()
            url = str(row.get("url", "")).strip()

            rest_id = generate_restaurant_id(name, address, loc_micro)

            clean_records.append({
                "restaurant_id": rest_id,
                "name": name,
                "address": address,
                "location": loc_micro,
                "location_cluster": loc_cluster,
                "cuisines": cuisines_val,
                "cost_for_two": cost_val,
                "rate": rate_val,
                "votes": votes,
                "rest_type": rest_type if rest_type and rest_type.lower() != "nan" else "Casual Dining",
                "dish_liked": dishes,
                "sample_reviews": reviews,
                "online_order": online,
                "book_table": book,
                "is_new": is_new,
                "url": url,
                # Temporary keys for intelligent deduplication merge
                "_dedup_key": f"{name.lower()}||{address.lower() if len(address) > 10 else loc_micro.lower()}",
            })

        df_cleaned = pd.DataFrame(clean_records)
        before_dedup = len(df_cleaned)

        logger.info(f"Deduplicating {before_dedup:,} records by unique name & location/address...")
        # Group by dedup_key and aggregate missing dishes/reviews across sibling records
        df_dedup = (
            df_cleaned.groupby("_dedup_key", as_index=False)
            .first()  # Already sorted by votes descending, keeps most active row
            .drop(columns=["_dedup_key"])
        )
        dedup_count = len(df_dedup)
        removed_duplicates = before_dedup - dedup_count
        logger.info(f"Removed {removed_duplicates:,} duplicate listings ({dedup_count:,} unique restaurants remaining).")

        # Refine cost imputation by location_cluster median where applicable
        cluster_medians = df_dedup.groupby("location_cluster")["cost_for_two"].median().to_dict()
        df_dedup["cost_for_two"] = df_dedup.apply(
            lambda r: int(cluster_medians.get(r["location_cluster"], DEFAULT_MEDIAN_COST))
            if r["cost_for_two"] == DEFAULT_MEDIAN_COST
            else r["cost_for_two"],
            axis=1,
        )

        output_parquet = self.output_dir / "zomato_clean.parquet"
        output_csv = self.output_dir / "zomato_clean.csv"

        # Enforce column order and explicit types
        df_final = df_dedup[CLEAN_COLUMNS].copy()
        df_final["is_new"] = df_final["is_new"].astype(bool)

        # Save to Parquet
        logger.info(f"Persisting processed clean dataset to {output_parquet}...")
        df_final.to_parquet(
            output_parquet,
            index=False,
            engine="pyarrow",
            compression="snappy",
        )

        # Save CSV for rapid inspection if requested
        if export_csv:
            logger.info(f"Exporting readable CSV inspection file to {output_csv}...")
            # For CSV, serialize lists as comma-separated strings for clean spreadsheet viewing
            df_csv = df_final.copy()
            df_csv["cuisines"] = df_csv["cuisines"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
            df_csv["dish_liked"] = df_csv["dish_liked"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
            df_csv["sample_reviews"] = df_csv["sample_reviews"].apply(lambda x: " | ".join(x) if isinstance(x, list) else str(x))
            df_csv.to_csv(output_csv, index=False, encoding="utf-8")

        elapsed = round(time.time() - start_time, 2)
        file_size_mb = round(output_parquet.stat().st_size / (1024 * 1024), 2)
        rated_count = int(df_final["rate"].notna().sum())
        unrated_count = int(df_final["rate"].isna().sum())

        report = ProcessingReport(
            raw_row_count=raw_count,
            cleaned_row_count=len(df_final),
            deduplicated_removed=removed_duplicates,
            imputed_costs=imputed_cost_count,
            imputed_cuisines=imputed_cuisine_count,
            rated_count=rated_count,
            unrated_count=unrated_count,
            new_restaurants_count=new_count,
            execution_time_seconds=elapsed,
            output_parquet=str(output_parquet),
            output_csv=str(output_csv) if export_csv else "",
            file_size_mb=file_size_mb,
        )

        # Write audit metadata JSON
        self._write_metadata(df_final, report)
        logger.info(f"Phase 2 processing completed successfully in {elapsed}s.")

        return df_final, report

    def _write_metadata(self, df: pd.DataFrame, report: ProcessingReport) -> None:
        """Writes audit provenance metadata for Phase 2."""
        meta = asdict(report)
        meta["processed_at"] = datetime.now(timezone.utc).isoformat()
        meta["schema_columns"] = list(df.columns)
        meta["top_cuisines"] = (
            df.explode("cuisines")["cuisines"].value_counts().head(15).to_dict()
        )
        meta["top_clusters"] = df["location_cluster"].value_counts().head(10).to_dict()
        meta["rating_distribution"] = {
            "min": float(df["rate"].min()) if df["rate"].notna().any() else 0.0,
            "max": float(df["rate"].max()) if df["rate"].notna().any() else 0.0,
            "median": float(df["rate"].median()) if df["rate"].notna().any() else 0.0,
            "mean": round(float(df["rate"].mean()), 2) if df["rate"].notna().any() else 0.0,
        }
        meta["cost_distribution"] = {
            "min": int(df["cost_for_two"].min()),
            "max": int(df["cost_for_two"].max()),
            "median": int(df["cost_for_two"].median()),
            "mean": round(float(df["cost_for_two"].mean()), 2),
        }

        meta_file = self.output_dir / "processing_metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
