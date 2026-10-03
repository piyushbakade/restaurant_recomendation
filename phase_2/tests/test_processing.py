"""
Automated Test Suite for Phase 2: Data Processing & Preparation.

Covers:
- Numeric rating parsing (standard, space variations, NEW, -, nulls)
- Cost normalization and currency cleaning (comma separation, null imputation)
- Cuisine list splitting and imputation
- Dish parsing and review excerpt extraction
- Locality clustering and canonical mapping
- Boolean conversion
- Deterministic restaurant ID generation
- Deduplication and pipeline end-to-end execution
"""
from pathlib import Path

import pandas as pd
import pytest

from phase_2.cleaner import (
    DataProcessor,
    cluster_location,
    generate_restaurant_id,
    parse_boolean,
    parse_cost,
    parse_cuisines,
    parse_dishes,
    parse_rate,
    parse_reviews,
)
from phase_2.config import CLEAN_COLUMNS, DEFAULT_MEDIAN_COST, RAW_PARQUET_FILE


# -------------------------------------------------------------------------
# Unit Tests: Field Normalization Functions
# -------------------------------------------------------------------------

def test_parse_rate_standard():
    """Verify standard ratings are extracted as floats."""
    val, is_new = parse_rate("4.1/5")
    assert val == 4.1
    assert is_new is False

    val, is_new = parse_rate("3.8 /5")
    assert val == 3.8
    assert is_new is False

    val, is_new = parse_rate("5.0")
    assert val == 5.0
    assert is_new is False


def test_parse_rate_special_cases():
    """Verify NEW, hyphen, and missing rates."""
    val, is_new = parse_rate("NEW")
    assert val is None
    assert is_new is True

    val, is_new = parse_rate("-")
    assert val is None
    assert is_new is False

    val, is_new = parse_rate(None)
    assert val is None
    assert is_new is False

    # Out of bounds rates
    val, is_new = parse_rate("6.5/5")
    assert val is None


def test_parse_cost():
    """Verify comma-separated cost strings are parsed to integers."""
    cost, imputed = parse_cost("1,200")
    assert cost == 1200
    assert imputed is False

    cost, imputed = parse_cost("800")
    assert cost == 800
    assert imputed is False

    cost, imputed = parse_cost(None, default=450)
    assert cost == 450
    assert imputed is True

    cost, imputed = parse_cost("invalid", default=DEFAULT_MEDIAN_COST)
    assert cost == DEFAULT_MEDIAN_COST
    assert imputed is True


def test_parse_cuisines():
    """Verify cuisine strings are split into clean lists."""
    cuisines, imputed = parse_cuisines("North Indian, Chinese, Continental")
    assert cuisines == ["North Indian", "Chinese", "Continental"]
    assert imputed is False

    cuisines, imputed = parse_cuisines(None)
    assert cuisines == ["Multi-Cuisine"]
    assert imputed is True

    cuisines, imputed = parse_cuisines("   ")
    assert cuisines == ["Multi-Cuisine"]
    assert imputed is True


def test_parse_dishes():
    """Verify liked dishes are extracted as lists."""
    dishes = parse_dishes("Pasta, Lunch Buffet, Masala Chai")
    assert dishes == ["Pasta", "Lunch Buffet", "Masala Chai"]

    assert parse_dishes(None) == []
    assert parse_dishes("") == []


def test_parse_boolean():
    """Verify boolean normalization."""
    assert parse_boolean("Yes") is True
    assert parse_boolean("yes") is True
    assert parse_boolean(True) is True
    assert parse_boolean("1") is True

    assert parse_boolean("No") is False
    assert parse_boolean(None) is False
    assert parse_boolean("") is False


def test_cluster_location():
    """Verify micro-localities map to macro-clusters."""
    loc, cluster = cluster_location("Koramangala 5th Block")
    assert loc == "Koramangala 5th Block"
    assert cluster == "Koramangala"

    loc, cluster = cluster_location("Domlur")
    assert cluster == "Indiranagar"

    loc, cluster = cluster_location("Whitefield")
    assert cluster == "Whitefield"

    # Fallback title-casing
    loc, cluster = cluster_location("Hebbal")
    assert cluster == "Hebbal"


def test_parse_reviews():
    """Verify reviews tuples are parsed into clean text strings."""
    raw_review = "[('Rated 4.0', 'RATED\\n  A beautiful place to dine in. The food was tasty.'), ('Rated 5.0', 'RATED\\n  Excellent service and great ambiance!')]"
    reviews = parse_reviews(raw_review, max_reviews=2)
    assert len(reviews) == 2
    assert "A beautiful place to dine in." in reviews[0]
    assert "RATED" not in reviews[0]

    # Empty reviews
    assert parse_reviews("[]") == []
    assert parse_reviews(None) == []


def test_generate_restaurant_id():
    """Verify deterministic UUID generation."""
    id1 = generate_restaurant_id("Toscano", "Koramangala 5th Block", "Koramangala")
    id2 = generate_restaurant_id("Toscano", "Koramangala 5th Block", "Koramangala")
    assert id1 == id2

    # Case insensitive
    id3 = generate_restaurant_id("toscano", "koramangala 5th block", "koramangala")
    assert id1 == id3

    # Different address
    id4 = generate_restaurant_id("Toscano", "UB City", "Lavelle Road")
    assert id1 != id4


# -------------------------------------------------------------------------
# Integration / Pipeline Tests: Synthetic & Real Data
# -------------------------------------------------------------------------

@pytest.fixture
def synthetic_raw_df() -> pd.DataFrame:
    """Creates synthetic raw records with intentional duplicates across delivery zones."""
    return pd.DataFrame([
        {
            "name": "Empire Restaurant",
            "address": "80 Feet Road, Koramangala",
            "location": "Koramangala 5th Block",
            "rate": "4.1/5",
            "votes": "500",
            "online_order": "Yes",
            "book_table": "No",
            "cuisines": "North Indian, Biryani, Mughlai",
            "approx_cost(for two people)": "800",
            "dish_liked": "Ghee Rice, Chicken Kebab",
            "reviews_list": "[('Rated 4.0', 'RATED\\n  Great midnight food!')]",
            "rest_type": "Casual Dining",
            "listed_in(city)": "Koramangala",
            "url": "https://zomato.com/empire-1",
        },
        # Duplicate record under different delivery city
        {
            "name": "Empire Restaurant",
            "address": "80 Feet Road, Koramangala",
            "location": "Koramangala 5th Block",
            "rate": "4.1/5",
            "votes": "450",
            "online_order": "Yes",
            "book_table": "No",
            "cuisines": "North Indian, Biryani, Mughlai",
            "approx_cost(for two people)": "800",
            "dish_liked": "Ghee Rice, Chicken Kebab",
            "reviews_list": "[('Rated 4.0', 'RATED\\n  Great midnight food!')]",
            "rest_type": "Casual Dining",
            "listed_in(city)": "BTM",
            "url": "https://zomato.com/empire-1",
        },
        # Unrated / NEW restaurant
        {
            "name": "Fresh Bakers",
            "address": "Indiranagar 100ft Road",
            "location": "Indiranagar",
            "rate": "NEW",
            "votes": "0",
            "online_order": "No",
            "book_table": "No",
            "cuisines": "Bakery, Desserts",
            "approx_cost(for two people)": "300",
            "dish_liked": None,
            "reviews_list": "[]",
            "rest_type": "Bakery",
            "listed_in(city)": "Indiranagar",
            "url": "https://zomato.com/fresh-bakers",
        },
    ])


def test_pipeline_deduplication(tmp_path, synthetic_raw_df):
    """Verify that duplicates are removed and schema matches CLEAN_COLUMNS."""
    raw_file = tmp_path / "synthetic_raw.parquet"
    synthetic_raw_df.to_parquet(raw_file)

    output_dir = tmp_path / "processed"
    processor = DataProcessor(raw_path=raw_file, output_dir=output_dir)

    df_clean, report = processor.process_and_save(export_csv=True)

    # 3 raw records -> 2 unique restaurants after deduplication
    assert report.raw_row_count == 3
    assert report.cleaned_row_count == 2
    assert report.deduplicated_removed == 1

    # Check columns
    assert list(df_clean.columns) == CLEAN_COLUMNS

    # Check Empire Restaurant
    empire = df_clean[df_clean["name"] == "Empire Restaurant"].iloc[0]
    assert empire["rate"] == 4.1
    assert empire["cost_for_two"] == 800
    assert empire["location_cluster"] == "Koramangala"
    assert empire["is_new"] == False
    assert "Biryani" in empire["cuisines"]
    assert "Ghee Rice" in empire["dish_liked"]

    # Check Fresh Bakers (NEW)
    bakers = df_clean[df_clean["name"] == "Fresh Bakers"].iloc[0]
    assert pd.isna(bakers["rate"])
    assert bakers["is_new"] == True
    assert bakers["location_cluster"] == "Indiranagar"


@pytest.mark.skipif(not RAW_PARQUET_FILE.exists(), reason="Requires Phase 1 raw dataset")
def test_processor_with_real_sample(tmp_path):
    """Test running processor on a sample of real Phase 1 data."""
    output_dir = tmp_path / "sample_processed"
    processor = DataProcessor(raw_path=RAW_PARQUET_FILE, output_dir=output_dir)

    df_clean, report = processor.process_and_save(sample_limit=100, export_csv=False)
    assert len(df_clean) > 0
    assert report.cleaned_row_count <= 100
    assert (output_dir / "zomato_clean.parquet").exists()
    assert (output_dir / "processing_metadata.json").exists()
