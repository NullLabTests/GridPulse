"""Ingestion and normalization pipeline for GridPulse."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from gridpulse.provenance import record_source, sha256_file
from gridpulse.schemas import analysis_ready, validate_merged_schema

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def ingest_merged_csv(path: Path, source_id: str = "openei_outage_merged") -> pd.DataFrame:
    """Ingest a merged outage CSV and validate it."""
    df = pd.read_csv(path)
    result = validate_merged_schema(df)
    if not result.valid:
        raise ValueError(f"Schema validation failed: {result.errors}")

    # Record provenance if not already
    record_source(
        source_id=source_id,
        url="https://data.openei.org/submissions/6458",
        publisher="Pacific Northwest National Laboratory",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        attribution=(
            "She, Buxin, et al. Event-correlated Outage Dataset in America. "
            "Pacific Northwest National Laboratory, 1 October, 2024, "
            "Open Energy Data Initiative (OEDI). https://data.openei.org/submissions/6458."
        ),
        original_filename=path.name,
        local_path=path,
        dataset_version="R1 (2025-04)",
        notes="Processed merged outage events from EAGLE-I correlated with DOE-417.",
    )
    return df


def build_analysis_table(df: pd.DataFrame, out_path: Path | None = None) -> pd.DataFrame:
    """Normalize and write analysis-ready table."""
    ready = analysis_ready(df)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ready.to_parquet(out_path, index=False)
        # Also write checksum
        checksum_path = out_path.with_suffix(".sha256")
        checksum_path.write_text(sha256_file(out_path) + "\n")
    return ready


def data_quality_summary(df: pd.DataFrame) -> dict[str, Any]:
    """Produce a data-quality summary."""
    summary: dict[str, Any] = {
        "n_rows": len(df),
        "n_unique_fips": int(df["fips"].nunique()) if "fips" in df.columns else 0,
        "n_states": int(df["state"].nunique()) if "state" in df.columns else 0,
        "time_min": str(df["start_time"].min()) if "start_time" in df.columns else None,
        "time_max": str(df["start_time"].max()) if "start_time" in df.columns else None,
        "mean_customers_describe": df["mean_customers"].describe().to_dict()
        if "mean_customers" in df.columns
        else {},
        "zero_outages": int((df["mean_customers"] == 0).sum()) if "mean_customers" in df.columns else 0,
        "missing_mean": int(df["mean_customers"].isna().sum()) if "mean_customers" in df.columns else 0,
    }
    return summary


def save_quality_report(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(summary, f, indent=2, default=str)
