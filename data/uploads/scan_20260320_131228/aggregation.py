"""
novawireless.pipeline.aggregation
-----------------------------------
Aggregation functions that roll call-level signals up to summary views.

Functions
---------
summarize_by_rep         — rep-level trust, gap, drift, and DAR summary
summarize_by_scenario    — scenario-level health and per-scenario DOV
summarize_by_customer    — customer-level risk and churn exposure
compute_monthly_trends   — month-over-month signal trajectory
compute_churn_by_trust_decile — trust-churn correlation by decile

Paper connection
----------------
Rep-level and scenario-level aggregation surfaces the heterogeneity that
is masked when Goodhart Gap is reported only at system level.  A 42.1pp
aggregate gap is composed of individual scenarios (e.g. gamed_metric at
~89pp gap) alongside clean scenarios at near-zero gap.  This decomposition
is necessary evidence for the paper's claim that distortion is architectural,
not evenly distributed.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .integrity import _coerce_flag
from .signals   import _safe_coerce, _safe_numeric


# ── Rep-level summary ─────────────────────────────────────────────────────────

def summarize_by_rep(
    df: pd.DataFrame,
    min_calls: int = 1,
) -> pd.DataFrame:
    """
    Aggregate call-level signals to rep level.

    Includes rep-level DAR (paper formula F/D) to identify which reps are
    specifically driving 31–60 day callbacks after labeled resolution.

    Parameters
    ----------
    df        : scored calls DataFrame
    min_calls : minimum call volume for a rep to appear in the output

    Returns
    -------
    pd.DataFrame sorted by trust_score_avg ascending (worst reps first)
    """
    if "rep_id" not in df.columns:
        return pd.DataFrame()

    agg_spec = {
        "calls":                 ("call_id",           "count"),
        "proxy_resolution_rate": ("resolution_flag",   lambda s: _coerce_flag(s).mean()),
        "true_resolution_rate":  ("true_resolution",   lambda s: _coerce_flag(s).mean()),
        "proxy_true_gap_rate":   ("proxy_vs_true_gap", "mean"),
        "credit_risk_avg":       ("credit_risk_score", "mean"),
        "detection_density_avg": ("detection_signal_density", "mean"),
        "rep_drift_avg":         ("rep_drift_score",   "mean"),
        "outcome_risk_avg":      ("outcome_risk_score","mean"),
        "trust_score_avg":       ("call_trust_score",  "mean"),
    }

    # Optional columns — zero-fill if absent
    for col_spec, agg_col in [
        ("repeat_contact_30d",    "repeat_30d_rate"),
        ("repeat_contact_31_60d", "repeat_31_60d_rate"),
        ("escalation_flag",       "escalation_rate"),
    ]:
        if col_spec in df.columns:
            agg_spec[agg_col] = (col_spec, lambda s: _coerce_flag(s).mean())
        else:
            agg_spec[agg_col] = ("call_id", lambda s: 0.0)

    for col_spec, agg_col in [
        ("rep_gaming_propensity", "gaming_propensity_avg"),
        ("rep_burnout_level",     "burnout_avg"),
        ("rep_aware_gaming",      "aware_gaming_rate"),
        ("scripted_window_flag",  "scripted_phrase_rate"),
    ]:
        if col_spec in df.columns:
            agg_spec[agg_col] = (
                col_spec,
                lambda s: (
                    _coerce_flag(s).mean()
                    if agg_col in {"aware_gaming_rate", "scripted_phrase_rate"}
                    else pd.to_numeric(s, errors="coerce").mean()
                ),
            )
        else:
            agg_spec[agg_col] = ("call_id", lambda s: np.nan)

    if "credit_type" in df.columns:
        agg_spec["bandaid_rate"] = (
            "credit_type",
            lambda s: (s.astype(str).str.strip() == "bandaid").mean(),
        )
    else:
        agg_spec["bandaid_rate"] = ("call_id", lambda s: 0.0)

    agg = df.groupby("rep_id", dropna=False).agg(**agg_spec).reset_index()
    agg["resolution_gap"] = (
        agg["proxy_resolution_rate"] - agg["true_resolution_rate"]
    ).round(4)

    # Per-rep DAR (paper formula F/D) — identifies which reps drive 31–60d callbacks
    if "resolution_flag" in df.columns and "repeat_contact_31_60d" in df.columns:
        def _rep_dar(g: pd.DataFrame) -> float:
            resolved = _coerce_flag(g["resolution_flag"]) == 1
            D = int(resolved.sum())
            if D == 0:
                return np.nan
            F = int(_coerce_flag(g.loc[resolved, "repeat_contact_31_60d"]).sum())
            return round(F / D, 6)

        rep_dar = (
            df.groupby("rep_id", dropna=False)
            .apply(_rep_dar)
            .reset_index()
        )
        rep_dar.columns = ["rep_id", "rep_dar"]
        agg = agg.merge(rep_dar, on="rep_id", how="left")
    else:
        agg["rep_dar"] = np.nan

    return (
        agg[agg["calls"] >= min_calls]
        .sort_values("trust_score_avg")
        .reset_index(drop=True)
    )


# ── Scenario-level summary ────────────────────────────────────────────────────

def summarize_by_scenario(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate call-level signals to scenario level.

    Includes per-scenario DOV (proxy label error rate = 1 − accuracy),
    which identifies which call types are corrupting the measurement
    environment.  Higher scenario DOV = worse.

    Returns
    -------
    pd.DataFrame sorted by trust_score_avg ascending
    """
    if "scenario" not in df.columns:
        return pd.DataFrame()

    agg_spec = {
        "calls":               ("call_id",           "count"),
        "pct_of_total":        ("call_id",           "count"),
        "proxy_resolution_rate": ("resolution_flag", lambda s: _coerce_flag(s).mean()),
        "true_resolution_rate":  ("true_resolution", lambda s: _coerce_flag(s).mean()),
        "proxy_true_gap_rate":   ("proxy_vs_true_gap", "mean"),
        "credit_applied_rate": ("credit_applied",    lambda s: _coerce_flag(s).mean()),
        "detection_density_avg": ("detection_signal_density", "mean"),
        "trust_score_avg":     ("call_trust_score",  "mean"),
        "outcome_risk_avg":    ("outcome_risk_score","mean"),
    }

    if "credit_type" in df.columns:
        agg_spec["bandaid_rate"] = (
            "credit_type",
            lambda s: (s.astype(str).str.strip() == "bandaid").mean(),
        )

    if "scripted_window_flag" in df.columns:
        agg_spec["scripted_rate"] = (
            "scripted_window_flag",
            lambda s: _coerce_flag(s).mean(),
        )

    agg = df.groupby("scenario", dropna=False).agg(**agg_spec).reset_index()
    agg["pct_of_total"] = (agg["calls"] / max(len(df), 1) * 100).round(2)
    agg["resolution_gap"] = (
        agg["proxy_resolution_rate"] - agg["true_resolution_rate"]
    ).round(4)

    # Per-scenario DOV
    if "resolution_flag" in df.columns and "true_resolution" in df.columns:
        def _scen_dov(g: pd.DataFrame) -> float:
            proxy    = _coerce_flag(g["resolution_flag"])
            true     = _coerce_flag(g["true_resolution"])
            accuracy = float((proxy == true).mean())
            return round(1.0 - accuracy, 6)

        scen_dov = (
            df.groupby("scenario", dropna=False)
            .apply(_scen_dov)
            .reset_index()
        )
        scen_dov.columns = ["scenario", "scenario_dov"]
        agg = agg.merge(scen_dov, on="scenario", how="left")
    else:
        agg["scenario_dov"] = np.nan

    return agg.sort_values("trust_score_avg").reset_index(drop=True)


# ── Customer-level summary ────────────────────────────────────────────────────

def summarize_by_customer(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate call-level signals to customer level.

    Returns
    -------
    pd.DataFrame sorted by call volume descending, then trust ascending
    """
    if "customer_id" not in df.columns:
        return pd.DataFrame()

    spec = {
        "calls":            ("call_id",          "count"),
        "avg_trust_score":  ("call_trust_score", "mean"),
        "min_trust_score":  ("call_trust_score", "min"),
        "max_trust_score":  ("call_trust_score", "max"),
        "trust_score_std":  ("call_trust_score", "std"),
        "avg_outcome_risk": ("outcome_risk_score","mean"),
        "avg_proxy_gap":    ("proxy_vs_true_gap", "mean"),
    }

    if "scenario" in df.columns:
        spec["distinct_scenarios"] = ("scenario", "nunique")

    for col_spec, agg_col in [
        ("repeat_contact_30d",     "any_repeat_30d"),
        ("repeat_contact_30d",     "repeat_30d_rate"),
        ("customer_is_churned",    "is_churned"),
    ]:
        if col_spec in df.columns:
            fn = (
                (lambda s: _coerce_flag(s).max())
                if agg_col in {"any_repeat_30d", "is_churned"}
                else (lambda s: _coerce_flag(s).mean())
            )
            spec[agg_col] = (col_spec, fn)

    for col_spec, agg_col in [
        ("customer_churn_risk_effective", "avg_churn_risk"),
        ("customer_trust_baseline",       "min_trust_baseline"),
    ]:
        if col_spec in df.columns:
            fn = (
                (lambda s: pd.to_numeric(s, errors="coerce").mean())
                if "avg" in agg_col
                else (lambda s: pd.to_numeric(s, errors="coerce").min())
            )
            spec[agg_col] = (col_spec, fn)

    if "call_date" in df.columns:
        spec["first_call"] = ("call_date", "min")
        spec["last_call"]  = ("call_date", "max")

    agg = df.groupby("customer_id", dropna=False).agg(**spec).reset_index()
    return (
        agg
        .sort_values(["calls", "avg_trust_score"], ascending=[False, True])
        .reset_index(drop=True)
    )


# ── Monthly trend tracking ────────────────────────────────────────────────────

def compute_monthly_trends(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate signals to monthly periods and compute velocity signals.

    trust_velocity  — month-over-month change in mean trust score
    gap_velocity    — month-over-month change in resolution gap
    bandaid_velocity — month-over-month change in bandaid rate

    Returns
    -------
    pd.DataFrame  (empty if call_date column is absent)
    """
    if "call_date" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["_month"] = pd.to_datetime(df["call_date"], errors="coerce").dt.to_period("M")
    df = df.dropna(subset=["_month"])

    spec = {
        "calls":                  ("call_id",            "count"),
        "trust_score_avg":        ("call_trust_score",   "mean"),
        "trust_score_median":     ("call_trust_score",   "median"),
        "trust_score_p10":        ("call_trust_score",   lambda s: s.quantile(0.10)),
        "proxy_resolution_rate":  ("resolution_flag",    lambda s: _coerce_flag(s).mean()),
        "true_resolution_rate":   ("true_resolution",    lambda s: _coerce_flag(s).mean()),
        "proxy_true_gap_rate":    ("proxy_vs_true_gap",  "mean"),
        "detection_density_avg":  ("detection_signal_density", "mean"),
        "credit_risk_avg":        ("credit_risk_score",  "mean"),
        "outcome_risk_avg":       ("outcome_risk_score", "mean"),
        "rep_drift_avg":          ("rep_drift_score",    "mean"),
    }

    for col_spec, agg_col in [
        ("credit_type",           "bandaid_rate"),
        ("repeat_contact_30d",    "repeat_30d_rate"),
        ("escalation_flag",       "escalation_rate"),
        ("customer_is_churned",   "churn_rate"),
    ]:
        if col_spec in df.columns:
            if agg_col == "bandaid_rate":
                spec[agg_col] = (
                    col_spec,
                    lambda s: (s.astype(str).str.strip() == "bandaid").mean(),
                )
            else:
                spec[agg_col] = (col_spec, lambda s: _coerce_flag(s).mean())

    m = df.groupby("_month").agg(**spec).reset_index()
    m["_month"] = m["_month"].astype(str)
    m["resolution_gap"]    = (m["proxy_resolution_rate"] - m["true_resolution_rate"]).round(4)
    m["trust_velocity"]    = m["trust_score_avg"].diff().round(3)
    m["gap_velocity"]      = m["resolution_gap"].diff().round(4)
    if "bandaid_rate" in m.columns:
        m["bandaid_velocity"] = m["bandaid_rate"].diff().round(4)

    return m


# ── Churn-by-trust-decile ─────────────────────────────────────────────────────

def compute_churn_by_trust_decile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Stratify calls into 10 trust-score deciles and compute churn rate per decile.

    The trust–churn correlation is attached as a DataFrame attribute
    (``df.attrs["trust_churn_correlation"]``).

    Paper connection:
        If TER ≈ baseline churn at system level, the decile analysis reveals
        whether the null relationship holds uniformly or is masked by
        cancelling effects across the distribution.

    Returns
    -------
    pd.DataFrame (empty if churn data unavailable or < 10 rows)
    """
    if "customer_is_churned" not in df.columns:
        return pd.DataFrame()
    if len(df) < 10:
        return pd.DataFrame()

    out = df.copy()
    out["_churned"] = _safe_coerce(out, "customer_is_churned")

    try:
        out["trust_decile"] = (
            pd.qcut(out["call_trust_score"], 10, labels=False, duplicates="drop") + 1
        )
    except ValueError:
        return pd.DataFrame()

    spec = {
        "calls":               ("call_id",          "count"),
        "trust_score_min":     ("call_trust_score", "min"),
        "trust_score_max":     ("call_trust_score", "max"),
        "trust_score_avg":     ("call_trust_score", "mean"),
        "churn_rate":          ("_churned",         "mean"),
        "proxy_resolution_rate": (
            "resolution_flag",
            lambda s: pd.to_numeric(_coerce_flag(s), errors="coerce").mean(),
        ),
        "true_resolution_rate": (
            "true_resolution",
            lambda s: pd.to_numeric(_coerce_flag(s), errors="coerce").mean(),
        ),
    }

    if "repeat_contact_30d" in out.columns:
        spec["repeat_30d_rate"] = (
            "repeat_contact_30d", lambda s: _coerce_flag(s).mean()
        )

    dec = out.groupby("trust_decile").agg(**spec).reset_index()
    dec["resolution_gap"] = (
        dec["proxy_resolution_rate"] - dec["true_resolution_rate"]
    ).round(4)

    if len(dec) > 2:
        corr = dec["trust_score_avg"].corr(dec["churn_rate"])
        dec.attrs["trust_churn_correlation"] = round(corr, 4) if pd.notna(corr) else None

    return dec
