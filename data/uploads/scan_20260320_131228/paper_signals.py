"""
novawireless.pipeline.paper_signals
-------------------------------------
Formal governance signals from Aulabaugh (2026), Appendix A.

All six signals are computed here:

    DAR — Delayed Adverse Rate
        DAR_raw = F / D
        DAR     = N↑(DAR_raw; L_DAR, H_DAR)
        F = repeat contacts 31–60 days after labeled resolution
        D = total labeled-resolved calls

    DRL — Downstream Remediation Load
        DRL_raw = JS(p ∥ q)   (Jensen–Shannon divergence)
        DRL     = N↑(DRL_raw; L_DRL, H_DRL)
        Detects distributional drift in call scenario mix over time.
        Requires ≥ 2 months of data.

    DOV — Durable Outcome Validation
        DOV = clamp((A_base − A_cur) / (A_base + ε), 0, 1)
        Measures decay in the predictive validity of the proxy label.
        DOV gate: if DOV ≥ τ, SII_gated is forced to 100.

    POR — Proxy Overfit Ratio
        POR_raw = clamp(ΔP / (ΔT + ε), 0, K)
        POR     = clamp((POR_raw − 1) / (K − 1), 0, 1)
        Measures acceleration imbalance: proxy improving faster than outcomes.
        Requires ≥ 2 months of data.

    TER — Terminal Exit Rate  (diagnostic, not a SII component)
        TER = churn rate among proxy-resolved calls.
        TER ≈ baseline churn → resolution label carries no retention signal.

    SII — System Integrity Index
        SII       = 100 · (w_DAR·DAR + w_DRL·DRL + w_DOV·DOV + w_POR·POR)
        SII_gated = 100  if DOV ≥ τ,  SII otherwise
        Default weights: DAR=0.30, DRL=0.20, DOV=0.25, POR=0.25

    Thresholds:
        SII_gated ≥ 60  → VETO:  Halt AI optimization.
        SII_gated 30–60 → WATCH: Human review required.
        SII_gated < 30  → OK:    Within governance bounds.

    NovaWireless benchmark (82,305 call records):
        Proxy FCR:    89.4%    True CRT:   47.3%
        Goodhart Gap: 42.1pp   Bandaid:    71.1%
        SII (clean):   5.25    → Type III
        Classification: Type I (Goodhart Gap override)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .integrity import _coerce_flag


# ── Default calibration ───────────────────────────────────────────────────────

PAPER_SIGNAL_DEFAULTS: Dict = {
    # Normalization bounds — set for early detection (signals climb before catastrophe)
    "DAR_L": 0.05,   # Negligible risk floor (5% repeat rate after resolution)
    "DAR_H": 0.40,   # Saturation ceiling (40% repeat rate = maximum risk)
    "DRL_L": 0.02,   # JS divergence noise floor
    "DRL_H": 0.30,   # JS divergence saturation (serious scenario mix drift)
    "POR_K": 5.0,    # Proxy improving ≥5× faster than true outcomes = max signal

    # SII gate and thresholds
    "DOV_tau":   0.50,   # DOV ≥ 0.50 → SII_gated forced to 100
    "SII_veto":  60.0,   # SII_gated ≥ 60 → VETO
    "SII_watch": 30.0,   # SII_gated ≥ 30 → WATCH

    "EPSILON": 1e-9,     # Division guard (inactive when denominator > 0)

    "SII_weights": {
        "DAR": 0.30,
        "DRL": 0.20,
        "DOV": 0.25,
        "POR": 0.25,
    },
}


# ── Math helpers ──────────────────────────────────────────────────────────────

def _norm_up(x: float, L: float, H: float) -> float:
    """
    N↑(x; L, H) — Higher-Is-Worse Normalization (Appendix A).

    Converts a raw signal value into a standardized risk score on [0, 1].
    x ≤ L → 0.0  (at or below lower bound: no risk detected)
    x ≥ H → 1.0  (at or above upper bound: maximum risk)
    """
    if H <= L:
        return 0.0
    return float(np.clip((x - L) / (H - L), 0.0, 1.0))


def _js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """
    Jensen–Shannon divergence JS(p ∥ q), used by DRL.

    JS(p ∥ q) = 0.5 · KL(p ∥ m) + 0.5 · KL(q ∥ m)
    where m = 0.5 · (p + q).

    Properties:
        Symmetric:  JS(p ∥ q) == JS(q ∥ p)
        Bounded:    JS ∈ [0, ln2 ≈ 0.693]
        JS = 0 when p and q are identical distributions.

    Returns 0.0 if either distribution is all-zero.
    """
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    if p.sum() == 0 or q.sum() == 0:
        return 0.0
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)

    def _kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = (a > 0) & (b > 0)
        return float(np.sum(a[mask] * np.log(a[mask] / b[mask])))

    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


# ── Individual signal computations ────────────────────────────────────────────

def _compute_dar(df: pd.DataFrame, cfg: Dict) -> Tuple[float, float]:
    """
    DAR — Delayed Adverse Rate.
    Returns (DAR_raw, DAR_normalized).
    """
    eps = cfg["EPSILON"]
    if "resolution_flag" not in df.columns:
        return 0.0, 0.0

    resolved_mask = _coerce_flag(df["resolution_flag"]) == 1
    D = int(resolved_mask.sum())
    if D == 0:
        return 0.0, 0.0
    if "repeat_contact_31_60d" not in df.columns:
        return 0.0, 0.0

    F = int(_coerce_flag(df.loc[resolved_mask, "repeat_contact_31_60d"]).sum())
    DAR_raw  = F / (D + eps)
    DAR_norm = _norm_up(DAR_raw, cfg["DAR_L"], cfg["DAR_H"])
    return round(DAR_raw, 6), round(DAR_norm, 6)


def _compute_drl(
    df: pd.DataFrame,
    cfg: Dict,
) -> Tuple[float, float, int]:
    """
    DRL — Downstream Remediation Load.
    Returns (DRL_raw, DRL_normalized, n_months_available).
    Requires ≥ 2 months.  Returns (0.0, 0.0, n_months) if insufficient data.
    """
    if "scenario" not in df.columns or "call_date" not in df.columns:
        return 0.0, 0.0, 0

    tmp = df.copy()
    tmp["_month"] = pd.to_datetime(tmp["call_date"], errors="coerce").dt.to_period("M")
    tmp = tmp.dropna(subset=["_month"])
    n = tmp["_month"].nunique()

    if n < 2:
        return 0.0, 0.0, n

    months_sorted    = sorted(tmp["_month"].unique())
    baseline_month   = months_sorted[0]
    current_month    = months_sorted[-1]
    scenarios        = sorted(tmp["scenario"].dropna().unique())

    def _dist(month_df: pd.DataFrame) -> np.ndarray:
        counts = month_df["scenario"].value_counts()
        return np.array([counts.get(s, 0) for s in scenarios], dtype=float)

    q = _dist(tmp[tmp["_month"] == baseline_month])
    p = _dist(tmp[tmp["_month"] == current_month])

    DRL_raw  = _js_divergence(p, q)
    DRL_norm = _norm_up(DRL_raw, cfg["DRL_L"], cfg["DRL_H"])
    return round(DRL_raw, 6), round(DRL_norm, 6), n


def _compute_dov(df: pd.DataFrame, cfg: Dict) -> float:
    """
    DOV — Durable Outcome Validation.
    Returns DOV (already normalized to [0, 1]).

    Single-month fallback: uses perfect accuracy (1.0) as A_base,
    giving a conservative sensitivity reading rather than returning 0.
    """
    eps = cfg["EPSILON"]
    if "resolution_flag" not in df.columns or "true_resolution" not in df.columns:
        return 0.0

    if "call_date" not in df.columns:
        proxy  = _coerce_flag(df["resolution_flag"])
        true   = _coerce_flag(df["true_resolution"])
        A_base = 1.0
        A_cur  = float((proxy == true).mean())
        return float(np.clip((A_base - A_cur) / (A_base + eps), 0.0, 1.0))

    tmp = df.copy()
    tmp["_month"] = pd.to_datetime(tmp["call_date"], errors="coerce").dt.to_period("M")
    tmp = tmp.dropna(subset=["_month"])

    if tmp["_month"].nunique() < 2:
        proxy  = _coerce_flag(tmp["resolution_flag"])
        true   = _coerce_flag(tmp["true_resolution"])
        A_base = 1.0
        A_cur  = float((proxy == true).mean())
        return round(float(np.clip((A_base - A_cur) / (A_base + eps), 0.0, 1.0)), 6)

    months_sorted = sorted(tmp["_month"].unique())

    def _accuracy(month_df: pd.DataFrame) -> float:
        proxy = _coerce_flag(month_df["resolution_flag"])
        true  = _coerce_flag(month_df["true_resolution"])
        return float((proxy == true).mean())

    A_base = _accuracy(tmp[tmp["_month"] == months_sorted[0]])
    A_cur  = _accuracy(tmp[tmp["_month"] == months_sorted[-1]])
    DOV    = float(np.clip((A_base - A_cur) / (A_base + eps), 0.0, 1.0))
    return round(DOV, 6)


def _compute_por(
    df: pd.DataFrame,
    cfg: Dict,
) -> Tuple[float, float, int]:
    """
    POR — Proxy Overfit Ratio.
    Returns (POR_raw, POR_normalized, n_months_available).
    Requires ≥ 2 months.
    """
    eps = cfg["EPSILON"]
    K   = cfg["POR_K"]

    if "resolution_flag" not in df.columns or "true_resolution" not in df.columns:
        return 0.0, 0.0, 0
    if "call_date" not in df.columns:
        return 0.0, 0.0, 0

    tmp = df.copy()
    tmp["_month"] = pd.to_datetime(tmp["call_date"], errors="coerce").dt.to_period("M")
    tmp = tmp.dropna(subset=["_month"])
    n   = tmp["_month"].nunique()

    if n < 2:
        return 0.0, 0.0, n

    months_sorted = sorted(tmp["_month"].unique())

    def _rates(month_df: pd.DataFrame) -> Tuple[float, float]:
        proxy = float(_coerce_flag(month_df["resolution_flag"]).mean())
        true  = float(_coerce_flag(month_df["true_resolution"]).mean())
        return proxy, true

    P_base, T_base = _rates(tmp[tmp["_month"] == months_sorted[0]])
    P_cur,  T_cur  = _rates(tmp[tmp["_month"] == months_sorted[-1]])

    delta_P  = P_cur  - P_base
    delta_T  = T_cur  - T_base
    POR_raw  = float(np.clip(delta_P / (delta_T + eps), 0.0, K))
    POR_norm = float(np.clip((POR_raw - 1.0) / (K - 1.0), 0.0, 1.0))
    return round(POR_raw, 6), round(POR_norm, 6), n


def _compute_ter(df: pd.DataFrame) -> Optional[float]:
    """
    TER — Terminal Exit Rate (diagnostic only, not a SII component).
    Returns churn rate among proxy-resolved calls, or None if columns absent.

    TER ≈ baseline churn → proxy resolution label carries no retention signal.
    NovaWireless benchmark: TER = 27.6% ≈ baseline 27.63% (odds ratio 0.99, p=.78).
    """
    if "resolution_flag" not in df.columns or "customer_is_churned" not in df.columns:
        return None

    resolved_mask  = _coerce_flag(df["resolution_flag"]) == 1
    resolved_calls = df[resolved_mask]
    if len(resolved_calls) == 0:
        return None

    return round(float(_coerce_flag(resolved_calls["customer_is_churned"]).mean()), 6)


def _compute_sii(
    DAR:  float,
    DRL:  float,
    DOV:  float,
    POR:  float,
    cfg:  Dict,
) -> Tuple[float, float, str]:
    """
    SII — System Integrity Index.
    Returns (SII_raw, SII_gated, status) where status ∈ {'VETO', 'WATCH', 'OK'}.

    SII is not a performance score.  It is a velocity regulator — a veto
    condition on unchecked proxy acceleration.
    """
    w = cfg["SII_weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-6, (
        f"SII weights must sum to 1.0, got {sum(w.values()):.6f}"
    )

    SII_raw   = 100.0 * (
        w["DAR"] * DAR + w["DRL"] * DRL + w["DOV"] * DOV + w["POR"] * POR
    )
    SII_gated = 100.0 if DOV >= cfg["DOV_tau"] else SII_raw

    if SII_gated >= cfg["SII_veto"]:
        status = "VETO"
    elif SII_gated >= cfg["SII_watch"]:
        status = "WATCH"
    else:
        status = "OK"

    return round(SII_raw, 4), round(SII_gated, 4), status


# ── Orchestrator ──────────────────────────────────────────────────────────────

def compute_paper_signals(
    df:  pd.DataFrame,
    cfg: Optional[Dict] = None,
) -> Dict:
    """
    Compute all six Aulabaugh (2026) governance signals from call-level data.

    Parameters
    ----------
    df  : pd.DataFrame — scored calls (output of ``compute_trust_signals``)
    cfg : dict          — calibration overrides (defaults: PAPER_SIGNAL_DEFAULTS)

    Returns
    -------
    dict with top-level keys: DAR, DRL, DOV, POR, TER, SII, summary
    """
    if cfg is None:
        cfg = PAPER_SIGNAL_DEFAULTS.copy()

    DAR_raw,  DAR_norm              = _compute_dar(df, cfg)
    DRL_raw,  DRL_norm, drl_months  = _compute_drl(df, cfg)
    DOV_norm                        = _compute_dov(df, cfg)
    POR_raw,  POR_norm, por_months  = _compute_por(df, cfg)
    TER                             = _compute_ter(df)
    SII_raw,  SII_gated, status     = _compute_sii(
        DAR_norm, DRL_norm, DOV_norm, POR_norm, cfg
    )

    baseline_churn = None
    if "customer_is_churned" in df.columns:
        baseline_churn = round(
            float(_coerce_flag(df["customer_is_churned"]).mean()), 6
        )

    drl_needs_more = drl_months < 2
    por_needs_more = por_months < 2

    return {
        "DAR": {
            "full_name":  "Delayed Adverse Rate",
            "raw":        DAR_raw,
            "normalized": DAR_norm,
            "formula":    "F / D  where F=repeat contacts 31–60d among resolved, D=resolved calls",
            "bounds":     {"L": cfg["DAR_L"], "H": cfg["DAR_H"]},
        },
        "DRL": {
            "full_name":            "Downstream Remediation Load",
            "raw":                  DRL_raw,
            "normalized":           DRL_norm,
            "formula":              "JS(p ∥ q)  Jensen–Shannon divergence, current vs baseline scenario mix",
            "bounds":               {"L": cfg["DRL_L"], "H": cfg["DRL_H"]},
            "n_months_available":   drl_months,
            "requires_multi_month": True,
            "note": (
                "Requires ≥ 2 months of data.  Value is 0.0 when only 1 month "
                "available — not a zero-drift finding."
                if drl_needs_more else None
            ),
        },
        "DOV": {
            "full_name":          "Durable Outcome Validation",
            "normalized":         DOV_norm,
            "formula":            "clamp((A_base − A_cur) / (A_base + ε), 0, 1)",
            "DOV_gate_tau":       cfg["DOV_tau"],
            "DOV_gate_triggered": DOV_norm >= cfg["DOV_tau"],
        },
        "POR": {
            "full_name":            "Proxy Overfit Ratio",
            "raw":                  POR_raw,
            "normalized":           POR_norm,
            "formula":              "clamp(ΔP/(ΔT+ε), 0, K) → clamp((raw−1)/(K−1), 0, 1)",
            "K":                    cfg["POR_K"],
            "n_months_available":   por_months,
            "requires_multi_month": True,
            "note": (
                "Requires ≥ 2 months of data.  Value is 0.0 when only 1 month "
                "available — not a zero-imbalance finding."
                if por_needs_more else None
            ),
        },
        "TER": {
            "full_name":          "Terminal Exit Rate",
            "value":              TER,
            "baseline_churn":     baseline_churn,
            "delta_vs_baseline":  (
                round(TER - baseline_churn, 6)
                if TER is not None and baseline_churn is not None else None
            ),
            "formula":  "churn rate among proxy-resolved calls",
            "note":     (
                "Diagnostic only — not a SII component.  "
                "TER ≈ baseline churn = proxy carries no retention signal."
            ),
        },
        "SII": {
            "full_name":       "System Integrity Index",
            "raw":             SII_raw,
            "gated":           SII_gated,
            "status":          status,
            "DOV_gate_applied": DOV_norm >= cfg["DOV_tau"],
            "formula":  (
                "100 · (0.30·DAR + 0.20·DRL + 0.25·DOV + 0.25·POR); "
                "DOV ≥ τ → SII_gated = 100"
            ),
            "weights":     cfg["SII_weights"],
            "thresholds":  {"veto": cfg["SII_veto"], "watch": cfg["SII_watch"]},
        },
        "summary": {
            "SII_gated": SII_gated,
            "status":    status,
            "component_scores": {
                "DAR": DAR_norm,
                "DRL": DRL_norm,
                "DOV": DOV_norm,
                "POR": POR_norm,
            },
            "TER":            TER,
            "baseline_churn": baseline_churn,
        },
    }


# ── Human-readable rendering ──────────────────────────────────────────────────

def format_paper_signals_text(signals: Dict) -> List[str]:
    """Render paper signals as human-readable report lines."""
    s   = signals["summary"]
    sii = signals["SII"]
    dar = signals["DAR"]
    drl = signals["DRL"]
    dov = signals["DOV"]
    por = signals["POR"]
    ter = signals["TER"]

    status_str = {
        "VETO":  "⛔ VETO  — Halt AI optimization. Re-audit measurement environment.",
        "WATCH": "⚠  WATCH — Drift detected. Human review before next optimization cycle.",
        "OK":    "✓  OK    — Measurement environment within governance bounds.",
    }.get(sii["status"], sii["status"])

    lines = [
        "PAPER GOVERNANCE SIGNALS (Aulabaugh 2026)",
        "=" * 60,
        f"  SII (System Integrity Index): {sii['gated']:.1f} / 100   {status_str}",
    ]
    if sii["DOV_gate_applied"]:
        lines.append(
            f"  ⚠ DOV gate triggered (DOV={dov['normalized']:.4f} >= τ={dov['DOV_gate_tau']}) "
            f"→ SII forced to 100"
        )
    lines += [
        "",
        "  Signal Breakdown (higher = worse; SII weights in parens):",
        f"    DAR — Delayed Adverse Rate        (w=0.30): {dar['normalized']:.4f}  [raw={dar['raw']:.4f}]",
        f"    DRL — Downstream Remediation Load (w=0.20): {drl['normalized']:.4f}  [raw={drl['raw']:.4f}]",
        f"    DOV — Durable Outcome Validation  (w=0.25): {dov['normalized']:.4f}",
        f"    POR — Proxy Overfit Ratio         (w=0.25): {por['normalized']:.4f}  [raw={por['raw']:.4f}]",
        "",
        "  TER — Terminal Exit Rate (diagnostic, not in SII):",
    ]
    if ter["value"] is not None:
        delta     = ter.get("delta_vs_baseline")
        delta_str = f"  (Δ vs baseline: {delta:+.4f})" if delta is not None else ""
        lines.append(
            f"    Proxy-resolved churn: {ter['value']:.4f}  |  "
            f"Baseline churn: {ter.get('baseline_churn', 'N/A')}{delta_str}"
        )
        if (
            ter["value"] is not None
            and ter.get("baseline_churn") is not None
            and abs(ter["value"] - ter["baseline_churn"]) < 0.02
        ):
            lines.append(
                "    → TER ≈ baseline: proxy resolution flag carries NO retention signal."
            )
    else:
        lines.append("    N/A (churn data not available)")

    lines += [
        "",
        "  Normalization bounds:",
        f"    DAR: L={dar['bounds']['L']}, H={dar['bounds']['H']}",
        f"    DRL: L={drl['bounds']['L']}, H={drl['bounds']['H']}",
        f"    POR: K={por['K']}  (POR_raw saturates at proxy improving {por['K']}× faster than true)",
        f"    DOV gate τ={dov['DOV_gate_tau']}  |  SII VETO ≥ {sii['thresholds']['veto']}  "
        f"WATCH ≥ {sii['thresholds']['watch']}",
    ]
    return lines
