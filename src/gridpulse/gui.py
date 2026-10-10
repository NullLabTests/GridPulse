"""Tkinter desktop front-end for GridPulse.

A dependency-free (stdlib Tkinter + already-required matplotlib) GUI that lets a
user load a series, tune detector parameters, run the benchmark and inspect both
the detections and the proxy-agreement metrics interactively.

The GUI deliberately reuses the same detector / evaluation code as the CLI so
that whatever is shown on screen is exactly what the reproducible pipeline
computes. The GUI is an exploration and communication surface; the CLI remains
the source of record for archived results.
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("TkAgg")
import tkinter as tk
from contextlib import suppress
from tkinter import filedialog, ttk
from typing import Literal, cast

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from gridpulse.detectors import DetectorResult, mad_detector, trailing_window_baseline
from gridpulse.evaluation import (
    chronological_split,
    compute_metrics,
    define_proxy_anomaly,
)
from gridpulse.ingestion import data_quality_summary

# Palette
INK = "#0f172a"
MUTED = "#64748b"
PANEL = "#f1f5f9"
CARD = "#ffffff"
ACCENT = "#0ea5e9"
ACCENT_DARK = "#0369a1"
FLAG = "#dc2626"
PROXY = "#f59e0b"
OK = "#16a34a"

LIMITATIONS = [
    "Proxy labels are percentile-based and derived from the same series; agreement",
    "is not independent verification against authoritative outage events.",
    "Event-level records, not a continuous 15-minute county time series.",
    "No causal claims between weather and outages. CPU-only, fully offline.",
]


def make_demo_frame(seed: int = 42, n: int = 365) -> pd.DataFrame:
    """Deterministic, clearly-labeled synthetic series used for the GUI demo.

    Seasonal baseline plus a handful of injected multi-county outage spikes so
    the visualization has something meaningful to flag. Never real data.
    """
    rng = np.random.default_rng(seed)
    times = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    doy = np.arange(n)
    baseline = (
        280
        + 90 * np.sin(2 * np.pi * doy / 365.0)
        + 40 * np.sin(2 * np.pi * doy / 30.0)
        + rng.normal(0, 18, n)
    ).clip(20)

    spike_days = [40, 92, 140, 141, 205, 260, 300, 301, 302, 350]
    spike_mag = [4200, 3100, 6800, 2400, 5200, 3600, 7100, 3900, 2700, 6000]
    for d, m in zip(spike_days, spike_mag, strict=True):
        baseline[d] += m

    return pd.DataFrame(
        {
            "fips": 1001,
            "state": "SYNTHETIC",
            "county": "SYNTHETIC_COUNTY",
            "start_time": times,
            "duration": 1.0,
            "mean_customers": baseline,
            "max_customers": baseline * 1.1,
            "min_customers": baseline * 0.9,
        }
    )


class GridPulseGUI:
    def __init__(self, root: tk.Tk, data_path: Path | None = None) -> None:
        self.root = root
        self.root.title("GridPulse Studio — outage anomaly detection benchmark")
        self.root.geometry("1340x840+40+40")
        self.root.minsize(1080, 700)
        self.root.configure(bg=PANEL)

        self._df: pd.DataFrame = make_demo_frame()
        self._source_label = "Synthetic demo fixture (clearly labeled, not real data)"
        self._last: dict = {}

        # --- state variables -------------------------------------------------
        self.source_mode = tk.StringVar(value="synthetic")
        self.data_path: Path | None = data_path
        if data_path is not None:
            self.source_mode.set("file")
            self._load_df(data_path)

        self.use_baseline = tk.BooleanVar(value=True)
        self.use_mad = tk.BooleanVar(value=True)
        self.baseline_k = tk.DoubleVar(value=3.0)
        self.mad_k = tk.DoubleVar(value=5.0)
        self.window = tk.IntVar(value=30)
        self.zero_policy = tk.StringVar(value="skip")
        self.proxy_pct = tk.DoubleVar(value=95.0)
        self.eval_mode = tk.StringVar(value="holdout")

        self._build_style()
        self._build_layout()
        self._draw()

    # ------------------------------------------------------------------ style
    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        with suppress(tk.TclError):
            style.theme_use("clam")
        style.configure("TFrame", background=PANEL)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=PANEL, foreground=INK, font=("Helvetica", 10))
        style.configure("Card.TLabel", background=CARD, foreground=INK)
        style.configure("Section.TLabel", background=PANEL, foreground=ACCENT_DARK,
                        font=("Helvetica", 10, "bold"))
        style.configure("TCheckbutton", background=PANEL, foreground=INK)
        style.configure("TRadiobutton", background=PANEL, foreground=INK)
        style.configure("TButton", font=("Helvetica", 10))
        style.configure("Accent.TButton", font=("Helvetica", 11, "bold"),
                        foreground="white", background=ACCENT)
        style.map("Accent.TButton",
                  background=[("active", ACCENT_DARK), ("!active", ACCENT)])
        style.configure("TLabelframe", background=PANEL)
        style.configure("TLabelframe.Label", background=PANEL, foreground=INK,
                        font=("Helvetica", 10, "bold"))

    # ----------------------------------------------------------------- layout
    def _build_layout(self) -> None:
        header = tk.Frame(self.root, bg=INK, height=64)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="GridPulse Studio", bg=INK, fg="white",
                 font=("Helvetica", 17, "bold")).pack(side=tk.LEFT, padx=18, pady=(10, 0))
        tk.Label(header, text="  reproducible, offline anomaly detection for county-level power outages",
                 bg=INK, fg="#94a3b8", font=("Helvetica", 10)).pack(side=tk.LEFT, pady=(14, 0))

        body = tk.Frame(self.root, bg=PANEL)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self._build_sidebar(body)

        right = tk.Frame(body, bg=PANEL)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12), pady=12)

        chart_card = tk.Frame(right, bg=CARD)
        chart_card.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.fig = Figure(figsize=(8.6, 5.4), dpi=100, facecolor=CARD)
        self.ax0 = self.fig.add_subplot(211)
        self.ax1 = self.fig.add_subplot(212, sharex=self.ax0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_card)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        bottom = tk.Frame(right, bg=PANEL)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        self._metrics_bar = tk.Frame(bottom, bg=PANEL)
        self._metrics_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._build_metric_cards()

    def _build_sidebar(self, parent: tk.Frame) -> None:
        side = tk.Frame(parent, bg=PANEL, width=336)
        side.pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=12)
        side.pack_propagate(False)

        # Data source
        src = ttk.Labelframe(side, text="1 · Data source")
        src.pack(fill=tk.X, pady=(0, 8))
        ttk.Radiobutton(src, text="Synthetic demo (labeled, offline)", value="synthetic",
                        variable=self.source_mode, command=self._on_source_change).pack(
            anchor="w", padx=8, pady=(4, 0))
        row = tk.Frame(src, bg=PANEL)
        row.pack(anchor="w", fill=tk.X, padx=8, pady=(0, 6))
        ttk.Radiobutton(row, text="Load Parquet (ingested)", value="file",
                        variable=self.source_mode, command=self._on_source_change).pack(side=tk.LEFT)
        ttk.Button(row, text="Browse…", command=self._browse).pack(side=tk.LEFT, padx=6)
        self.source_lbl = ttk.Label(src, text=self._source_label, wraplength=300,
                                    foreground=MUTED, font=("Helvetica", 8))
        self.source_lbl.pack(anchor="w", padx=8, pady=(0, 6))

        # Detectors
        det = ttk.Labelframe(side, text="2 · Detectors")
        det.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(det, text="Trailing-window baseline (mean + k·std)",
                        variable=self.use_baseline).pack(anchor="w", padx=8, pady=(4, 0))
        self._slider(det, "baseline k", self.baseline_k, 1.0, 8.0, 0.5)
        ttk.Checkbutton(det, text="Robust MAD (rolling median + modified z)",
                        variable=self.use_mad).pack(anchor="w", padx=8, pady=(6, 0))
        self._slider(det, "MAD k", self.mad_k, 1.0, 12.0, 0.5)
        ttk.Label(det, text="Rolling window (days)", foreground=MUTED).pack(anchor="w", padx=8, pady=(6, 0))
        ttk.Scale(det, from_=5, to=90, variable=self.window, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=8)
        prow = tk.Frame(det, bg=PANEL)
        prow.pack(anchor="w", fill=tk.X, padx=8, pady=(4, 6))
        ttk.Label(prow, text="Zero-dispersion:").pack(side=tk.LEFT)
        ttk.Combobox(prow, textvariable=self.zero_policy, width=11, state="readonly",
                     values=["skip", "flag_all", "flag_none"]).pack(side=tk.LEFT, padx=6)

        # Proxy labels
        prox = ttk.Labelframe(side, text="3 · Proxy anomaly labels")
        prox.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(prox, text="Percentile threshold", foreground=MUTED).pack(anchor="w", padx=8, pady=(4, 0))
        ttk.Scale(prox, from_=80, to=99.9, variable=self.proxy_pct, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=8)
        ttk.Label(prox, text="Labels are computed independently of the detectors.",
                  foreground=MUTED, wraplength=300, font=("Helvetica", 8)).pack(
            anchor="w", padx=8, pady=(2, 6))

        # Evaluation
        ev = ttk.Labelframe(side, text="4 · Evaluate on")
        ev.pack(fill=tk.X, pady=(0, 8))
        ttk.Radiobutton(ev, text="Holdout (final 20%, leakage-free)",
                        value="holdout", variable=self.eval_mode).pack(anchor="w", padx=8, pady=(4, 0))
        ttk.Radiobutton(ev, text="Full series (illustrative)",
                        value="full", variable=self.eval_mode).pack(anchor="w", padx=8, pady=(0, 6))

        ttk.Button(side, text="▶  Run benchmark", style="Accent.TButton",
                   command=self.run_benchmark).pack(fill=tk.X, pady=(2, 6))
        self.status = ttk.Label(side, text="Ready.", foreground=MUTED, wraplength=310)
        self.status.pack(anchor="w")

        lim = ttk.Labelframe(side, text="Limitations")
        lim.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(lim, text="\n".join(LIMITATIONS), foreground=MUTED,
                  font=("Helvetica", 8), wraplength=310, justify=tk.LEFT).pack(
            anchor="w", padx=8, pady=6)

    def _slider(self, parent, label, var, lo, hi, step) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill=tk.X, padx=8, pady=(2, 0))
        ttk.Label(row, text=label, foreground=MUTED, width=10).pack(side=tk.LEFT)
        val = ttk.Label(row, textvariable=var, foreground=INK, width=5)
        val.pack(side=tk.RIGHT)
        ttk.Scale(row, from_=lo, to=hi, variable=var, orient=tk.HORIZONTAL).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 6))

    def _build_metric_cards(self) -> None:
        self._card_widgets: dict[str, tk.Label] = {}
        specs = [("f1", "F1"), ("precision", "Precision"), ("recall", "Recall"),
                 ("tp", "True pos"), ("fp", "False pos"), ("fn", "False neg"),
                 ("fp_per_day", "FP / day"), ("n", "Evaluated")]
        for i, (key, title) in enumerate(specs):
            card = tk.Frame(self._metrics_bar, bg=CARD, highlightbackground="#e2e8f0",
                            highlightthickness=1)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            self._metrics_bar.grid_columnconfigure(i, weight=1)
            tk.Label(card, text=title.upper(), bg=CARD, fg=MUTED,
                     font=("Helvetica", 7, "bold")).pack(padx=8, pady=(5, 0))
            v = tk.Label(card, text="—", bg=CARD, fg=INK, font=("Helvetica", 15, "bold"))
            v.pack(padx=8, pady=(0, 5))
            self._card_widgets[key] = v

    # ------------------------------------------------------------- data logic
    def _on_source_change(self) -> None:
        if self.source_mode.get() == "synthetic":
            self._df = make_demo_frame()
            self._source_label = "Synthetic demo fixture (clearly labeled, not real data)"
        else:
            if self.data_path is None:
                self._browse()
                if self.data_path is None:
                    self.source_mode.set("synthetic")
                    return
            self._load_df(self.data_path)
        self.source_lbl.configure(text=self._source_label)
        self._draw()

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select analysis-ready Parquet",
            filetypes=[("Parquet", "*.parquet"), ("All files", "*.*")])
        if path:
            self._load_df(Path(path))

    def _load_df(self, path: Path) -> None:
        try:
            df = pd.read_parquet(path)
            df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
        except Exception as exc:  # pragma: no cover - UI feedback
            self.status.configure(text=f"Could not load {path.name}: {exc}", foreground=FLAG)
            return
        self._df = df
        self.data_path = path
        self._source_label = f"Local file: {path.name} ({len(df)} rows)"
        if hasattr(self, "source_lbl"):
            self.source_lbl.configure(text=self._source_label)
        self.source_mode.set("file")

    def _series(self) -> pd.Series:
        return self._df.set_index("start_time")["mean_customers"].sort_index()

    def run_benchmark(self) -> None:
        df = self._df
        series = self._series()
        win = int(self.window.get())
        proxy = define_proxy_anomaly(series, percentile=float(self.proxy_pct.get()))

        detections: dict[str, DetectorResult] = {}
        if self.use_baseline.get():
            detections["baseline"] = trailing_window_baseline(
                series, window=win, threshold_std=float(self.baseline_k.get()))
        if self.use_mad.get():
            policy = cast(Literal["skip", "flag_all", "flag_none"], self.zero_policy.get())
            detections["mad"] = mad_detector(
                series, window=win, threshold_mad=float(self.mad_k.get()),
                zero_dispersion_policy=policy)

        if self.eval_mode.get() == "holdout":
            _, _, test = chronological_split(df, train_frac=0.6, val_frac=0.2)
            idx = pd.DatetimeIndex(test["start_time"].sort_values())
            split_label = "holdout (final 20% of ordered timestamps)"
        else:
            idx = series.index
            split_label = "full series (illustrative)"

        metrics = {}
        for name, res in detections.items():
            m = compute_metrics(proxy.reindex(idx).fillna(False),
                                res.flags.reindex(idx).fillna(False), pd.Series(idx))
            metrics[name] = m

        primary = detections.get("mad") or detections.get("baseline")
        summary = data_quality_summary(df)
        self._last = {
            "detections": detections, "metrics": metrics, "proxy": proxy,
            "primary": primary, "split": split_label, "summary": summary, "series": series,
        }
        self._update_cards()
        self._draw()
        n_flag = int(primary.flags.reindex(idx).fillna(False).sum()) if primary is not None else 0
        names = ", ".join(detections) or "none"
        self.status.configure(
            text=f"Ran {names} · window={win}d · {split_label} · flags in eval set: {n_flag}",
            foreground=OK)

    # --------------------------------------------------------------- rendering
    def _update_cards(self) -> None:
        m = self._last["metrics"].get("mad") or self._last["metrics"].get("baseline")
        cards = self._last and {  # type: ignore[assignment]
            "f1": f"{m.f1:.2f}", "precision": f"{m.precision:.2f}", "recall": f"{m.recall:.2f}",
            "tp": str(m.n_true_positives), "fp": str(m.n_false_positives),
            "fn": str(m.n_false_negatives), "fp_per_day": f"{m.false_positives_per_day:.2f}",
            "n": str(m.n_evaluated),
        } if m else {}
        for key, w in self._card_widgets.items():
            w.configure(text=cards.get(key, "—"))

    def _draw(self) -> None:
        if not self._last:
            series = self._series()
            self.ax0.clear()
            self.ax1.clear()
            self.ax0.plot(series.index, series.values, color=ACCENT, lw=1.3)
            self.ax0.set_title("Mean customers per outage event", fontsize=10, loc="left")
            self.ax1.set_title("Detector score (run to populate)", fontsize=10, loc="left")
            self._finish_axes()
            self.canvas.draw()
            return

        series = self._last["series"]
        proxy = self._last["proxy"]
        primary = self._last["primary"]
        dets = self._last["detections"]

        self.ax0.clear()
        self.ax1.clear()

        self.ax0.plot(series.index, series.values, color=ACCENT, lw=1.3, label="mean_customers")
        praw = series[proxy]
        if len(praw):
            self.ax0.scatter(praw.index, praw.values, marker="s", s=42, facecolors="none",
                             edgecolors=PROXY, linewidths=1.4, label="proxy anomaly", zorder=4)
        for name, res in dets.items():
            f = series[res.flags]
            if len(f):
                self.ax0.scatter(f.index, f.values, color=FLAG, s=26, zorder=5,
                                 label=f"{name} flag")
        self.ax0.set_title(
            f"Outage magnitude — {self._source_label.split('(')[0].strip()}",
            fontsize=10, loc="left")
        self.ax0.legend(loc="upper left", fontsize=8, frameon=False)
        self.ax0.set_ylabel("customers", fontsize=8)

        if primary is not None:
            self.ax1.plot(primary.scores.index, primary.scores.values,
                          color="#7c3aed", lw=1.2, label=f"{primary.name} score")
            self.ax1.axhline(float(primary.thresholds.iloc[0]), color="#94a3b8",
                             ls="--", lw=1, label="threshold")
            self.ax1.fill_between(primary.scores.index, primary.scores.values,
                                  float(primary.thresholds.iloc[0]),
                                  where=(primary.scores.values > float(primary.thresholds.iloc[0])),
                                  color=FLAG, alpha=0.25)
        self.ax1.set_title("Detector score & threshold (shifted rolling window — no leakage)",
                           fontsize=10, loc="left")
        self.ax1.set_ylabel("score", fontsize=8)
        self.ax1.legend(loc="upper left", fontsize=8, frameon=False)

        self._finish_axes()
        self.canvas.draw()

    def _finish_axes(self) -> None:
        for ax in (self.ax0, self.ax1):
            ax.set_facecolor("#fbfdff")
            ax.grid(True, color="#e2e8f0", lw=0.6)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            for s in ("left", "bottom"):
                ax.spines[s].set_color("#cbd5e1")
        self.fig.tight_layout(pad=1.6)

    # -------------------------------------------------------------- demo tour
    def start_demo_tour(self) -> None:
        """Scripted sequence used to produce README screenshots / video."""
        steps = [
            (700, self._demo_step1),
            (2600, self._demo_step2),
            (2600, self._demo_step3),
            (2600, self._demo_step4),
        ]

        def schedule(i: int) -> None:
            if i >= len(steps):
                self.status.configure(text="Demo tour complete.", foreground=OK)
                return None
            delay, fn = steps[i]

            def next_step() -> None:
                fn()
                schedule(i + 1)

            self.root.after(delay, next_step)

        schedule(0)

    def _demo_step1(self) -> None:
        self.source_mode.set("synthetic")
        self.use_baseline.set(True)
        self.use_mad.set(False)
        self.baseline_k.set(3.0)
        self.eval_mode.set("full")
        self.run_benchmark()

    def _demo_step2(self) -> None:
        self.use_mad.set(True)
        self.mad_k.set(5.0)
        self.window.set(30)
        self.run_benchmark()

    def _demo_step3(self) -> None:
        self.mad_k.set(8.0)
        self.run_benchmark()

    def _demo_step4(self) -> None:
        self.mad_k.set(5.0)
        self.window.set(60)
        self.eval_mode.set("holdout")
        self.run_benchmark()


def launch(demo: bool = False, data: Path | None = None) -> None:
    """Entry point used by the ``gridpulse gui`` command."""
    root = tk.Tk()
    app = GridPulseGUI(root, data_path=data)
    if demo or os.environ.get("GRIDPULSE_GUI_DEMO") == "1":
        app.start_demo_tour()
    root.mainloop()
