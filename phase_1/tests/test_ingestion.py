"""
Automated Test Suite for Phase 1: Data Ingestion.

Covers:
- Schema and column definitions
- Validation logic (passing, missing columns, row thresholds)
- SHA-256 integrity calculation
- Network fallback mechanisms
- Mocked end-to-end ingestion pipeline
- Metadata generation
- Live Hugging Face dataset connectivity (Integration test)
"""
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from phase_1.config import (
    DEFAULT_PARQUET_URLS,
    EXPECTED_COLUMNS,
    EXPECTED_MIN_ROWS,
    HF_DATASET_INFO_URL,
    HF_PARQUET_INFO_URL,
)
from phase_1.fetcher import (
    DataIngestor,
    calculate_sha256,
    get_parquet_urls,
    validate_dataframe,
)


@pytest.fixture
def sample_valid_df() -> pd.DataFrame:
    """Creates a minimal valid DataFrame matching the Zomato schema."""
    data = {col: [f"sample_value_{i}" for i in range(5)] for col in EXPECTED_COLUMNS}
    data["votes"] = [100, 200, 300, 400, 500]
    data["rate"] = ["4.1/5", "3.9/5", "4.5/5", "NEW", "-"]
    data["approx_cost(for two people)"] = ["800", "1,200", "500", "1,500", "400"]
    return pd.DataFrame(data)


# -------------------------------------------------------------------------
# Unit Tests: Schema & Configuration
# -------------------------------------------------------------------------

def test_expected_columns_definition():
    """Verify that all 17 mandatory columns are properly configured."""
    assert len(EXPECTED_COLUMNS) == 17
    assert "name" in EXPECTED_COLUMNS
    assert "location" in EXPECTED_COLUMNS
    assert "cuisines" in EXPECTED_COLUMNS
    assert "rate" in EXPECTED_COLUMNS
    assert "approx_cost(for two people)" in EXPECTED_COLUMNS
    assert "votes" in EXPECTED_COLUMNS


def test_default_parquet_urls():
    """Verify default fallback URLs are well-formed Hugging Face endpoints."""
    assert len(DEFAULT_PARQUET_URLS) >= 2
    for url in DEFAULT_PARQUET_URLS:
        assert url.startswith("https://huggingface.co/api/datasets/")
        assert url.endswith(".parquet")


# -------------------------------------------------------------------------
# Unit Tests: Validation Logic
# -------------------------------------------------------------------------

def test_validate_dataframe_success(sample_valid_df):
    """Test that a DataFrame conforming to the schema passes validation."""
    result = validate_dataframe(sample_valid_df, min_rows=1)
    assert result.is_valid is True
    assert result.row_count == 5
    assert result.column_count == 17
    assert len(result.missing_columns) == 0
    assert len(result.errors) == 0


def test_validate_dataframe_missing_column(sample_valid_df):
    """Test that missing required columns triggers a validation failure."""
    invalid_df = sample_valid_df.drop(columns=["location", "rate"])
    result = validate_dataframe(invalid_df, min_rows=1)
    assert result.is_valid is False
    assert "location" in result.missing_columns
    assert "rate" in result.missing_columns
    assert any("Missing mandatory columns" in err for err in result.errors)


def test_validate_dataframe_insufficient_rows(sample_valid_df):
    """Test that row count below min_rows fails validation."""
    result = validate_dataframe(sample_valid_df, min_rows=10)
    assert result.is_valid is False
    assert any("below minimum threshold" in err for err in result.errors)


# -------------------------------------------------------------------------
# Unit Tests: Hash Integrity & Metadata
# -------------------------------------------------------------------------

def test_calculate_sha256(tmp_path):
    """Test SHA-256 calculation against known content."""
    test_file = tmp_path / "test_hash.txt"
    content = b"Antigravity AI Restaurant Recommender Phase 1 Test"
    test_file.write_bytes(content)

    expected_sha = hashlib.sha256(content).hexdigest()
    actual_sha = calculate_sha256(test_file)
    assert actual_sha == expected_sha


# -------------------------------------------------------------------------
# Unit Tests: Network Resilience & Fallback
# -------------------------------------------------------------------------

@patch("requests.get")
def test_get_parquet_urls_api_success(mock_get):
    """Test discovering Parquet URLs from Hugging Face API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "default": {"train": ["https://hf.co/shard0.parquet", "https://hf.co/shard1.parquet"]}
    }
    mock_get.return_value = mock_response

    urls = get_parquet_urls()
    assert urls == ["https://hf.co/shard0.parquet", "https://hf.co/shard1.parquet"]


@patch("requests.get", side_effect=Exception("Connection timed out"))
def test_get_parquet_urls_fallback_on_error(mock_get):
    """Test that network error gracefully falls back to default URLs."""
    urls = get_parquet_urls()
    assert urls == DEFAULT_PARQUET_URLS


# -------------------------------------------------------------------------
# Unit Tests: Mocked Data Ingestor Pipeline
# -------------------------------------------------------------------------

def test_data_ingestor_mock_pipeline(tmp_path, sample_valid_df):
    """Test full Ingestor fetch_and_save_parquet pipeline with mocked download."""
    raw_dir = tmp_path / "raw"
    ingestor = DataIngestor(raw_dir=raw_dir)

    target_file = raw_dir / "test_output.parquet"
    mock_parquet_path = tmp_path / "shard_mock.parquet"
    sample_valid_df.to_parquet(mock_parquet_path)

    with patch("phase_1.fetcher.get_parquet_urls", return_value=["https://dummy/0.parquet"]), \
         patch("phase_1.fetcher.download_stream") as mock_download:
        
        # When download_stream is called, write sample parquet to the requested destination
        def side_effect_download(url, target_path, **kwargs):
            sample_valid_df.to_parquet(target_path)
            return target_path

        mock_download.side_effect = side_effect_download

        output_file, validation, metadata = ingestor.fetch_and_save_parquet(
            target_file=target_file,
            force=True,
            sample_limit=5,
        )

        assert output_file.exists()
        assert validation.is_valid is True
        assert validation.row_count == 5
        assert metadata["total_rows"] == 5
        assert metadata["file_name"] == "test_output.parquet"
        assert (raw_dir / "ingestion_metadata.json").exists()


def test_data_ingestor_skip_if_exists(tmp_path, sample_valid_df):
    """Test that existing valid raw dataset is not re-downloaded if force=False."""
    raw_dir = tmp_path / "raw"
    target_file = raw_dir / "existing.parquet"
    raw_dir.mkdir(parents=True, exist_ok=True)
    sample_valid_df.to_parquet(target_file)

    ingestor = DataIngestor(raw_dir=raw_dir)

    with patch("phase_1.fetcher.download_stream") as mock_download:
        output_file, validation, metadata = ingestor.fetch_and_save_parquet(
            target_file=target_file,
            force=False,
            sample_limit=5,
        )
        # Should NOT call download_stream because file exists
        mock_download.assert_not_called()
        assert output_file == target_file
        assert validation.row_count == 5


# -------------------------------------------------------------------------
# Integration Test: Live Hugging Face API Connectivity
# -------------------------------------------------------------------------

@pytest.mark.integration
def test_live_hf_dataset_metadata():
    """Verify live connectivity and accessibility of Hugging Face dataset info."""
    import requests
    response = requests.get(
        HF_PARQUET_INFO_URL,
        headers={"User-Agent": "Restaurant-Recommendation-Agent/1.0"},
        timeout=10,
    )
    assert response.status_code == 200, f"HF Parquet API returned {response.status_code}"
    data = response.json()
    assert "default" in data
    assert "train" in data["default"]
    assert len(data["default"]["train"]) >= 1
