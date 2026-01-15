"""
Baseline normalization for MEA analysis.

Adds a normalized column (default: value_norm) computed per well and metric
relative to baseline time point (default: 0).

Rules:
- If baseline is NaN -> exclude that well+metric (cannot normalize)
- If baseline is 0 and exclude_zero_baseline=True -> exclude (division invalid / meaningless)
- Exclusions can be kept (with NaN normalized values) or removed entirely.

Expected input columns:
- time_point (int)
- well (str)
- metric (str)
- value_col (float, default "value")
Optional:
- plate_id, condition, etc (preserved)
"""

from __future__ import annotations

from typing import Tuple, Optional
import numpy as np
import pandas as pd


def baseline_normalize(
    df: pd.DataFrame,
    *,
    baseline_time_point: int = 0,
    value_col: str = "value",
    normalized_col: str = "value_norm",
    method: str = "ratio",
    exclude_zero_baseline: bool = True,
    keep_excluded_rows: bool = False,
    return_qc_table: bool = False,
) -> pd.DataFrame | Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Normalize values to baseline per well × metric (and plate if present).

    Parameters
    ----------
    df : pd.DataFrame
        Long-format dataframe (e.g., df_filtered) containing values to normalize.
    baseline_time_point : int
        Time point index used as baseline (typically 0).
    value_col : str
        Column containing raw values.
    normalized_col : str
        Output column name for normalized values.
    method : str
        One of:
        - "ratio": value / baseline  (baseline becomes ~1)
        - "percent": 100 * value / baseline (baseline becomes ~100)
        - "delta": value - baseline (baseline becomes ~0)
    exclude_zero_baseline : bool
        If True, baseline==0 causes exclusion for ratio/percent.
    keep_excluded_rows : bool
        If True, keep excluded well-metric rows in output, but normalized_col is NaN.
        If False, drop excluded well-metric rows entirely.
    return_qc_table : bool
        If True, returns (df_norm, baseline_qc_table).

    Returns
    -------
    df_norm : pd.DataFrame
        DataFrame with normalized_col added.
    baseline_qc_table : pd.DataFrame (optional)
        Table listing excluded well×metric (and plate if present) with reason.
    """
    if method not in {"ratio", "percent", "delta"}:
        raise ValueError("method must be one of: 'ratio', 'percent', 'delta'")

    required = {"time_point", "well", "metric", value_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")

    d = df.copy()

    # Standardize types
    d["well"] = d["well"].astype(str).str.strip().str.upper()
    d["time_point"] = pd.to_numeric(d["time_point"], errors="coerce").astype(int)
    d[value_col] = pd.to_numeric(d[value_col], errors="coerce")

    # If plate_id exists, normalize per plate too (safer when multiple plates are combined)
    key_cols = ["well", "metric"]
    if "plate_id" in d.columns:
        key_cols = ["plate_id"] + key_cols

    # Extract baseline rows
    base = d[d["time_point"] == baseline_time_point][key_cols + [value_col]].copy()
    base = base.rename(columns={value_col: "_baseline_value"})

    # If multiple baseline rows exist for same key, take mean (shouldn't happen, but safe)
    base = base.groupby(key_cols, as_index=False)["_baseline_value"].mean()

    # Merge baseline back
    out = d.merge(base, on=key_cols, how="left")

    # Determine exclusion reason per row
    baseline = out["_baseline_value"]

    reason = pd.Series(index=out.index, dtype="object")

    # Baseline missing
    mask_nan = baseline.isna()
    reason.loc[mask_nan] = "baseline_missing"

    # Baseline zero (only relevant for ratio/percent)
    if method in {"ratio", "percent"} and exclude_zero_baseline:
        mask_zero = (~mask_nan) & (baseline == 0)
        reason.loc[mask_zero] = "baseline_zero"

    out["_baseline_exclusion_reason"] = reason

    # Compute normalized values (only for non-excluded rows)
    ok = out["_baseline_exclusion_reason"].isna()

    out[normalized_col] = np.nan
    if method == "ratio":
        out.loc[ok, normalized_col] = out.loc[ok, value_col] / out.loc[ok, "_baseline_value"]
    elif method == "percent":
        out.loc[ok, normalized_col] = 100.0 * out.loc[ok, value_col] / out.loc[ok, "_baseline_value"]
    elif method == "delta":
        out.loc[ok, normalized_col] = out.loc[ok, value_col] - out.loc[ok, "_baseline_value"]

    # Build QC table: unique excluded keys + reason
    excluded = out[~ok].copy()
    qc_cols = key_cols + ["_baseline_value", "_baseline_exclusion_reason"]
    baseline_qc = (
        excluded[qc_cols]
        .drop_duplicates()
        .rename(columns={
            "_baseline_value": "baseline_value",
            "_baseline_exclusion_reason": "exclusion_reason"
        })
        .sort_values(key_cols)
        .reset_index(drop=True)
    )

    # Drop or keep excluded rows
    if not keep_excluded_rows:
        out = out[ok].copy()

    # Clean helper columns
    out = out.drop(columns=["_baseline_value"], errors="ignore")

    if return_qc_table:
        return out, baseline_qc
    return out
