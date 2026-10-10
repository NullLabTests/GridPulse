"""Data schemas and validation for GridPulse."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

REQUIRED_MERGED_COLUMNS = {
    "fips",
    "state",
    "county",
    "start_time",
    "duration",
    "min_customers",
    "max_customers",
    "mean_customers",
}

OPTIONAL_EVENT_COLUMNS = {
    "event_id",
    "event_type",
    "Datetime Event Began",
    "Datetime Restoration",
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]
    n_rows: int
    n_duplicates: int
    n_missing_timestamps: int
    n_negative_counts: int


def validate_merged_schema(df: pd.DataFrame) -> ValidationResult:
    """Validate a merged outage DataFrame against expected schema."""
    errors: list[str] = []
    warnings: list[str] = []

    missing = REQUIRED_MERGED_COLUMNS - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {sorted(missing)}")

    if df.empty:
        warnings.append("DataFrame is empty")

    n_dup = 0
    if not df.empty and "start_time" in df.columns and "fips" in df.columns:
        n_dup = int(df.duplicated(subset=["fips", "start_time"]).sum())
        if n_dup:
            warnings.append(f"Found {n_dup} duplicate (fips, start_time) pairs")

    n_missing_ts = 0
    if "start_time" in df.columns:
        n_missing_ts = int(df["start_time"].isna().sum())
        if n_missing_ts:
            errors.append(f"{n_missing_ts} missing start_time values")

    n_neg = 0
    for col in ["min_customers", "max_customers", "mean_customers", "duration"]:
        if col in df.columns:
            neg = int((df[col] < 0).sum())
            if neg:
                n_neg += neg
                errors.append(f"{neg} negative values in {col}")

    # Zero vs missing: mean_customers == 0 is valid (no outage recorded for that event)
    # Missing is NaN

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        n_rows=len(df),
        n_duplicates=n_dup,
        n_missing_timestamps=n_missing_ts,
        n_negative_counts=n_neg,
    )


def normalize_timestamps(df: pd.DataFrame, tz: str = "UTC") -> pd.DataFrame:
    """Normalize start_time to timezone-aware UTC."""
    df = df.copy()
    if "start_time" not in df.columns:
        return df
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce", utc=True)
    return df


def analysis_ready(df: pd.DataFrame) -> pd.DataFrame:
    """Produce a compact analysis-ready table."""
    df = normalize_timestamps(df)
    # Keep essential columns
    keep = [
        c
        for c in [
            "fips",
            "state",
            "county",
            "start_time",
            "duration",
            "mean_customers",
            "max_customers",
            "min_customers",
        ]
        if c in df.columns
    ]
    out = df[keep].copy()
    out = out.sort_values(["fips", "start_time"]).reset_index(drop=True)
    return out
