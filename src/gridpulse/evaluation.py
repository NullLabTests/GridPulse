"""Evaluation metrics and chronological splitting for GridPulse.

Proxy labels are explicitly distinguished from ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class Metrics:
    precision: float
    recall: float
    f1: float
    n_true_positives: int
    n_false_positives: int
    n_false_negatives: int
    n_true_negatives: int
    false_positives_per_day: float
    n_evaluated: int


def chronological_split(
    df: pd.DataFrame,
    time_col: str = "start_time",
    train_frac: float = 0.6,
    val_frac: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chronological train/val/test split. No future leakage."""
    df = df.sort_values(time_col).reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


def define_proxy_anomaly(
    series: pd.Series,
    percentile: float = 95.0,
    min_value: float = 1000.0,
) -> pd.Series:
    """Transparent operational definition of proxy anomaly labels.

    A point is a proxy anomaly if it exceeds the historical percentile
    of eligible observations OR exceeds an absolute magnitude threshold.
    Labels are defined independently of any model predictions.
    """
    thresh = np.nanpercentile(series.dropna(), percentile)
    return (series >= max(thresh, min_value)).astype(bool)


def compute_metrics(
    y_true: pd.Series,
    y_pred: pd.Series,
    timestamps: pd.Series | None = None,
) -> Metrics:
    """Compute precision, recall, F1, and false-positive rate."""
    y_true = y_true.astype(bool)
    y_pred = y_pred.astype(bool)
    tp = int((y_true & y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    tn = int((~y_true & ~y_pred).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    n_days = 1.0
    if timestamps is not None and len(timestamps) > 1:
        span = (timestamps.max() - timestamps.min()).total_seconds() / 86400.0
        n_days = max(span, 1.0)
    fp_per_day = fp / n_days

    return Metrics(
        precision=precision,
        recall=recall,
        f1=f1,
        n_true_positives=tp,
        n_false_positives=fp,
        n_false_negatives=fn,
        n_true_negatives=tn,
        false_positives_per_day=fp_per_day,
        n_evaluated=len(y_true),
    )


def detection_delay(
    y_true: pd.Series,
    y_pred: pd.Series,
    timestamps: pd.Series,
) -> float | None:
    """Median detection delay (in hours) for true events that were detected."""
    delays = []
    true_times = timestamps[y_true]
    for t in true_times:
        detections = timestamps[y_pred & (timestamps >= t)]
        if len(detections):
            delay_h = (detections.min() - t).total_seconds() / 3600.0
            delays.append(delay_h)
    return float(np.median(delays)) if delays else None
