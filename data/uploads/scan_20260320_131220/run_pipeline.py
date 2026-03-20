#!/usr/bin/env python3
"""
run_pipeline.py
----------------
NovaWireless Trust Signal Health Pipeline v3.0
Aulabaugh (2026): When KPIs Lie — Governance Signals for AI-Optimized Call Centers

Usage
-----
From repo root:
    python src/run_pipeline.py
    python src/run_pipeline.py --dupe_policy quarantine_extras_keep_latest
    python src/run_pipeline.py --min_calls_for_rank 30

Output
------
    output/
    ├── data/
    │   ├── calls_clean.csv              calls_quarantine.csv
    │   ├── integrity_flags.csv          calls_scored.csv
    │   ├── rep_summary.csv              scenario_summary.csv
    │   ├── customer_summary.csv         monthly_trends.csv
    │   └── churn_by_trust_decile.csv
    ├── figures/
    │   ├── trust_score_distribution.png    proxy_vs_true_by_scenario.png
    │   ├── rep_trust_landscape.png         scenario_drift_heatmap.png
    │   ├── credit_type_by_scenario.png     rep_signal_correlations.png
    │   ├── monthly_trust_trend.png         monthly_gap_trend.png
    │   ├── churn_by_trust_decile.png       rep_dar_ranking.png
    │   ├── scenario_dov.png                scripted_language_by_scenario.png
    │   └── kardashev_trust_classification.png
    └── reports/
        ├── integrity_summary.json          governance_report.json
        ├── threshold_alerts.json           threshold_alerts.txt
        ├── paper_signals.json              summary_report.txt
        └── kardashev_report.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── Allow running directly from src/ or from repo root ───────────────────────
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import numpy as np
import pandas as pd

from novawireless.pipeline import (
    load_monthly_files, ensure_output_dirs, save_json,
    run_integrity_gate, IntegrityConfig, ThresholdConfig,
    compute_trust_signals,
    summarize_by_rep, summarize_by_scenario,
    summarize_by_customer, compute_monthly_trends,
    compute_churn_by_trust_decile,
    compute_paper_signals, format_paper_signals_text, PAPER_SIGNAL_DEFAULTS,
    run_threshold_alerts, write_threshold_alerts_txt,
    write_summary_report, build_governance_report,
    chart_trust_distribution, chart_proxy_truth_gap, chart_rep_landscape,
    chart_scenario_drift_heatmap, chart_credit_analysis, chart_corr_heatmap,
    chart_monthly_trust_trend, chart_monthly_gap_trend, chart_churn_by_trust_decile,
    chart_rep_dar_ranking, chart_scenario_dov, chart_scripted_language,
    chart_kardashev_tier,
)

# Kardashev classifier — graceful degradation if absent
try:
    from novawireless.kardashev import (
        classify_from_pipeline,
        apply_kardashev_classification,
        KardashevResult,
        SII_WATCH_THRESHOLD,
        SII_VETO_THRESHOLD,
    )
    _KARDASHEV_AVAILABLE = True
except ImportError:
    _KARDASHEV_AVAILABLE = False


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "NovaWireless Trust Signal Health Pipeline v3.0  "
            "(Aulabaugh 2026 — When KPIs Lie)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--dupe_policy",
        default="quarantine_extras_keep_latest",
        choices=[
            "quarantine_all",
            "quarantine_extras_keep_latest",
            "quarantine_extras_keep_first",
        ],
        help="Duplicate call-ID handling policy (default: keep_latest)",
    )
    p.add_argument(
        "--min_calls_for_rank",
        type=int,
        default=20,
        help="Minimum calls for a rep to appear in rankings (default: 20)",
    )
    p.add_argument(
        "--data_dir",
        default=None,
        help="Override path to data directory (default: <repo_root>/data/raw)",
    )
    return p


# ── Main pipeline ─────────────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace) -> int:
    from novawireless.pipeline.loader import find_repo_root

    repo_root = find_repo_root(Path.cwd())
    data_dir  = Path(args.data_dir) if args.data_dir else repo_root / "data" / "raw"
    out_dirs  = ensure_output_dirs(repo_root)
    fig_dir   = out_dirs["figures"]

    _banner("TRUST SIGNAL HEALTH PIPELINE v3.0")
    print(f"  Paper:    Aulabaugh (2026): When KPIs Lie")
    print(f"  Repo:     {repo_root}")
    print(f"  Data:     {data_dir}")
    print(f"  Output:   {out_dirs['base']}")
    print(f"  Kardashev classification: {'enabled' if _KARDASHEV_AVAILABLE else 'UNAVAILABLE'}")
    print()

    # ── 1. Load ───────────────────────────────────────────────────────────────
    _step("Loading monthly files...")
    df_raw = load_monthly_files(data_dir)

    # ── 2. Integrity gate ─────────────────────────────────────────────────────
    _step("Running integrity gate...")
    gate = run_integrity_gate(
        df_raw, out_dirs, cfg=IntegrityConfig(), dupe_policy=args.dupe_policy
    )
    s = gate["summary"]
    print(
        f"  Clean: {s['rows_clean']:,}  |  "
        f"Quarantined: {s['rows_quarantined']:,} "
        f"({s['quarantine_rate']:.2%})\n"
    )

    # ── 3. Trust signal scoring ───────────────────────────────────────────────
    _step("Computing trust signals...")
    df_clean  = gate["clean_df"].copy()
    if "_source_file" in df_clean.columns:
        df_clean = df_clean.drop(columns=["_source_file"])
    df_scored = compute_trust_signals(df_clean)
    df_scored.to_csv(out_dirs["data"] / "calls_scored.csv", index=False)
    print(
        f"  Scored {len(df_scored):,} rows  |  "
        f"Mean trust: {df_scored['call_trust_score'].mean():.1f}\n"
    )

    # ── 4. Aggregation ────────────────────────────────────────────────────────
    _step("Building summaries...")
    rep_summary      = summarize_by_rep(df_scored, min_calls=args.min_calls_for_rank)
    scenario_summary = summarize_by_scenario(df_scored)
    customer_summary = summarize_by_customer(df_scored)
    rep_summary.to_csv(      out_dirs["data"] / "rep_summary.csv",      index=False)
    scenario_summary.to_csv( out_dirs["data"] / "scenario_summary.csv", index=False)
    customer_summary.to_csv( out_dirs["data"] / "customer_summary.csv", index=False)
    print(
        f"  Reps: {len(rep_summary)}  |  "
        f"Scenarios: {len(scenario_summary)}  |  "
        f"Customers: {len(customer_summary)}\n"
    )

    # ── 5. Monthly trends ─────────────────────────────────────────────────────
    _step("Computing monthly trends...")
    monthly_trends = compute_monthly_trends(df_scored)
    if not monthly_trends.empty:
        monthly_trends.to_csv(out_dirs["data"] / "monthly_trends.csv", index=False)
        vel = monthly_trends["trust_velocity"].dropna()
        if len(vel):
            print(
                f"  {len(monthly_trends)} months  |  "
                f"Velocity range: {vel.min():+.2f} to {vel.max():+.2f} pts/month"
            )
    print()

    # ── 6. Churn by trust decile ──────────────────────────────────────────────
    _step("Computing churn by trust decile...")
    churn_decile = compute_churn_by_trust_decile(df_scored)
    if not churn_decile.empty:
        churn_decile.to_csv(out_dirs["data"] / "churn_by_trust_decile.csv", index=False)
        corr = churn_decile.attrs.get("trust_churn_correlation", None)
        print(
            f"  Trust–Churn correlation: r = {corr:.4f}"
            if corr is not None else "  Churn correlation: N/A"
        )
    else:
        print("  Churn data not available — skipping")
    print()

    # ── 7. Paper governance signals (Appendix A) ──────────────────────────────
    _step("Computing paper governance signals (Aulabaugh 2026)...")
    paper_signals = compute_paper_signals(df_scored)
    save_json(out_dirs["reports"] / "paper_signals.json", paper_signals)
    ps         = paper_signals["summary"]
    sii_status = paper_signals["SII"]["status"]
    sii_gated  = ps["SII_gated"]

    drl_note = " [N/A: needs ≥2 months]" if paper_signals["DRL"].get("n_months_available", 2) < 2 else ""
    por_note = " [N/A: needs ≥2 months]" if paper_signals["POR"].get("n_months_available", 2) < 2 else ""
    print(
        f"  DAR={ps['component_scores']['DAR']:.4f}  "
        f"DRL={ps['component_scores']['DRL']:.4f}{drl_note}  "
        f"DOV={ps['component_scores']['DOV']:.4f}  "
        f"POR={ps['component_scores']['POR']:.4f}{por_note}"
    )
    print(f"  SII (gated): {sii_gated:.1f} → {sii_status}")
    if paper_signals["TER"]["value"] is not None:
        print(
            f"  TER: {paper_signals['TER']['value']:.4f}  "
            f"baseline churn: {paper_signals['TER'].get('baseline_churn', 'N/A')}"
        )
    _sii_banner(sii_status)
    print()

    # ── 8. Kardashev Trust Classification (Section 7) ─────────────────────────
    kardashev_result = None
    if _KARDASHEV_AVAILABLE:
        _step("Computing Kardashev Trust Classification (Section 7)...")
        try:
            kardashev_result = classify_from_pipeline(paper_signals, df_scored)
            tier_icon = {1: "⛔", 2: "⚠ ", 3: "✓ "}.get(
                kardashev_result.kardashev_type, "  "
            )
            print(
                f"  {tier_icon} {kardashev_result.kardashev_label}  "
                f"[{kardashev_result.circuit_breaker}]"
            )
            print(
                f"  Goodhart Gap: {kardashev_result.goodhart_gap:.1%}  "
                f"SII: {sii_gated:.1f}"
            )
            if kardashev_result.kardashev_type == 1:
                print(f"  ⛔ {kardashev_result.reason[:100]}…")

            # Save standalone Kardashev report
            save_json(
                out_dirs["reports"] / "kardashev_report.json",
                {
                    "kardashev_type":    kardashev_result.kardashev_type,
                    "kardashev_label":   kardashev_result.kardashev_label,
                    "kardashev_tier":    kardashev_result.kardashev_tier,
                    "circuit_breaker":   kardashev_result.circuit_breaker,
                    "goodhart_gap":      round(kardashev_result.goodhart_gap, 4),
                    "reason":            kardashev_result.reason,
                    "sii_gated":         sii_gated,
                    "paper_section":     "Aulabaugh (2026), Section 7",
                    "override_thresholds": {
                        "bandaid_rate":    "> 50%",
                        "gaming_lift":     "> 20×",
                        "repeat_rate":     "> 40%",
                        "drift_score":     "> 0.60",
                        "goodhart_gap":    "> 25pp",
                    },
                },
            )

            # Rep-level Kardashev (uses system SII as conservative proxy)
            if not rep_summary.empty:
                rep_classify_df = rep_summary.assign(
                    sii_score           = sii_gated,
                    proxy_kpi           = rep_summary["proxy_resolution_rate"],
                    true_crt            = rep_summary["true_resolution_rate"],
                    repeat_rate         = rep_summary["repeat_31_60d_rate"],
                    drift_score         = rep_summary["rep_drift_avg"],
                    bandaid_credit_rate = rep_summary.get("bandaid_rate", 0.0),
                    gaming_term_lift    = 0.0,
                )
                try:
                    rep_summary = apply_kardashev_classification(rep_classify_df)
                    rep_summary.to_csv(
                        out_dirs["data"] / "rep_summary.csv", index=False
                    )
                    type_i_reps = int((rep_summary["kardashev_type"] == 1).sum())
                    print(
                        f"  Rep-level: {type_i_reps} Type I, "
                        f"{int((rep_summary['kardashev_type'] == 2).sum())} Type II, "
                        f"{int((rep_summary['kardashev_type'] == 3).sum())} Type III"
                    )
                except Exception as e:
                    print(f"  Rep-level Kardashev failed: {e}")
        except Exception as e:
            print(f"  Kardashev classification failed: {e}")
    else:
        print("  [kardashev] Classifier not on path — skipping Section 7 output")
    print()

    # ── 9. Threshold alerts ───────────────────────────────────────────────────
    _step("Evaluating governance thresholds...")
    thresholds    = ThresholdConfig()
    alert_summary = run_threshold_alerts(
        scenario_summary, rep_summary, monthly_trends, thresholds
    )
    save_json(out_dirs["reports"] / "threshold_alerts.json", alert_summary)
    write_threshold_alerts_txt(
        alert_summary, out_dirs["reports"] / "threshold_alerts.txt"
    )
    print(
        f"  Alerts: {alert_summary['total_alerts']} "
        f"(VETO: {alert_summary['veto_count']}, "
        f"WATCH: {alert_summary['watch_count']})\n"
    )

    # ── 10. Charts ────────────────────────────────────────────────────────────
    _step("Generating charts...")
    chart_trust_distribution(df_scored, fig_dir)
    chart_proxy_truth_gap(df_scored, fig_dir)
    chart_rep_landscape(rep_summary, fig_dir)
    chart_scenario_drift_heatmap(scenario_summary, fig_dir)
    chart_credit_analysis(df_scored, fig_dir)
    chart_corr_heatmap(rep_summary, fig_dir)
    chart_monthly_trust_trend(monthly_trends, fig_dir)
    chart_monthly_gap_trend(monthly_trends, fig_dir)
    chart_churn_by_trust_decile(churn_decile, fig_dir)
    chart_rep_dar_ranking(rep_summary, fig_dir)
    chart_scenario_dov(scenario_summary, fig_dir)
    chart_scripted_language(df_scored, scenario_summary, fig_dir)
    chart_kardashev_tier(kardashev_result, rep_summary, fig_dir, sii_gated=sii_gated)
    print("  13 charts written to output/figures/\n")

    # ── 11. Reports ───────────────────────────────────────────────────────────
    _step("Writing reports...")
    write_summary_report(
        df_scored, rep_summary=rep_summary, scenario_summary=scenario_summary,
        monthly_trends=monthly_trends, alert_summary=alert_summary,
        churn_decile=churn_decile, integrity_summary=s,
        outpath=out_dirs["reports"] / "summary_report.txt",
        min_calls_for_rank=args.min_calls_for_rank,
        paper_signals=paper_signals,
        kardashev_result=kardashev_result,
    )
    gov_report = build_governance_report(
        integrity_summary=s, scenario_summary=scenario_summary,
        rep_summary=rep_summary, monthly_trends=monthly_trends,
        alert_summary=alert_summary, churn_decile=churn_decile,
        df_scored=df_scored, paper_signals=paper_signals,
        kardashev_result=kardashev_result,
    )
    save_json(out_dirs["reports"] / "governance_report.json", gov_report)
    print("  Reports written to output/reports/\n")

    # ── 12. Console summary ───────────────────────────────────────────────────
    _banner("PIPELINE COMPLETE")
    proxy = _safe_mean(df_scored, "resolution_flag")
    true  = _safe_mean(df_scored, "true_resolution")
    print(
        f"Input:    {s.get('months_loaded', '?')} monthly files "
        f"({s['rows_total']:,} rows total)"
    )
    print(f"Clean:    {s['rows_clean']:,} rows → scored → aggregated → reported")
    print()
    print(f"Mean trust score:     {df_scored['call_trust_score'].mean():.1f} / 100")
    print(
        f"Resolution inflation: {100*(proxy-true):.1f}pp "
        f"(proxy {100*proxy:.1f}% vs true {100*true:.1f}%)"
    )
    print(
        f"Governance alerts:    {alert_summary['total_alerts']} "
        f"(VETO: {alert_summary['veto_count']}, "
        f"WATCH: {alert_summary['watch_count']})"
    )
    print(
        f"SII: {sii_gated:.1f} [{sii_status}]  "
        f"DAR={ps['component_scores']['DAR']:.3f}  "
        f"DRL={ps['component_scores']['DRL']:.3f}  "
        f"DOV={ps['component_scores']['DOV']:.3f}  "
        f"POR={ps['component_scores']['POR']:.3f}"
    )
    if kardashev_result is not None:
        tier_icon = {1: "⛔", 2: "⚠ ", 3: "✓ "}.get(
            kardashev_result.kardashev_type, "  "
        )
        print(
            f"Kardashev tier:   {tier_icon} {kardashev_result.kardashev_label}  "
            f"[{kardashev_result.circuit_breaker}]"
        )
    print()
    print("Output:")
    print("  output/data/         (CSVs)  output/figures/  (13 PNGs)")
    print("  output/reports/      (JSON + TXT)")
    print()
    return 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _banner(msg: str) -> None:
    print()
    print("=" * 60)
    print(f"  {msg}")
    print("=" * 60)


def _step(msg: str) -> None:
    print(msg)


def _sii_banner(status: str) -> None:
    if status == "VETO":
        print("  ⛔ SII VETO — halt AI optimization, re-audit measurement environment")
    elif status == "WATCH":
        print("  ⚠  SII WATCH — human review required before next optimization cycle")
    else:
        print("  ✓  SII OK — measurement environment within governance bounds")


def _safe_mean(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return 0.0
    from novawireless.pipeline.integrity import _coerce_flag
    return float(_coerce_flag(df[col]).mean())


# ── Entry point ───────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    parser = build_parser()
    args   = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
