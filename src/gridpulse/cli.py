"""Command-line interface for GridPulse."""

from __future__ import annotations

import json
from pathlib import Path

import click
import pandas as pd
import yaml

from gridpulse import __version__
from gridpulse.detectors import mad_detector, trailing_window_baseline
from gridpulse.evaluation import (
    chronological_split,
    compute_metrics,
    define_proxy_anomaly,
)
from gridpulse.ingestion import (
    build_analysis_table,
    data_quality_summary,
    ingest_merged_csv,
    save_quality_report,
)
from gridpulse.provenance import load_manifest
from gridpulse.reporting import plot_time_series, write_html_report, write_metrics_json


@click.group()
@click.version_option(__version__)
def main() -> None:
    """GridPulse: anomaly detection benchmark for power outages."""


@main.command()
def check_sources() -> None:
    """Check source metadata and data availability."""
    manifest = load_manifest()
    click.echo(json.dumps(manifest, indent=2))
    raw = Path("data/raw")
    if raw.exists():
        click.echo(f"\nRaw files present: {[p.name for p in raw.iterdir()]}")
    else:
        click.echo("No data/raw directory.")


@main.command()
@click.option("--data", type=click.Path(exists=True, path_type=Path), default=None,
              help="Optional analysis-ready Parquet to open on startup.")
@click.option("--demo", is_flag=True,
              help="Auto-play a scripted parameter tour (used for screenshots/video).")
def gui(data: Path | None, demo: bool) -> None:
    """Launch the interactive desktop GUI (Tkinter)."""
    from gridpulse.gui import launch

    launch(demo=demo, data=data)


@main.command()
@click.argument("csv_path", type=click.Path(exists=True, path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), default=Path("data/processed/analysis.parquet"))
def ingest(csv_path: Path, out: Path) -> None:
    """Ingest an explicitly permitted merged outage CSV."""
    click.echo(f"Ingesting {csv_path} ...")
    df = ingest_merged_csv(csv_path)
    ready = build_analysis_table(df, out)
    summary = data_quality_summary(ready)
    save_quality_report(summary, out.parent / "quality_summary.json")
    click.echo(f"Wrote {len(ready)} rows to {out}")
    click.echo(json.dumps(summary, indent=2, default=str))


@main.command()
@click.argument("parquet_path", type=click.Path(exists=True, path_type=Path))
def validate(parquet_path: Path) -> None:
    """Validate and summarize local analysis-ready data."""
    df = pd.read_parquet(parquet_path)
    summary = data_quality_summary(df)
    click.echo(json.dumps(summary, indent=2, default=str))


@main.command()
@click.option("--config", type=click.Path(exists=True, path_type=Path), default=Path("configs/benchmark.yaml"))
@click.option("--data", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out-dir", type=click.Path(path_type=Path), default=Path("experiments/m1"))
@click.option("--synthetic", is_flag=True, help="Use built-in synthetic fixture instead of real data")
def run(config: Path, data: Path | None, out_dir: Path, synthetic: bool) -> None:
    """Run the benchmark (offline, deterministic with fixed seeds)."""
    with config.open() as f:
        cfg = yaml.safe_load(f)

    out_dir.mkdir(parents=True, exist_ok=True)
    seed = cfg.get("random_seed", 42)

    if synthetic or data is None:
        click.echo("Using SYNTHETIC fixture (clearly labeled).")
        df = _make_synthetic(seed)
        is_synthetic = True
    else:
        df = pd.read_parquet(data)
        is_synthetic = False

    # Simple univariate series: mean_customers per observation (already event-level)
    series = df.set_index("start_time")["mean_customers"].sort_index()

    # Proxy labels defined independently
    proxy = define_proxy_anomaly(series, percentile=cfg.get("proxy_percentile", 95.0))

    # Chronological split
    train, val, test = chronological_split(df, train_frac=0.6, val_frac=0.2)
    # Use fixed thresholds from config; in production would tune on val
    baseline = trailing_window_baseline(
        series,
        window=cfg["detectors"]["baseline"]["window"],
        threshold_std=cfg["detectors"]["baseline"]["threshold_std"],
    )
    mad = mad_detector(
        series,
        window=cfg["detectors"]["mad"]["window"],
        threshold_mad=cfg["detectors"]["mad"]["threshold_mad"],
        zero_dispersion_policy=cfg["detectors"]["mad"].get("zero_dispersion_policy", "skip"),
    )

    # Evaluate only on test portion
    test_idx = test["start_time"]
    test_proxy = proxy.reindex(test_idx).fillna(False)
    test_baseline_flags = baseline.flags.reindex(test_idx).fillna(False)
    test_mad_flags = mad.flags.reindex(test_idx).fillna(False)

    m_base = compute_metrics(test_proxy, test_baseline_flags, test_idx)
    m_mad = compute_metrics(test_proxy, test_mad_flags, test_idx)

    results = {
        "is_synthetic": is_synthetic,
        "baseline": m_base.__dict__,
        "mad": m_mad.__dict__,
        "n_train": len(train),
        "n_val": len(val),
        "n_test": len(test),
        "config": cfg,
        "random_seed": seed,
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str))
    write_metrics_json(m_mad, out_dir / "metrics_mad.json")

    # Plot
    plot_path = out_dir / "timeseries.png"
    plot_time_series(df, mad.scores, mad.flags, plot_path)

    limitations = [
        "Proxy labels are defined from the same series (high percentile); agreement is not independent verification.",
        "Event-level records, not continuous 15-minute time series.",
        "No causal claims between weather and outages.",
        "Chronological split used; residual temporal dependence remains.",
        "Synthetic runs are clearly labeled and not real observations.",
    ]
    write_html_report(
        metrics=m_mad.__dict__,
        summary={"n_rows": len(df), "synthetic": is_synthetic},
        limitations=limitations,
        out_path=out_dir / "report.html",
        plot_paths=[plot_path],
    )
    click.echo(f"Benchmark complete. Results in {out_dir}")
    click.echo(f"MAD F1 (proxy): {m_mad.f1:.3f}  FP: {m_mad.n_false_positives}")


def _make_synthetic(seed: int) -> pd.DataFrame:
    """Deterministic synthetic fixture for offline smoke tests."""
    import numpy as np

    rng = np.random.default_rng(seed)
    n = 200
    times = pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC")
    base = rng.normal(200, 50, n).clip(0)
    # Inject a few large anomalies
    base[50] = 5000
    base[120] = 8000
    base[150] = 3500
    df = pd.DataFrame(
        {
            "fips": 1001,
            "state": "SYNTHETIC",
            "county": "SYNTHETIC_COUNTY",
            "start_time": times,
            "duration": 1.0,
            "mean_customers": base,
            "max_customers": base * 1.1,
            "min_customers": base * 0.9,
        }
    )
    return df


if __name__ == "__main__":
    main()
