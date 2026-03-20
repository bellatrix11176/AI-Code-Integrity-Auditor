"""
novawireless.pipeline — Core governance pipeline modules.

Execution order (see run_pipeline.py):
  1. loader        → load_monthly_files()
  2. integrity     → run_integrity_gate()
  3. signals       → compute_trust_signals()
  4. aggregation   → summarize_by_rep/scenario/customer/monthly
                     compute_churn_by_trust_decile()
  5. paper_signals → compute_paper_signals()   ← DAR / DRL / DOV / POR / TER / SII
  6. alerts        → run_threshold_alerts()
  7. charts        → chart_* suite
  8. reports       → write_summary_report() / build_governance_report()
"""

from .loader        import load_monthly_files, ensure_output_dirs, save_json
from .integrity     import run_integrity_gate, IntegrityConfig, ThresholdConfig
from .signals       import compute_trust_signals
from .aggregation   import (
    summarize_by_rep, summarize_by_scenario,
    summarize_by_customer, compute_monthly_trends,
    compute_churn_by_trust_decile,
)
from .paper_signals import compute_paper_signals, format_paper_signals_text, PAPER_SIGNAL_DEFAULTS
from .alerts        import run_threshold_alerts, write_threshold_alerts_txt
from .reports       import write_summary_report, build_governance_report
from .charts        import (
    chart_trust_distribution, chart_proxy_truth_gap, chart_rep_landscape,
    chart_scenario_drift_heatmap, chart_credit_analysis, chart_corr_heatmap,
    chart_monthly_trust_trend, chart_monthly_gap_trend, chart_churn_by_trust_decile,
    chart_rep_dar_ranking, chart_scenario_dov, chart_scripted_language,
    chart_kardashev_tier,
)

__all__ = [
    "load_monthly_files", "ensure_output_dirs", "save_json",
    "run_integrity_gate", "IntegrityConfig", "ThresholdConfig",
    "compute_trust_signals",
    "summarize_by_rep", "summarize_by_scenario", "summarize_by_customer",
    "compute_monthly_trends", "compute_churn_by_trust_decile",
    "compute_paper_signals", "format_paper_signals_text", "PAPER_SIGNAL_DEFAULTS",
    "run_threshold_alerts", "write_threshold_alerts_txt",
    "write_summary_report", "build_governance_report",
    "chart_trust_distribution", "chart_proxy_truth_gap", "chart_rep_landscape",
    "chart_scenario_drift_heatmap", "chart_credit_analysis", "chart_corr_heatmap",
    "chart_monthly_trust_trend", "chart_monthly_gap_trend", "chart_churn_by_trust_decile",
    "chart_rep_dar_ranking", "chart_scenario_dov", "chart_scripted_language",
    "chart_kardashev_tier",
]
