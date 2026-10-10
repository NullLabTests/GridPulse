# GridPulse

Reproducible, CPU-friendly research benchmark for detecting anomalous county-level power-outage events using openly licensed data.

## Research Question

Can lightweight statistical anomaly detectors identify unusually large or rapidly increasing county-level power outages, and how do their detection performance and false-alarm rates compare against simple baselines?

See `docs/preregistration.md` for the full protocol. This is retrospective detection, not operational forecasting.

## Quickstart

```bash
# Create virtual environment (Python 3.10+)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Offline smoke test with synthetic fixture (no network, no real data required)
gridpulse run --synthetic --out-dir experiments/m1_synthetic

# Check sources
gridpulse check-sources
```

## Data Provenance

Primary dataset: Event-correlated Outage Dataset in America (OpenEI / PNNL), CC BY 4.0.  
See `docs/data_provenance.md` and `data/provenance/manifest.json`.

Large raw files are gitignored. Download manually if desired:

```bash
# Example (user responsibility)
mkdir -p data/raw
curl -L -o data/raw/Outage_Dataset_R1.zip https://data.openei.org/files/6458/Outage_Dataset_R1.zip
unzip -l data/raw/Outage_Dataset_R1.zip   # inspect
# Then extract a merged CSV and ingest:
gridpulse ingest data/raw/Outage_Dataset/eaglei_outages_2014_merged.csv
```

## Reproducibility

```bash
# From local data (or synthetic)
gridpulse run --config configs/benchmark.yaml --synthetic
# or
gridpulse run --data data/processed/analysis.parquet --out-dir experiments/m1
```

Fixed random seeds, versioned config, and saved metrics/predictions ensure bit-for-bit reproducibility on the same inputs.

## Limitations

- Proxy labels derived from the magnitude series itself; not independently verified events.
- Event-level aggregates rather than continuous high-resolution time series.
- No causal claims.
- See `docs/limitations.md`.

## License

MIT for original code. Datasets retain their own licenses (CC BY 4.0).
