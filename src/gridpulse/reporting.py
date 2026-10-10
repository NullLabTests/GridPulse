"""Reporting and simple static plot generation for GridPulse."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from gridpulse.evaluation import Metrics


def plot_time_series(
    df: pd.DataFrame,
    scores: pd.Series,
    flags: pd.Series,
    out_path: Path,
    title: str = "Outage time series and detector scores",
) -> None:
    """Generate a simple static plot of outages, scores, and flags."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax0, ax1 = axes

    if "mean_customers" in df.columns and "start_time" in df.columns:
        ax0.plot(df["start_time"], df["mean_customers"], label="mean_customers", alpha=0.7)
        ax0.set_ylabel("Customers")
        ax0.legend()
    ax0.set_title(title)

    ax1.plot(scores.index if hasattr(scores, "index") else range(len(scores)), scores, label="score", color="C1")
    flagged = scores[flags]
    if len(flagged):
        ax1.scatter(
            flagged.index if hasattr(flagged, "index") else range(len(flagged)),
            flagged,
            color="red",
            s=20,
            label="flagged",
            zorder=5,
        )
    ax1.set_ylabel("Score")
    ax1.legend()
    ax1.set_xlabel("Time / Index")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


def write_metrics_json(metrics: Metrics, path: Path) -> None:
    data = {
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "n_true_positives": metrics.n_true_positives,
        "n_false_positives": metrics.n_false_positives,
        "n_false_negatives": metrics.n_false_negatives,
        "n_true_negatives": metrics.n_true_negatives,
        "false_positives_per_day": metrics.false_positives_per_day,
        "n_evaluated": metrics.n_evaluated,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)


def write_html_report(
    metrics: dict[str, Any],
    summary: dict[str, Any],
    limitations: list[str],
    out_path: Path,
    plot_paths: list[Path] | None = None,
) -> None:
    """Write a compact self-contained HTML report."""
    plot_html = ""
    if plot_paths:
        for p in plot_paths:
            plot_html += f'<p><img src="{p.name}" alt="plot" style="max-width:100%"></p>\n'

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>GridPulse M1 Report</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; }}
table {{ border-collapse: collapse; }}
td, th {{ border: 1px solid #ccc; padding: 0.4em 0.8em; }}
.warn {{ background: #fff3cd; padding: 0.5em; }}
</style>
</head>
<body>
<h1>GridPulse M1 — Anomaly Detection Benchmark</h1>
<p><strong>Note:</strong> All results below are based on proxy labels defined independently of model predictions. They do not constitute real-world predictive accuracy or causal claims.</p>

<h2>Data Summary</h2>
<pre>{json.dumps(summary, indent=2, default=str)}</pre>

<h2>Metrics (proxy labels)</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Precision</td><td>{metrics.get('precision', 'N/A'):.3f}</td></tr>
<tr><td>Recall</td><td>{metrics.get('recall', 'N/A'):.3f}</td></tr>
<tr><td>F1</td><td>{metrics.get('f1', 'N/A'):.3f}</td></tr>
<tr><td>False positives</td><td>{metrics.get('n_false_positives', 'N/A')}</td></tr>
<tr><td>True positives</td><td>{metrics.get('n_true_positives', 'N/A')}</td></tr>
<tr><td>FP per day</td><td>{metrics.get('false_positives_per_day', 'N/A'):.3f}</td></tr>
<tr><td>N evaluated</td><td>{metrics.get('n_evaluated', 'N/A')}</td></tr>
</table>

<h2>Plots</h2>
{plot_html}

<h2>Known Limitations</h2>
<ul>
{''.join(f'<li>{lim}</li>' for lim in limitations)}
</ul>

<p class="warn">Synthetic fixtures are clearly labeled. Real-data results require verified local ingestion.</p>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
