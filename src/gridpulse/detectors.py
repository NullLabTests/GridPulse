"""Anomaly detectors for GridPulse.

All detectors are retrospective, causal (no future leakage), and CPU-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


@dataclass
class DetectorResult:
    scores: pd.Series
    thresholds: pd.Series
    flags: pd.Series
    name: str
    params: dict


def trailing_window_baseline(
    series: pd.Series,
    window: int = 30,
    threshold_std: float = 3.0,
    min_periods: int = 5,
) -> DetectorResult:
    """Naive baseline: flag points > mean + k * std of trailing window (excluding current)."""
    # Shift so current point is not in the window
    rolling_mean = series.shift(1).rolling(window=window, min_periods=min_periods).mean()
    rolling_std = series.shift(1).rolling(window=window, min_periods=min_periods).std()
    # Handle zero or near-zero std: treat as no dispersion, score 0 unless absolute deviation is large
    scores = (series - rolling_mean) / rolling_std.replace(0, np.nan)
    scores = scores.fillna(0.0)
    # If std was zero and deviation > 0, flag based on absolute
    zero_std = (rolling_std == 0) | rolling_std.isna()
    large_dev = (series - rolling_mean).abs() > threshold_std
    flags = (scores > threshold_std) | (zero_std & large_dev & rolling_mean.notna())
    thresh = pd.Series(threshold_std, index=series.index)
    return DetectorResult(
        scores=scores,
        thresholds=thresh,
        flags=flags,
        name="trailing_window_baseline",
        params={"window": window, "threshold_std": threshold_std, "min_periods": min_periods},
    )


def mad_detector(
    series: pd.Series,
    window: int = 30,
    threshold_mad: float = 5.0,
    min_periods: int = 5,
    zero_dispersion_policy: Literal["skip", "flag_all", "flag_none"] = "skip",
) -> DetectorResult:
    """Robust statistical detector using rolling median and MAD.

    Handles zero dispersion and insufficient history explicitly.
    """
    shifted = series.shift(1)
    rolling_median = shifted.rolling(window=window, min_periods=min_periods).median()
    # MAD = median(|x - median|)
    def _mad(x: np.ndarray) -> float:
        if len(x) < min_periods or np.all(np.isnan(x)):
            return np.nan
        med = np.nanmedian(x)
        return float(np.nanmedian(np.abs(x - med)))

    rolling_mad = shifted.rolling(window=window, min_periods=min_periods).apply(
        _mad, raw=True
    )
    # Modified z-score: 0.6745 * (x - med) / MAD
    scores = 0.6745 * (series - rolling_median) / rolling_mad
    scores = scores.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    flags = scores > threshold_mad

    # Explicit zero-dispersion handling
    zero_disp = rolling_mad == 0
    if zero_dispersion_policy == "flag_all":
        flags = flags | zero_disp
    elif zero_dispersion_policy == "flag_none":
        flags = flags & ~zero_disp
    # "skip" leaves flags as computed (scores become nan -> 0, so not flagged)

    insufficient = rolling_median.isna()
    flags = flags & ~insufficient  # do not flag without history

    thresh = pd.Series(threshold_mad, index=series.index)
    return DetectorResult(
        scores=scores,
        thresholds=thresh,
        flags=flags,
        name="mad_detector",
        params={
            "window": window,
            "threshold_mad": threshold_mad,
            "min_periods": min_periods,
            "zero_dispersion_policy": zero_dispersion_policy,
        },
    )


def isolation_forest_detector(
    features: pd.DataFrame,
    contamination: float = 0.05,
    random_state: int = 42,
    n_estimators: int = 100,
) -> DetectorResult | None:
    """Optional Isolation Forest. Returns None if scikit-learn unavailable."""
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return None

    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
        n_estimators=n_estimators,
        n_jobs=1,
    )
    # Fit only on training portion; caller must ensure no leakage
    preds = model.fit_predict(features.fillna(0))
    scores = -model.decision_function(features.fillna(0))  # higher = more anomalous
    flags = preds == -1
    return DetectorResult(
        scores=pd.Series(scores, index=features.index),
        thresholds=pd.Series(0.0, index=features.index),  # model-internal
        flags=pd.Series(flags, index=features.index),
        name="isolation_forest",
        params={
            "contamination": contamination,
            "random_state": random_state,
            "n_estimators": n_estimators,
        },
    )
