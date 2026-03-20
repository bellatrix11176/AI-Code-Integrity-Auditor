"""
novawireless.pipeline.reports
-------------------------------
Report generation — summary_report.txt and governance_report.json.

Both reports integrate all pipeline stages:
  integrity gate → signal scoring → aggregations → paper signals →
  Kardashev classification → alerts
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .loader    import save_json
from .signals   import _safe_coerce
from .paper_signals import format_paper_signals_text


# ── Governance JSON report ────────────────────────────────────────────────────

def build_governance_report(
    integrity_summary: Dict,
    scenario_summary:  pd.DataFrame,
    rep_summary:       pd.DataFrame,
    monthly_trends:    pd.DataFrame,
    alert_summary:     Dict,
    churn_decile:      pd.DataFrame,
    df_scored:         pd.DataFrame,
    paper_signals:     Optional[Dict] = None,
    kardashev_result:  Any            = None,   # KardashevResult | None
) -> Dict:
    """
    Build the master governance JSON report.

    All pipeline outputs are combined into a single structured document
    suitable for downstream dashboards, version control, and audit trails.

    Parameters
    ----------
    kardashev_result : KardashevResult or None
        If provided, adds a ``kardashev_classification`` block to the report.
    """
    proxy_rate = _safe_coerce(df_scored, "resolution_flag").mean()
    true_rate  = _safe_coerce(df_scored, "true_resolution").mean()
    trust      = df_scored["call_trust_score"]

    report: Dict = {
        "meta": {
            "pipeline_version": "3.0.0",
            "generated":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rows_analyzed":    len(df_scored),
            "months_loaded":    integrity_summary.get("months_loaded", 0),
            "paper":            "Aulabaugh (2026): When KPIs Lie",
        },
        "integrity_gate": {
            "rows_total":       integrity_summary.get("rows_total", 0),
            "rows_clean":       integrity_summary.get("rows_clean", 0),
            "rows_quarantined": integrity_summary.get("rows_quarantined", 0),
            "quarantine_rate":  round(integrity_summary.get("quarantine_rate", 0), 4),
            "proxy_true_divergence_rate": round(
                integrity_summary.get("soft_signal_rates", {})
                .get("proxy_true_divergence", 0), 4
            ),
        },
        "overall_signals": {
            "proxy_resolution_rate":    round(float(proxy_rate), 4),
            "true_resolution_rate":     round(float(true_rate),  4),
            "resolution_inflation_pp":  round(float(100 * (proxy_rate - true_rate)), 2),
            "trust_score_mean":         round(float(trust.mean()),           2),
            "trust_score_median":       round(float(trust.median()),         2),
            "trust_score_p10":          round(float(trust.quantile(0.10)),   2),
            "trust_score_p90":          round(float(trust.quantile(0.90)),   2),
            "repeat_contact_30d_rate":  round(float(_safe_coerce(df_scored, "repeat_contact_30d").mean()),  4),
            "escalation_rate":          round(float(_safe_coerce(df_scored, "escalation_flag").mean()),     4),
            "bandaid_rate":             round(float(
                (df_scored["credit_type"].astype(str).str.strip() == "bandaid").mean()
                if "credit_type" in df_scored.columns else 0
            ), 4),
        },
        "scenario_health":  [],
        "rep_health": {
            "total_reps":        len(rep_summary),
            "lowest_trust_reps":  [],
            "highest_trust_reps": [],
        },
        "monthly_trends":               [],
        "alerts":                       alert_summary,
        "churn_integration":            {},
        "paper_governance_signals":     paper_signals if paper_signals is not None else {},
        "kardashev_classification": (
            {
                "kardashev_type":   kardashev_result.kardashev_type,
                "kardashev_label":  kardashev_result.kardashev_label,
                "kardashev_tier":   kardashev_result.kardashev_tier,
                "circuit_breaker":  kardashev_result.circuit_breaker,
                "goodhart_gap":     round(kardashev_result.goodhart_gap, 4),
                "reason":           kardashev_result.reason,
                "paper_section":    "Aulabaugh (2026), Section 7",
            }
            if kardashev_result is not None
            else {"note": "kardashev_trust_classifier not available or not run"}
        ),
    }

    # Scenario health
    if not scenario_summary.empty:
        for _, row in scenario_summary.iterrows():
            t = row.get("trust_score_avg", 100)
            report["scenario_health"].append({
                "scenario":       row["scenario"],
                "calls":          int(row["calls"]),
                "trust_score":    round(t, 2),
                "resolution_gap": round(row.get("resolution_gap", 0), 4),
                "bandaid_rate":   round(row.get("bandaid_rate",    0), 4),
                "status": "VETO" if t < 50 else "WATCH" if t < 65 else "OK",
            })

    # Rep health
    if not rep_summary.empty:
        for _, r in rep_summary.head(5).iterrows():
            report["rep_health"]["lowest_trust_reps"].append({
                "rep_id":         r["rep_id"],
                "calls":          int(r["calls"]),
                "trust_score":    round(r["trust_score_avg"], 2),
                "resolution_gap": round(r.get("resolution_gap", 0), 4),
            })
        for _, r in rep_summary.tail(5).iloc[::-1].iterrows():
            report["rep_health"]["highest_trust_reps"].append({
                "rep_id":         r["rep_id"],
                "calls":          int(r["calls"]),
                "trust_score":    round(r["trust_score_avg"], 2),
                "resolution_gap": round(r.get("resolution_gap", 0), 4),
            })

    # Monthly trends
    if not monthly_trends.empty:
        for _, row in monthly_trends.iterrows():
            vel = row.get("trust_velocity", 0)
            report["monthly_trends"].append({
                "month":          str(row["_month"]),
                "calls":          int(row["calls"]),
                "trust_score":    round(row.get("trust_score_avg", 0), 2),
                "resolution_gap": round(row.get("resolution_gap",  0), 4),
                "bandaid_rate":   round(row.get("bandaid_rate",    0), 4),
                "trust_velocity": round(vel, 3) if pd.notna(vel) else None,
            })

    # Churn integration
    if not churn_decile.empty:
        corr = churn_decile.attrs.get("trust_churn_correlation", None)
        report["churn_integration"] = {
            "trust_churn_correlation": corr,
            "interpretation": (
                "Trust score is predictive of churn (negative correlation)."
                if corr is not None and corr < -0.3 else
                "Trust score shows weak/no relationship with churn at call level."
                if corr is not None else
                "Churn data not available."
            ),
            "deciles": [
                {
                    "decile":       int(r["trust_decile"]),
                    "trust_range":  f"{r['trust_score_min']:.1f}–{r['trust_score_max']:.1f}",
                    "calls":        int(r["calls"]),
                    "churn_rate":   round(r.get("churn_rate",    0), 4),
                    "resolution_gap": round(r.get("resolution_gap", 0), 4),
                }
                for _, r in churn_decile.iterrows()
            ],
        }

    return report


# ── Summary text report ───────────────────────────────────────────────────────

def write_summary_report(
    df:                pd.DataFrame,
    rep_summary:       pd.DataFrame,
    scenario_summary:  pd.DataFrame,
    monthly_trends:    pd.DataFrame,
    alert_summary:     Dict,
    churn_decile:      pd.DataFrame,
    integrity_summary: Dict,
    outpath:           Path,
    min_calls_for_rank: int  = 20,
    paper_signals:     Optional[Dict] = None,
    kardashev_result:  Any            = None,
) -> None:
    """Write the human-readable summary report to ``outpath``."""
    n = len(df)
    if n == 0:
        outpath.write_text("No rows found.\n", encoding="utf-8")
        return

    def pct(x: float) -> str:
        return f"{100 * x:.1f}%"

    lines = [
        "TRUST SIGNAL HEALTH PIPELINE — SUMMARY REPORT v3.0",
        "=" * 60,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Paper: Aulabaugh (2026): When KPIs Lie — Governance Signals for AI-Optimized Call Centers",
        f"Rows analyzed: {n:,}",
        f"Months loaded: {integrity_summary.get('months_loaded', '?')}",
        "",
    ]

    # Integrity gate
    lines += [
        "INTEGRITY GATE",
        f"  Total rows:       {integrity_summary.get('rows_total', n):,}",
        f"  Clean rows:       {integrity_summary.get('rows_clean', n):,}",
        f"  Quarantined:      {integrity_summary.get('rows_quarantined', 0):,} "
        f"({pct(integrity_summary.get('quarantine_rate', 0))})",
    ]
    soft = integrity_summary.get("soft_signal_rates", {})
    if soft.get("proxy_true_divergence", 0) > 0:
        lines.append(
            f"  Proxy-true divergence (soft signal, not quarantined): "
            f"{pct(soft['proxy_true_divergence'])}"
        )
    lines.append("")

    # Overall signals
    pr = _safe_coerce(df, "resolution_flag").mean()
    tr = _safe_coerce(df, "true_resolution").mean()
    lines += [
        "OVERALL SIGNAL RATES",
        f"  Proxy resolution rate:      {pct(pr)}",
        f"  True resolution rate:       {pct(tr)}",
        f"  Resolution inflation:       {pct(pr - tr)}  ← Goodhart Gap",
        f"  Repeat contact (30d) rate:  {pct(_safe_coerce(df, 'repeat_contact_30d').mean())}",
        f"  Escalation rate:            {pct(_safe_coerce(df, 'escalation_flag').mean())}",
        f"  Credit applied rate:        {pct(_safe_coerce(df, 'credit_applied').mean())}",
    ]
    if "credit_type" in df.columns:
        lines.append(
            f"  Bandaid credit rate:        "
            f"{pct((df['credit_type'].astype(str).str.strip() == 'bandaid').mean())}"
            f"  ← unauthorized suppression signal"
        )
    lines.append("")

    # Trust score summary
    trust = df["call_trust_score"]
    lines += [
        "TRUST SCORE SUMMARY",
        f"  Mean:   {trust.mean():.1f}",
        f"  Median: {trust.median():.1f}",
        f"  Std:    {trust.std():.1f}",
        f"  P10:    {trust.quantile(0.10):.1f}",
        f"  P90:    {trust.quantile(0.90):.1f}",
        "",
    ]

    # Scenario health
    if not scenario_summary.empty:
        lines.append("SCENARIO HEALTH (sorted by trust score, lowest first)")
        lines.append(
            f"  {'Scenario':<28} {'Calls':>7} {'Trust':>7} "
            f"{'Gap':>7} {'Bandaid':>8} {'DOV':>7}"
        )
        lines.append("  " + "─" * 68)
        for _, r in scenario_summary.iterrows():
            dov_str = f"{r['scenario_dov']:.3f}" if "scenario_dov" in r and pd.notna(r.get("scenario_dov")) else "  —"
            lines.append(
                f"  {r['scenario']:<28} {int(r['calls']):>7,} "
                f"{r['trust_score_avg']:>7.1f} "
                f"{pct(r.get('resolution_gap', 0)):>7} "
                f"{pct(r.get('bandaid_rate', 0)):>8} "
                f"{dov_str:>7}"
            )
        lines.append("")

    # Monthly trends
    if not monthly_trends.empty:
        lines.append("MONTHLY TREND SUMMARY")
        lines.append(
            f"  {'Month':<12} {'Calls':>7} {'Trust':>7} "
            f"{'Gap':>7} {'Bandaid':>8} {'Velocity':>10}"
        )
        lines.append("  " + "─" * 60)
        for _, r in monthly_trends.iterrows():
            vel = r.get("trust_velocity", 0)
            vs  = f"{vel:>+.2f}" if pd.notna(vel) else "    —"
            lines.append(
                f"  {str(r['_month']):<12} {int(r['calls']):>7,} "
                f"{r['trust_score_avg']:>7.1f} "
                f"{pct(r.get('resolution_gap', 0)):>7} "
                f"{pct(r.get('bandaid_rate', 0)):>8} "
                f"{vs:>10}"
            )
        lines.append("")

    # Rep rankings
    if not rep_summary.empty:
        qual = rep_summary[rep_summary["calls"] >= min_calls_for_rank]
        lines += [
            f"REP RANKINGS  (≥ {min_calls_for_rank} calls)",
            f"  Total reps: {len(rep_summary)}   Qualified: {len(qual)}",
            "",
        ]
        if not qual.empty:
            lines.append("  LOWEST TRUST (most concerning):")
            for _, r in qual.head(5).iterrows():
                lines.append(
                    f"    {r['rep_id']}  calls={int(r['calls'])}  "
                    f"trust={r['trust_score_avg']:.1f}  "
                    f"gap={pct(r.get('resolution_gap', 0))}  "
                    f"bandaid={pct(r.get('bandaid_rate', 0))}  "
                    f"DAR={r.get('rep_dar', float('nan')):.3f}"
                )
            lines.append("")
            lines.append("  HIGHEST TRUST (healthiest):")
            for _, r in qual.tail(5).iloc[::-1].iterrows():
                lines.append(
                    f"    {r['rep_id']}  calls={int(r['calls'])}  "
                    f"trust={r['trust_score_avg']:.1f}  "
                    f"gap={pct(r.get('resolution_gap', 0))}"
                )
        lines.append("")

    # Churn integration
    if not churn_decile.empty:
        corr = churn_decile.attrs.get("trust_churn_correlation", None)
        lines.append("CHURN INTEGRATION — Trust Score Predictive Power")
        if corr is not None:
            lines.append(f"  Trust–Churn Correlation: r = {corr:.4f}")
            if corr < -0.3:
                lines.append("  ► Trust IS predictive of churn. Lower trust = higher churn.")
            elif corr < -0.1:
                lines.append("  ► Weak negative relationship. Marginal predictive value.")
            else:
                lines += [
                    "  ► Trust shows minimal call-level churn prediction.",
                    "    Consistent with finding that churn signal is structurally diffuse.",
                ]
        lines.append("")
        lines.append(
            f"  {'Decile':<8} {'Trust Range':<14} {'Calls':>7} {'Churn':>7} {'Gap':>7}"
        )
        lines.append("  " + "─" * 50)
        for _, r in churn_decile.iterrows():
            lines.append(
                f"  D{int(r['trust_decile']):<7} "
                f"{r['trust_score_min']:.0f}–{r['trust_score_max']:.0f}{'':8} "
                f"{int(r['calls']):>7,} "
                f"{pct(r.get('churn_rate', 0)):>7} "
                f"{pct(r.get('resolution_gap', 0)):>7}"
            )
        lines.append("")

    # Paper governance signals
    if paper_signals:
        lines += [""] + format_paper_signals_text(paper_signals) + [""]

    # Kardashev classification
    if kardashev_result is not None:
        tier_badge = {1: "⛔", 2: "⚠ ", 3: "✓ "}.get(
            kardashev_result.kardashev_type, "  "
        )
        lines += [
            "KARDASHEV TRUST CLASSIFICATION (Aulabaugh 2026, Section 7)",
            "=" * 60,
            f"  {tier_badge} {kardashev_result.kardashev_label}",
            f"  Tier:            {kardashev_result.kardashev_tier}",
            f"  Circuit breaker: {kardashev_result.circuit_breaker}",
            f"  Goodhart Gap:    {kardashev_result.goodhart_gap:.1%}",
            f"  Reason:          {kardashev_result.reason}",
            "",
            "  Classification reference (paper Table, Section 7):",
            "  Type I  — Proxy Mastery      SII ≥ 30 or override condition triggered",
            "  Type II — Resolution Mastery SII 10–29, measurable proxy drift",
            "  Type III — Systemic Integrity SII < 10, proxy and outcome aligned",
            "",
            "  Override conditions (any one forces Type I regardless of SII):",
            "    Bandaid rate > 50%  |  Gaming TF-IDF lift > 20×",
            "    Repeat rate > 40%   |  Rep drift score > 0.60",
            "    Goodhart Gap > 25pp",
            "",
        ]

    # Threshold alert summary
    lines += [
        "THRESHOLD ALERTS",
        f"  Total: {alert_summary.get('total_alerts', 0)}  "
        f"(VETO: {alert_summary.get('veto_count', 0)}, "
        f"WATCH: {alert_summary.get('watch_count', 0)})",
    ]
    if alert_summary.get("veto_count", 0) > 0:
        lines.append("  ⚠ VETO conditions present — see threshold_alerts.txt")
    lines.append("")

    # Interpretation guide
    lines += [
        "INTERPRETATION GUIDE",
        "  Resolution inflation = proxy − true rate. Positive = system looks better than it is.",
        "  Bandaid credits = unauthorized credits to suppress repeat contacts.",
        "  Credit burden ratio = credit_amount / monthly_charges. High ratio = substantive",
        "    appeasement (e.g. $25 credit on a $27/month plan) vs a token courtesy gesture.",
        "  Detection signal density = fraction of fraud/gaming/scripted-language indicators firing.",
        "  Rep drift score = aware_gaming (0.45) + gaming_propensity (0.35) + burnout (0.20).",
        "  Rep DAR = rep-level F/D (paper formula). Identifies reps driving 31–60d callbacks.",
        "  Scripted window flag = scripted FCR-gaming language detected in transcript.",
        "  Scenario DOV = proxy label error rate per call type (1 − accuracy). Higher = worse.",
        "  Call trust score (0–100): 100 = fully trustworthy. 0 = total divergence.",
        "  Drift velocity = month-over-month trust score change. Negative = degrading.",
        "  VETO = halt AI optimization; re-audit labels. WATCH = human review required.",
        "  Kardashev tier = narrative rendering of SII for non-technical stakeholders.",
    ]

    outpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
