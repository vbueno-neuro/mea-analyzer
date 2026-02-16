"""
Time-point statistics for MEA analysis.

v1 focuses on comparisons BETWEEN conditions at a SINGLE time point.
This matches common MEA reporting and avoids incorrect repeated-measures assumptions.

Input df schema (minimum):
- metric (str)
- time_point (int)
- condition (str)
- value (float) OR value_norm (float)

Outputs:
- descriptives table per condition
- omnibus test result (ANOVA/Kruskal OR t-test/Mann-Whitney)
- pairwise comparisons with multiple testing correction
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Literal, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from scipy import stats
except ImportError as e:
    raise ImportError(
        "scipy is required for statistics. Install with: conda install scipy"
    ) from e


# -------------------------
# P-value correction
# -------------------------
def p_adjust(pvals: np.ndarray, method: Literal["bonferroni", "holm", "fdr_bh"] = "fdr_bh") -> np.ndarray:
    """
    Adjust p-values for multiple comparisons.

    bonferroni: p * m
    holm: step-down Bonferroni
    fdr_bh: Benjamini–Hochberg
    """
    pvals = np.asarray(pvals, dtype=float)
    m = pvals.size
    if m == 0:
        return pvals

    if method == "bonferroni":
        return np.minimum(pvals * m, 1.0)

    if method == "holm":
        order = np.argsort(pvals)
        ranked = pvals[order]
        adj = np.empty_like(ranked)
        for i, p in enumerate(ranked):
            adj[i] = min((m - i) * p, 1.0)
        # enforce monotonicity
        for i in range(1, m):
            adj[i] = max(adj[i], adj[i - 1])
        out = np.empty_like(adj)
        out[order] = adj
        return out

    if method == "fdr_bh":
        order = np.argsort(pvals)
        ranked = pvals[order]
        adj = np.empty_like(ranked)
        for i in range(m - 1, -1, -1):
            rank = i + 1
            adj[i] = ranked[i] * m / rank
            if i < m - 1:
                adj[i] = min(adj[i], adj[i + 1])
        adj = np.minimum(adj, 1.0)
        out = np.empty_like(adj)
        out[order] = adj
        return out

    raise ValueError("method must be one of: bonferroni, holm, fdr_bh")


# -------------------------
# Effect sizes (simple)
# -------------------------
def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d using pooled SD (ignores NaNs)."""
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if a.size < 2 or b.size < 2:
        return np.nan
    na, nb = a.size, b.size
    sa, sb = np.std(a, ddof=1), np.std(b, ddof=1)
    sp = np.sqrt(((na - 1) * sa**2 + (nb - 1) * sb**2) / (na + nb - 2))
    if sp == 0 or np.isnan(sp):
        return np.nan
    return (np.mean(a) - np.mean(b)) / sp


# -------------------------
# Main API
# -------------------------
@dataclass(frozen=True)
class TimepointStatsSpec:
    """
    test_family:
      - "parametric": Welch t-test (2 groups), one-way ANOVA (>=3)
      - "nonparametric": Mann–Whitney (2), Kruskal–Wallis (>=3)

    p_adjust_method applies to pairwise tests only.
    """
    test_family: Literal["parametric", "nonparametric"] = "nonparametric"
    p_adjust_method: Literal["bonferroni", "holm", "fdr_bh"] = "fdr_bh"
    value_col: str = "value"


def compare_conditions_at_timepoint(
    df: pd.DataFrame,
    *,
    metric: str,
    time_point: int,
    spec: TimepointStatsSpec = TimepointStatsSpec(),
    plate_id: Optional[str] = None,
    min_n_per_group: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Compare conditions for one metric at one time point.

    Returns
    -------
    descriptives_df : per condition (n, mean, sem, median)
    omnibus_df      : 1-row summary of omnibus test
    pairwise_df     : pairwise comparisons with adjusted p-values
    """
    required = {"metric", "time_point", "condition", spec.value_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")

    d = df.copy()
    d = d[(d["metric"] == metric) & (d["time_point"] == time_point)]
    d = d.dropna(subset=["condition"])
    d[spec.value_col] = pd.to_numeric(d[spec.value_col], errors="coerce")

    if plate_id is not None:
        if "plate_id" not in d.columns:
            raise ValueError("plate_id was provided but df has no 'plate_id' column.")
        d = d[d["plate_id"] == plate_id]

    # Descriptives
    desc = (
        d.groupby("condition")[spec.value_col]
        .agg(
            n=lambda x: int(pd.to_numeric(x, errors="coerce").dropna().shape[0]),
            mean="mean",
            sem=lambda x: float(pd.to_numeric(x, errors="coerce").dropna().std(ddof=1) / np.sqrt(max(pd.to_numeric(x, errors="coerce").dropna().shape[0], 1)))
            if pd.to_numeric(x, errors="coerce").dropna().shape[0] > 1 else np.nan,
            median="median",
            std="std",
        )
        .reset_index()
    )

    # Keep only groups with enough n
    valid_conditions = desc[desc["n"] >= min_n_per_group]["condition"].tolist()
    d = d[d["condition"].isin(valid_conditions)].copy()
    desc = desc[desc["condition"].isin(valid_conditions)].reset_index(drop=True)

    k = len(valid_conditions)
    if k < 2:
        raise ValueError(f"Not enough conditions with n>={min_n_per_group} at time_point={time_point}.")

    # Build arrays per group
    groups = {c: pd.to_numeric(d[d["condition"] == c][spec.value_col], errors="coerce").to_numpy() for c in valid_conditions}
    groups = {c: v[~np.isnan(v)] for c, v in groups.items()}

    # Omnibus test
    omnibus = {
        "metric": metric,
        "time_point": int(time_point),
        "plate_id": plate_id if plate_id is not None else "ALL",
        "test_family": spec.test_family,
        "test": None,
        "statistic": np.nan,
        "p_value": np.nan,
        "k_groups": k,
        "min_n_per_group": min_n_per_group,
    }

    if k == 2:
        a, b = groups[valid_conditions[0]], groups[valid_conditions[1]]
        if spec.test_family == "parametric":
            # Welch t-test
            tstat, p = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
            omnibus["test"] = "welch_ttest"
            omnibus["statistic"] = float(tstat)
            omnibus["p_value"] = float(p)
        else:
            # Mann–Whitney U
            u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            omnibus["test"] = "mannwhitney_u"
            omnibus["statistic"] = float(u)
            omnibus["p_value"] = float(p)
    else:
        arrs = [groups[c] for c in valid_conditions]
        if spec.test_family == "parametric":
            f, p = stats.f_oneway(*arrs)
            omnibus["test"] = "oneway_anova"
            omnibus["statistic"] = float(f)
            omnibus["p_value"] = float(p)
        else:
            h, p = stats.kruskal(*arrs, nan_policy="omit")
            omnibus["test"] = "kruskal_wallis"
            omnibus["statistic"] = float(h)
            omnibus["p_value"] = float(p)

    omnibus_df = pd.DataFrame([omnibus])

    # Pairwise comparisons (always computed; user can decide to use them if omnibus is significant)
    rows = []
    for c1, c2 in combinations(valid_conditions, 2):
        a, b = groups[c1], groups[c2]

        if spec.test_family == "parametric":
            tstat, p = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
            test_name = "welch_ttest"
            effect = cohens_d(a, b)
            effect_name = "cohens_d"
            stat_val = float(tstat)
        else:
            u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            test_name = "mannwhitney_u"
            # simple effect placeholder (rank-biserial could be added later)
            effect = np.nan
            effect_name = "effect"
            stat_val = float(u)

        rows.append(
            {
                "metric": metric,
                "time_point": int(time_point),
                "plate_id": plate_id if plate_id is not None else "ALL",
                "test_family": spec.test_family,
                "test": test_name,
                "condition_a": c1,
                "condition_b": c2,
                "n_a": int(a.size),
                "n_b": int(b.size),
                "statistic": stat_val,
                "p_value": float(p),
                effect_name: effect,
            }
        )

    pairwise_df = pd.DataFrame(rows)
    if not pairwise_df.empty:
        pairwise_df["p_adj"] = p_adjust(pairwise_df["p_value"].to_numpy(), method=spec.p_adjust_method)
        pairwise_df = pairwise_df.sort_values("p_adj").reset_index(drop=True)

    return desc, omnibus_df, pairwise_df
