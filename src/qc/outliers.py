"""
Outlier detection and handling utilities for MEA analysis.

Design principles:
- Outliers are FLAGGED, not automatically removed
- Detection is cross-sectional: within each time point
- User decides what to exclude later
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import numpy as np
import pandas as pd


# -------------------------
# Configuration container
# -------------------------
@dataclass(frozen=True)
class OutlierSpec:
    method: str = "zscore"  # "zscore" or "robust_zscore"
    threshold: float = 3.0
    min_group_n: int = 3
    group_cols: Tuple[str, ...] = ("plate_id", "metric", "condition", "time_point")
    value_col: str = "value"


# -------------------------
# Internal helpers
# -------------------------
def _check_required_columns(df: pd.DataFrame, cols: Iterable[str]) -> None:
    missing = set(cols) - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {sorted(missing)}")


# -------------------------
# Main API
# -------------------------
def flag_outliers(
    df: pd.DataFrame,
    spec: OutlierSpec = OutlierSpec(),
) -> pd.DataFrame:
    """
    Flag outliers using z-score or robust z-score.

    Adds columns:
    - is_outlier (bool)
    - outlier_score (float)
    - outlier_method (str)
    - outlier_threshold (float)
    - outlier_group_n (int)

    Does NOT remove or modify values.
    """
    _check_required_columns(df, list(spec.group_cols) + [spec.value_col])

    out = df.copy()
    out["outlier_method"] = spec.method
    out["outlier_threshold"] = float(spec.threshold)
    out["outlier_score"] = np.nan
    out["is_outlier"] = False
    out["outlier_group_n"] = 0

    def _process_group(g: pd.DataFrame) -> pd.DataFrame:
        vals = pd.to_numeric(g[spec.value_col], errors="coerce")
        valid = vals.dropna()
        n = int(valid.shape[0])

        g.loc[:, "outlier_group_n"] = n

        if n < spec.min_group_n:
            return g

        if spec.method == "zscore":
            mean = valid.mean()
            std = valid.std(ddof=1)
            if std == 0 or np.isnan(std):
                return g
            z = (vals - mean) / std

        elif spec.method == "robust_zscore":
            median = valid.median()
            mad = (valid - median).abs().median()
            if mad == 0 or np.isnan(mad):
                return g
            z = 0.6745 * (vals - median) / mad

        else:
            raise ValueError("method must be 'zscore' or 'robust_zscore'")

        g.loc[:, "outlier_score"] = z
        g.loc[:, "is_outlier"] = z.abs() >= spec.threshold
        return g

    out = out.groupby(list(spec.group_cols), group_keys=False).apply(_process_group)
    return out


def get_outliers_table(
    df: pd.DataFrame,
    *,
    include_value: bool = True,
    include_score: bool = True,
    sort: bool = True,
) -> pd.DataFrame:
    """
    Return a user-friendly table of flagged outliers.

    Columns:
    plate_id, condition, well, time_point, metric
    + optional value, outlier_score, outlier_group_n, method, threshold
    """
    if "is_outlier" not in df.columns:
        raise ValueError("Run flag_outliers() before calling get_outliers_table().")

    cols = ["plate_id", "condition", "well", "time_point", "metric"]

    if include_value and "value" in df.columns:
        cols.append("value")
    if include_score and "outlier_score" in df.columns:
        cols.append("outlier_score")
    if "outlier_group_n" in df.columns:
        cols.append("outlier_group_n")
    if "outlier_method" in df.columns:
        cols.append("outlier_method")
    if "outlier_threshold" in df.columns:
        cols.append("outlier_threshold")

    out = df[df["is_outlier"] == True].copy()
    cols = [c for c in cols if c in out.columns]
    out = out[cols]

    if sort and {"metric", "condition", "well", "time_point"}.issubset(out.columns):
        out = out.sort_values(["metric", "condition", "well", "time_point"])

    return out.reset_index(drop=True)


def apply_outlier_filter(
    df: pd.DataFrame,
    mode: str = "point_to_nan",
    value_col: str = "value",
) -> pd.DataFrame:
    """
    Apply user-approved outlier removal.

    Modes:
    - "point_to_nan": set flagged points to NaN (recommended default)
    - "drop_rows": drop only flagged rows
    - "drop_well_metric": drop entire well×metric if ANY outlier exists
    """
    if "is_outlier" not in df.columns:
        raise ValueError("Run flag_outliers() before apply_outlier_filter().")

    out = df.copy()

    if mode == "point_to_nan":
        out.loc[out["is_outlier"], value_col] = np.nan
        return out

    if mode == "drop_rows":
        return out[~out["is_outlier"]].copy()

    if mode == "drop_well_metric":
        _check_required_columns(out, ["plate_id", "well", "metric"])

        bad = (
            out[out["is_outlier"]]
            .dropna(subset=["plate_id", "well", "metric"])
            [["plate_id", "well", "metric"]]
            .drop_duplicates()
        )

        if bad.empty:
            return out

        out = out.merge(
            bad.assign(_drop=True),
            on=["plate_id", "well", "metric"],
            how="left",
        )
        out = out[out["_drop"] != True].drop(columns="_drop")
        return out

    raise ValueError("mode must be 'point_to_nan', 'drop_rows', or 'drop_well_metric'")
