"""Source registry and machine-readable provenance manifest."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROVENANCE_DIR = Path(__file__).resolve().parents[2] / "data" / "provenance"
MANIFEST_PATH = PROVENANCE_DIR / "manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record_source(
    source_id: str,
    url: str,
    publisher: str,
    license_url: str,
    attribution: str,
    original_filename: str,
    local_path: Path | None = None,
    dataset_version: str | None = None,
    redistribution: str = "Allowed under CC BY 4.0 with attribution",
    notes: str = "",
) -> dict[str, Any]:
    """Record a data source with provenance metadata."""
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "source_id": source_id,
        "url": url,
        "publisher": publisher,
        "license": "CC BY 4.0",
        "license_url": license_url,
        "attribution": attribution,
        "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
        "original_filename": original_filename,
        "dataset_version": dataset_version,
        "redistribution_restrictions": redistribution,
        "notes": notes,
        "sha256": None,
    }
    if local_path and local_path.exists():
        entry["sha256"] = sha256_file(local_path)
        entry["local_path"] = str(local_path)
        entry["size_bytes"] = local_path.stat().st_size

    # Update manifest
    manifest = load_manifest()
    sources = manifest.setdefault("sources", [])
    # Replace if exists
    sources = [s for s in sources if s.get("source_id") != source_id]
    sources.append(entry)
    manifest["sources"] = sources
    manifest["updated"] = datetime.now(timezone.utc).isoformat()
    save_manifest(manifest)
    return entry


def load_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open() as f:
            return json.load(f)
    return {"sources": [], "project": "gridpulse", "version": "0.1.0"}


def save_manifest(manifest: dict[str, Any]) -> None:
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def get_source(source_id: str) -> dict[str, Any] | None:
    for s in load_manifest().get("sources", []):
        if s.get("source_id") == source_id:
            return s
    return None
