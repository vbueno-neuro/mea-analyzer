"""
Time-course plotting utilities for MEA analysis.

Expected columns in df:
- plate_id (optional)
- time_point (int)
- well (str)
- condition (str)
- condition_color (optional, hex color like "#1f77b4")
- metric (str)
- value (float)
- value_norm (optional, float)
- is_outlier (optional, bool)

Main features:
- Plot raw or normalized using use_normalized switch
- Plot individual well traces + condition mean±SEM
- Outlier overlay (red dots) if is_outlier exists
- Uses YAML-defined condition_color when available
"""

from __future__ import annotations

from typing import Optional, Dict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _sem(x: pd.Series) -> float:
    """Standard error of the mean (SEM), ignoring NaNs."""
    x = pd.to_numeric(x, errors="coerce").dropna()
    if x.shape[0] <= 1:
        return np.nan
    return x.std(ddof=1) / np.sqrt(x.shape[0])


def plot_metric_timecourse(
    df: pd.DataFrame,
    metric: str,
    plate_id: Optional[str] = None,
    *,
    # Switch-related params
    use_normalized: bool = False,
    value_col: str = "value",
    normalized_col: str = "value_norm",
    # Plot options
    show_individual: bool = True,
    show_mean_sem: bool = True,
    show_outliers: bool = True,
    # Labels
    title: Optional[str] = None,
    y_label: Optional[str] = None,
    timepoint_labels: Optional[Dict[int, str]] = None,
):
    """
    Plot a time-course for one metric, grouped by condition.

    Parameters
    ----------
    df : pd.DataFrame
        Master dataframe (raw or normalized).
    metric : str
        Metric name to plot (must match df['metric'] values).
    plate_id : str, optional
        Filter to one plate.
    use_normalized : bool
        If True, plot normalized_col; else plot value_col.
    value_col : str
        Raw value column name (default "value").
    normalized_col : str
        Normalized value column name (default "value_norm").
    show_individual : bool
        Plot individual well traces (thin lines).
    show_mean_sem : bool
        Plot condition mean ± SEM (error bars).
    show_outliers : bool
        If df has 'is_outlier', overlay flagged points as red dots.
    title : str, optional
        Custom plot title.
    y_label : str, optional
        Custom y-axis label.
    timepoint_labels : dict[int,str], optional
        Map time_point indices to labels (e.g., {0:"Baseline",1:"1h"}).

    Returns
    -------
    matplotlib.figure.Figure
    """
    # Basic schema checks
    required = {"time_point", "condition", "well", "metric"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")

    plot_df = df[df["metric"] == metric].copy()

    if plate_id is not None:
        if "plate_id" not in plot_df.columns:
            raise ValueError("plate_id was provided, but df has no 'plate_id' column.")
        plot_df = plot_df[plot_df["plate_id"] == plate_id].copy()

    # Drop wells not assigned to a condition
    plot_df = plot_df.dropna(subset=["condition"])

    # Switch: choose y column
    if use_normalized:
        if normalized_col not in plot_df.columns:
            raise ValueError(
                f"use_normalized=True but column '{normalized_col}' was not found. "
                "Run baseline_normalize() first or pass the correct normalized_col."
            )
        ycol = normalized_col
    else:
        if value_col not in plot_df.columns:
            raise ValueError(f"Column '{value_col}' was not found in dataframe.")
        ycol = value_col

    # Ensure numeric
    plot_df[ycol] = pd.to_numeric(plot_df[ycol], errors="coerce")

    # Sort for clean lines
    plot_df = plot_df.sort_values(["condition", "well", "time_point"])

    fig, ax = plt.subplots(figsize=(10, 5))

    # Plot each condition
    for cond, gcond in plot_df.groupby("condition"):
        # Determine condition color from YAML if available
        color = None
        if "condition_color" in gcond.columns:
            c = gcond["condition_color"].dropna()
            if not c.empty:
                color = c.iloc[0]

        # Individual well traces
        if show_individual:
            for well, gw in gcond.groupby("well"):
                ax.plot(
                    gw["time_point"].values,
                    gw[ycol].values,
                    linewidth=1,
                    alpha=0.5,
                    color=color,  # same color family for that condition
                )

        # Mean ± SEM per time_point
        if show_mean_sem:
            summary = (
                gcond.groupby("time_point")[ycol]
                .agg(["mean", _sem, "count"])
                .rename(columns={"_sem": "sem"})
                .reset_index()
            )

            ax.errorbar(
                summary["time_point"].values,
                summary["mean"].values,
                yerr=summary["sem"].values,
                linewidth=2.5,
                marker="o",
                capsize=3,
                color=color,
                label=f"{cond} (mean±SEM)",
            )

        # Outlier overlay (red dots)
        if show_outliers and "is_outlier" in gcond.columns:
            gout = gcond[gcond["is_outlier"] == True]
            if not gout.empty:
                ax.scatter(
                    gout["time_point"].values,
                    gout[ycol].values,
                    color="red",
                    s=35,
                    edgecolors="black",
                    linewidths=0.5,
                    zorder=5,
                )

    ax.set_xlabel("Time point")

    if y_label is not None:
        ax.set_ylabel(y_label)
    else:
        mode = "normalized" if use_normalized else "raw"
        ax.set_ylabel(f"{metric} ({mode})")

    if title is None:
        mode = "normalized" if use_normalized else "raw"
        title = f"Time-course ({mode}) — {metric}"
        if plate_id is not None:
            title += f" — plate {plate_id}"
    ax.set_title(title)

    # X tick labels (Baseline, 1h, etc.)
    if timepoint_labels:
        ticks = sorted(plot_df["time_point"].unique())
        ax.set_xticks(ticks)
        ax.set_xticklabels([timepoint_labels.get(int(t), str(t)) for t in ticks])

    ax.legend(loc="best")
    plt.tight_layout()
    plt.show()
    return fig