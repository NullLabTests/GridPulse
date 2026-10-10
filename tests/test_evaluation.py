"""Tests for evaluation: chronological split, no leakage, metrics."""

import pandas as pd
import pytest

from gridpulse.evaluation import (
    chronological_split,
    compute_metrics,
    define_proxy_anomaly,
)


def test_chronological_split_order():
    times = pd.date_range("2020-01-01", periods=100, freq="D")
    df = pd.DataFrame({"start_time": times, "value": range(100)})
    train, val, test = chronological_split(df, train_frac=0.6, val_frac=0.2)
    assert train["start_time"].max() < val["start_time"].min()
    assert val["start_time"].max() < test["start_time"].min()
    assert len(train) == 60
    assert len(val) == 20
    assert len(test) == 20


def test_no_future_in_train():
    times = pd.date_range("2020-01-01", periods=10, freq="D")
    df = pd.DataFrame({"start_time": times, "value": range(10)})
    train, _, test = chronological_split(df, train_frac=0.5, val_frac=0.0)
    assert train["start_time"].max() < test["start_time"].min()


def test_proxy_label_independent():
    s = pd.Series([1, 2, 3, 4, 100])
    labels = define_proxy_anomaly(s, percentile=80.0, min_value=50.0)
    assert labels.iloc[-1]
    assert not labels.iloc[0]


def test_metrics_hand_computed():
    y_true = pd.Series([True, False, True, False])
    y_pred = pd.Series([True, True, False, False])
    m = compute_metrics(y_true, y_pred)
    assert m.n_true_positives == 1
    assert m.n_false_positives == 1
    assert m.n_false_negatives == 1
    assert m.n_true_negatives == 1
    assert m.precision == 0.5
    assert m.recall == 0.5
    assert abs(m.f1 - 0.5) < 1e-6


def test_fp_per_day():
    times = pd.date_range("2020-01-01", periods=10, freq="D")
    y_true = pd.Series([False] * 10)
    y_pred = pd.Series([True] + [False] * 9)
    m = compute_metrics(y_true, y_pred, times)
    assert m.n_false_positives == 1
    assert m.false_positives_per_day > 0
