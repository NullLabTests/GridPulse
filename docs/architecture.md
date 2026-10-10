# Architecture

```
src/gridpulse/
  cli.py          — Click CLI (check-sources, ingest, validate, run)
  ingestion.py    — CSV → validated analysis table + provenance
  schemas.py      — Column requirements, zero-vs-missing, timestamp normalization
  detectors.py    — Trailing-window baseline, MAD detector, optional IsolationForest
  evaluation.py   — Chronological splits, proxy labels, metrics, delay
  reporting.py    — Metrics JSON, static plots, compact HTML report
  provenance.py   — Source registry and SHA-256 manifest
```

Data flow:

1. Explicit ingest of permitted CSV → schema validation → analysis-ready Parquet.
2. Proxy anomaly labels defined independently of predictions.
3. Chronological split; detectors use only past observations (shifted rolling windows).
4. Metrics computed on test partition only.
5. Artifacts written to experiments/m1/.

All network access is confined to explicit ingestion commands. Tests and the default `run --synthetic` path are fully offline.
