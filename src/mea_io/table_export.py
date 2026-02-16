"""
Export MEA tables in Prism-friendly format.

Exports one CSV per metric:
- rows = time_point
- columns = wells
- values = raw (value) or normalized (value_norm)

Designed to work with your master_df schema:
plate_id, time_point, well, metric, value, value_norm (optional)

Metrics exported are taken from metrics_config.yaml via ConfigHandler,
so you don't hardcode them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Literal

import pandas as pd


def _safe_filename(s: str) -> str:
    """Make a safe filename chunk."""
    return (
        s.replace(" ", "_")
         .replace("/", "-")
         .replace("(", "")
         .replace(")", "")
         .replace(":", "")
         .replace(",", "")
    )


def export_metric_tables_wide(
    df: pd.DataFrame,
    *,
    out_dir: str | Path,
    config_handler,  # ConfigHandler instance
    mode: Literal["raw", "normalized"] = "raw",
    plate_id: Optional[str] = None,
    value_col_raw: str = "value",
    value_col_norm: str = "value_norm",
    include_timepoint_label: bool = True,
    timepoint_labels: Optional[Dict[int, str]] = None,
    drop_unassigned_wells: bool = True,
) -> Path:
    """
    Export one wide CSV per metric (Prism-friendly).

    Parameters
    ----------
    df : DataFrame
        master_df or df_norm (normalized must contain value_norm if mode="normalized")
    out_dir : Path
        Base output directory (e.g., PROJECT_ROOT / "data" / "processed")
    config_handler : ConfigHandler
        Used to retrieve the list of metrics from metrics_config.yaml
    mode : "raw" or "normalized"
    plate_id : optional
        Filter to a single plate if df contains multiple plates
    include_timepoint_label : bool
        If True, include a "time_label" column if labels provided
    timepoint_labels : dict[int,str]
        Map time_point -> label (Baseline, 1h, etc)
    drop_unassigned_wells : bool
        If True, drop rows where condition is NaN (if condition exists)

    Returns
    -------
    Path : directory where files were written
    """
    out_dir = Path(out_dir)

    # Choose value column
    if mode == "raw":
        value_col = value_col_raw
    elif mode == "normalized":
        value_col = value_col_norm
        if value_col not in df.columns:
            raise ValueError(
                f"mode='normalized' but '{value_col}' not found. "
                "Run baseline_normalize() first."
            )
    else:
        raise ValueError("mode must be 'raw' or 'normalized'")

    required = {"time_point", "well", "metric", value_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")

    d = df.copy()

    # Optional drop unassigned wells
    if drop_unassigned_wells and "condition" in d.columns:
        d = d.dropna(subset=["condition"])

    # Optional plate filter
    if plate_id is not None:
        if "plate_id" not in d.columns:
            raise ValueError("plate_id filter given but df has no 'plate_id' column")
        d = d[d["plate_id"] == plate_id].copy()

    # Determine plate_id for folder naming
    plate_name = plate_id
    if plate_name is None:
        plate_name = d["plate_id"].iloc[0] if "plate_id" in d.columns and not d.empty else "Plate"

    # Output directory structure
    write_dir = out_dir / str(plate_name) / mode
    write_dir.mkdir(parents=True, exist_ok=True)

    # Metrics to export (from config)
    metrics = config_handler.get_all_metrics()

    # Export
    written = 0
    for metric_name in metrics:
        sub = d[d["metric"] == metric_name].copy()
        if sub.empty:
            continue

        wide = sub.pivot_table(
            index="time_point",
            columns="well",
            values=value_col,
            aggfunc="mean",  # should be unique anyway; mean is safe fallback
        ).sort_index()

        # Optional time label column
        if include_timepoint_label and timepoint_labels:
            wide.insert(
                0,
                "time_label",
                [timepoint_labels.get(int(tp), str(tp)) for tp in wide.index]
            )

        # Prism prefers blanks over "NaN"
        # When writing CSV, NaNs will become empty cells automatically.
        fname = f"{_safe_filename(str(plate_name))}__{mode}__{_safe_filename(metric_name)}.csv"
        out_path = write_dir / fname
        wide.to_csv(out_path)

        written += 1

    if written == 0:
        raise ValueError("No metric tables were exported. Check metric names and df contents.")

    return write_dir