# Limitations

1. **Proxy labels only**. The public dataset does not contain independent, authoritative anomaly labels. High agreement with percentile-based proxy labels is expected and does not demonstrate external validity or operational skill.

2. **Event-level, not continuous series**. The processed OpenEI files contain outage events with start times and customer counts, not the original 15-minute county time series. Rapid-increase detection is therefore limited to differences between successive events.

3. **No future leakage by design**, but residual temporal dependence remains. Simple confidence intervals would be optimistic.

4. **Zero vs missing**. Zero customer counts are treated as valid observations. Missing values are rejected.

5. **Licensing**. Code is MIT. Data is CC BY 4.0; attribution required on redistribution.

6. **Synthetic fixtures** are deterministic and clearly labeled. Never interpret synthetic results as real-world performance.

7. **No GPU, no external APIs**. All computation is local and CPU-only.
