# GridPulse M1 Preregistration

**Version:** 0.1.0  
**Date:** 2026-10-10  
**Status:** Preregistered before full real-data evaluation

## Research Question

Can lightweight statistical anomaly detectors identify unusually large or rapidly increasing county-level power outages, and how do their detection performance and false-alarm rates compare against simple baselines?

This is retrospective anomaly detection. No claim of operational forecasting or causal weather-outage relationships is made.

## Observation Unit

County-level outage event records (merged format) containing start_time and mean_customers (or equivalent magnitude).

## Anomaly-Label Definition (Proxy)

A transparent operational definition:

- A record is labeled as a proxy anomaly if its mean_customers exceeds the 95th percentile of the eligible historical series **or** an absolute threshold of 1000 customers, whichever is larger.
- Labels are computed independently of any detector predictions.
- Agreement with these proxy labels is reported as such; it is **not** real-world predictive accuracy against independently verified events.

## Evaluation Splits

Chronological:

- Train: first 60% of ordered timestamps
- Validation: next 20%
- Test: final 20%

Thresholds and parameters are fixed in config or tuned only on train+validation. No future observations influence past predictions.

## Metrics

- Precision, Recall, F1
- Number of true positives, false positives, false negatives
- False positives per day (denominator = span of test timestamps in days)
- Detection delay (median hours from event start to first flag, where applicable)

## Baselines and Detectors

1. **Naive trailing-window baseline**: mean + k·std of prior window (current point excluded).
2. **Robust MAD detector**: rolling median + modified z-score with MAD; explicit handling of zero dispersion and insufficient history.
3. Optional: Isolation Forest (only if scikit-learn present and fair evaluation possible).

## Exclusion Criteria

- Records with missing start_time or negative customer counts are rejected at ingestion.
- Points with insufficient historical context (min_periods) are not flagged.
- Zero-dispersion windows follow the configured policy.

## Known Limitations

- Dataset provides event-level aggregates, not continuous 15-minute customer-outage time series.
- Proxy labels are derived from the same magnitude series; high agreement is expected and does not demonstrate external validity.
- Temporal and spatial dependence violate independence assumptions for simple confidence intervals.
- No authoritative anomaly labels exist in the public dataset; event-correlated fields must not be used as features when evaluating detection of those events.
- Licensing verified as CC BY 4.0; redistribution requires attribution.

## Methodological Changes

Any deviation from this document will be recorded in `docs/changelog.md` with rationale and date. The original preregistration remains immutable in Git history.
