"""Unit tests for schemas, validation, zero vs missing, timestamps."""

import pandas as pd
import pytest

from gridpulse.schemas import (
    REQUIRED_MERGED_COLUMNS,
    analysis_ready,
    normalize_timestamps,
    validate_merged_schema,
)


def test_required_columns_present():
    df = pd.DataFrame(
        {
            "fips": [1001],
            "state": ["AL"],
            "county": ["Autauga"],
            "start_time": ["2020-01-01"],
            "duration": [1.0],
            "min_customers": [0],
            "max_customers": [10],
            "mean_customers": [5],
        }
    )
    result = validate_merged_schema(df)
    assert result.valid
    assert result.n_rows == 1


def test_missing_required_column():
    df = pd.DataFrame({"fips": [1], "state": ["X"]})
    result = validate_merged_schema(df)
    assert not result.valid
    assert any("Missing required columns" in e for e in result.errors)


def test_negative_counts_rejected():
    df = pd.DataFrame(
        {
            "fips": [1],
            "state": ["X"],
            "county": ["Y"],
            "start_time": ["2020-01-01"],
            "duration": [1.0],
            "min_customers": [-1],
            "max_customers": [10],
            "mean_customers": [5],
        }
    )
    result = validate_merged_schema(df)
    assert not result.valid
    assert any("negative" in e.lower() for e in result.errors)


def test_zero_customers_valid():
    df = pd.DataFrame(
        {
            "fips": [1],
            "state": ["X"],
            "county": ["Y"],
            "start_time": ["2020-01-01"],
            "duration": [0.0],
            "min_customers": [0],
            "max_customers": [0],
            "mean_customers": [0],
        }
    )
    result = validate_merged_schema(df)
    assert result.valid
    assert result.n_negative_counts == 0


def test_duplicate_detection():
    df = pd.DataFrame(
        {
            "fips": [1, 1],
            "state": ["X", "X"],
            "county": ["Y", "Y"],
            "start_time": ["2020-01-01", "2020-01-01"],
            "duration": [1.0, 1.0],
            "min_customers": [0, 0],
            "max_customers": [10, 10],
            "mean_customers": [5, 5],
        }
    )
    result = validate_merged_schema(df)
    assert result.n_duplicates == 1
    assert result.valid  # warning, not error


def test_timestamp_normalization_utc():
    df = pd.DataFrame({"start_time": ["2020-01-01 12:00:00"]})
    out = normalize_timestamps(df)
    assert out["start_time"].dt.tz is not None
    assert str(out["start_time"].dt.tz) == "UTC"


def test_analysis_ready_sorts_and_selects():
    df = pd.DataFrame(
        {
            "fips": [2, 1],
            "state": ["B", "A"],
            "county": ["Y", "X"],
            "start_time": ["2020-01-02", "2020-01-01"],
            "duration": [1, 1],
            "mean_customers": [10, 20],
            "extra": [99, 99],
        }
    )
    ready = analysis_ready(df)
    assert list(ready.columns) == [
        "fips",
        "state",
        "county",
        "start_time",
        "duration",
        "mean_customers",
    ]
    assert ready.iloc[0]["fips"] == 1
