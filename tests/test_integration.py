"""Integration and provenance tests."""

import json
from pathlib import Path

import pandas as pd
import pytest

from gridpulse.cli import _make_synthetic
from gridpulse.ingestion import build_analysis_table, data_quality_summary, ingest_merged_csv
from gridpulse.provenance import load_manifest, record_source, sha256_file


def test_synthetic_fixture_labeled(tmp_path):
    df = _make_synthetic(42)
    assert (df["state"] == "SYNTHETIC").all()
    assert "SYNTHETIC" in df["county"].iloc[0]


def test_offline_synthetic_pipeline(tmp_path):
    df = _make_synthetic(42)
    ready = build_analysis_table(df, tmp_path / "analysis.parquet")
    assert len(ready) == 200
    summary = data_quality_summary(ready)
    assert summary["n_rows"] == 200
    assert summary["zero_outages"] >= 0


def test_provenance_manifest(tmp_path, monkeypatch):
    # Isolated manifest
    monkeypatch.setattr("gridpulse.provenance.PROVENANCE_DIR", tmp_path)
    monkeypatch.setattr("gridpulse.provenance.MANIFEST_PATH", tmp_path / "manifest.json")
    dummy = tmp_path / "dummy.csv"
    dummy.write_text("a,b\n1,2\n")
    entry = record_source(
        source_id="test",
        url="https://example.com",
        publisher="Test",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        attribution="Test attribution",
        original_filename="dummy.csv",
        local_path=dummy,
    )
    assert entry["sha256"] == sha256_file(dummy)
    manifest = load_manifest()
    assert any(s["source_id"] == "test" for s in manifest["sources"])


def test_checksum_stable():
    # Known small content
    p = Path("/tmp/gridpulse_test_hash.txt")
    p.write_text("hello")
    h1 = sha256_file(p)
    h2 = sha256_file(p)
    assert h1 == h2
    assert len(h1) == 64
