"""
novawireless.pipeline.signals
------------------------------
Call-level trust signal computation.

Produces the following new columns on the clean DataFrame:

proxy_vs_true_gap
    Binary flag: resolution_flag == 1 AND true_resolution == 0.
    The per-call form of the Goodhart Gap.

scripted_window_flag
    Binary flag: 1 if any FCR-gaming language pattern was detected
    in transcript_text.  These patterns are the primary mechanism
    driving 31–60 day callbacks in the paper's analysis.

scripted_phrase_count
    Count of distinct pattern families matched per transcript (0–N).

transcript_word_count
    Token count of transcript_text (proxy for resolution effort).

detection_signal_density
    Fraction of the detection flag columns (+ scripted_window_flag)
    that fired on this call.  Range [0, 1].

credit_risk_score
    Composite credit-quality risk.  Calibrated so that:
      0.0  = no credit applied
      0.1  = credit applied (authorized, non-bandaid)
      0.7  = credit applied, unauthorized
      1.0  = bandaid credit (by definition unauthorised)
    An additional 0–0.2 is added for high credit_burden_ratio
    (credit_amount / customer_monthly_charges > 0.5 signals
    substantive appeasement, not a token gesture).

credit_burden_ratio
    credit_amount / customer_monthly_charges.  Range [0, ∞] clipped
    implicitly by credit_risk_score capping.

rep_drift_score
    Weighted composite of conscious gaming, structural propensity,
    and burnout.  Weights: aware_gaming=0.45, gaming_propensity=0.35,
    burnout=0.20 (sum = 1.0).  Aware gaming is weighted highest
    because it represents deliberate, not structural, risk.

outcome_risk_score
    Composite of true non-resolution, repeat contacts, and escalation.
    Weights: true_resolution_fail=0.30, repeat_30d=0.30,
    repeat_31_60d=0.15, escalation=0.25.

call_trust_score
    Overall call-level governance health score.  Range [0, 100].
    100 = fully trustworthy measurement.  0 = total divergence.

    Formula:
        100 – 25·proxy_vs_true_gap – 20·detection_signal_density
            – 20·credit_risk_score  – 15·rep_drift_score
            – 20·outcome_risk_score
"""

from __future__ import annotations

import re
from typing import List

import numpy as np
import pandas as pd

from .integrity import _coerce_flag, DETECTION_FLAG_COLS


# ── Scripted FCR-gaming language patterns ────────────────────────────────────
# Calibrated for gamed_metric transcripts in the NovaWireless synthetic dataset.
# Real-world deployment requires re-calibration against domain transcripts.
# See paper Section 2 ("KPI Self-Reinforcement Drift") for mechanism description.

_SCRIPTED_PATTERNS: List[str] = [
    # 1. Temporal deflection — resolution promised in a future billing cycle
    r"(?:call|hear from us) (?:back )?next month",
    r"have you call back next",
    r"next month.{0,30}(?:resolved|fixed|taken care)",

    # 2. Performative honesty — acknowledges issue without resolving it;
    #    designed to achieve a satisfied-customer label before close
    r"honest(?:ly)? (?:answer|with you).{0,60}(?:call back|next month|not (?:able|going))",
    r"that.s the only way (?:i know how to handle|to handle) it",
    r"tell you what you want to hear",

    # 3. False prior-resolution acknowledgement — escalation cover language
    r"marked resolved (?:twice|before|previously|without)",
    r"marked resolved without actually",
    r"closed without (?:actually )?(?:being )?(?:resolved|fixed)",

    # 4. Not-able-to-override deflection — system-level blame language
    r"not (?:able|going) to (?:override|reverse).{0,40}(?:from my end|at my level|on my end)",
    r"system.level (?:pricing|change).{0,40}(?:not able|cannot|can.t)",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _SCRIPTED_PATTERNS]


# ── Safe accessors ────────────────────────────────────────────────────────────

def _safe_coerce(df: pd.DataFrame, col: str, default: int = 0) -> pd.Series:
    """Return ``_coerce_flag(df[col])`` if column exists, else a zero Series."""
    return (
        _coerce_flag(df[col]) if col in df.columns
        else pd.Series(default, index=df.index)
    )


def _safe_numeric(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    """Return ``df[col]`` coerced to float if column exists, else a zero Series."""
    return (
        pd.to_numeric(df[col], errors="coerce").fillna(default)
        if col in df.columns
        else pd.Series(default, index=df.index, dtype=float)
    )


# ── Core scoring ──────────────────────────────────────────────────────────────

def compute_trust_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all call-level trust signals and append them to ``df``.

    Parameters
    ----------
    df : pd.DataFrame
        Clean calls DataFrame (output of ``run_integrity_gate``).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with the eight new signal columns appended.
    """
    out = df.copy()

    # ── 1. Proxy-true gap ────────────────────────────────────────────────────
    proxy = _safe_coerce(out, "resolution_flag")
    true  = _safe_coerce(out, "true_resolution")
    out["proxy_vs_true_gap"] = ((proxy == 1) & (true == 0)).astype(int)

    # ── 2. Scripted FCR-gaming language ──────────────────────────────────────
    if "transcript_text" in out.columns:
        txt = out["transcript_text"].fillna("").astype(str).str.lower()
        out["scripted_phrase_count"] = sum(
            txt.apply(lambda t: int(bool(cp.search(t))))
            for cp in _COMPILED_PATTERNS
        )
        out["scripted_window_flag"]  = (out["scripted_phrase_count"] > 0).astype(int)
        out["transcript_word_count"] = (
            txt.str.split().str.len().fillna(0).astype(int)
        )
    else:
        out["scripted_window_flag"]  = 0
        out["scripted_phrase_count"] = 0
        out["transcript_word_count"] = 0

    # ── 3. Detection signal density ──────────────────────────────────────────
    # Include scripted_window_flag so transcript-based gaming detection feeds
    # the same composite as the structural fraud / gaming flags.
    det_cols = [c for c in DETECTION_FLAG_COLS if c in out.columns]
    det_cols = list(dict.fromkeys(det_cols + ["scripted_window_flag"]))
    if det_cols:
        out["detection_signal_density"] = (
            out[det_cols]
            .apply(lambda col: _coerce_flag(col), axis=0)
            .sum(axis=1) / len(det_cols)
        )
    else:
        out["detection_signal_density"] = 0.0

    # ── 4. Credit risk score ─────────────────────────────────────────────────
    ca   = _safe_coerce(out, "credit_applied")
    cauth = _safe_coerce(out, "credit_authorized")
    is_b = (
        out["credit_type"].astype(str).str.strip() == "bandaid"
        if "credit_type" in out.columns
        else pd.Series(False, index=out.index)
    )
    is_u = (ca == 1) & (cauth == 0)

    cr = pd.Series(0.0, index=out.index, dtype=float)
    cr = cr.where(~(ca == 1), 0.1)   # any credit applied
    cr = cr.where(~is_u,       0.7)   # unauthorized credit
    cr = cr.where(~is_b,       1.0)   # bandaid credit (worst)

    # Credit burden ratio: credit_amount / customer_monthly_charges.
    # A $25 credit on a $27/month plan is qualitatively different from
    # a $5 courtesy credit — add up to 0.2 for high-ratio events.
    if "credit_amount" in out.columns and "customer_monthly_charges" in out.columns:
        amt   = pd.to_numeric(out["credit_amount"],            errors="coerce").fillna(0.0).clip(lower=0)
        mchg  = pd.to_numeric(out["customer_monthly_charges"], errors="coerce").fillna(0.0)
        ratio = np.where(mchg > 0, amt / mchg, 0.0)
        out["credit_burden_ratio"] = np.round(ratio, 4)
        cr = np.clip(cr + 0.20 * np.clip(ratio, 0.0, 1.0), 0.0, 1.0)
    else:
        out["credit_burden_ratio"] = 0.0

    out["credit_risk_score"] = cr

    # ── 5. Rep drift score ───────────────────────────────────────────────────
    # Weights: aware_gaming=0.45, gaming_propensity=0.35, burnout=0.20
    # Aware gaming is weighted highest because it is deliberate, not structural.
    aware = (
        _safe_coerce(out, "rep_aware_gaming")
        if "rep_aware_gaming" in out.columns
        else pd.Series(0.0, index=out.index)
    )
    out["rep_drift_score"] = np.clip(
        0.45 * aware
        + 0.35 * _safe_numeric(out, "rep_gaming_propensity")
        + 0.20 * _safe_numeric(out, "rep_burnout_level"),
        0, 1,
    )

    # ── 6. Outcome risk score ─────────────────────────────────────────────────
    out["outcome_risk_score"] = np.clip(
        0.30 * (true == 0).astype(int)
        + 0.30 * _safe_coerce(out, "repeat_contact_30d")
        + 0.15 * _safe_coerce(out, "repeat_contact_31_60d")
        + 0.25 * _safe_coerce(out, "escalation_flag"),
        0, 1,
    )

    # ── 7. Call trust score ───────────────────────────────────────────────────
    out["call_trust_score"] = np.clip(
        100
        - 25 * out["proxy_vs_true_gap"]
        - 20 * out["detection_signal_density"]
        - 20 * out["credit_risk_score"]
        - 15 * out["rep_drift_score"]
        - 20 * out["outcome_risk_score"],
        0, 100,
    ).round(2)

    return out
