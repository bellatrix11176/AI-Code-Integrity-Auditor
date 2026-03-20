"""
novawireless.pipeline.charts
------------------------------
Matplotlib chart suite for the governance pipeline.

Produces 13 PNG figures in output/figures/:

  trust_score_distribution.png        — call trust score histogram
  proxy_vs_true_by_scenario.png       — proxy vs true resolution by scenario
  rep_trust_landscape.png             — rep scatter: trust vs resolution gap
  scenario_drift_heatmap.png          — heatmap of key signals by scenario
  credit_type_by_scenario.png         — credit type breakdown by scenario
  rep_signal_correlations.png         — correlation heatmap, rep-level signals
  monthly_trust_trend.png             — trust score trajectory
  monthly_gap_trend.png               — Goodhart gap trajectory
  churn_by_trust_decile.png           — churn rate by trust decile
  rep_dar_ranking.png                 — rep-level DAR ranking
  scenario_dov.png                    — scenario DOV (proxy label error rate)
  scripted_language_by_scenario.png   — scripted FCR-gaming language detection
  kardashev_trust_classification.png  — Kardashev tier badge + rep distribution
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


# ── Style constants ───────────────────────────────────────────────────────────

CHART_DPI    = 180
CHART_BG     = "#1a1a2e"
CHART_PANEL  = "#16213e"
CHART_FG     = "#e0e0e0"
CHART_BORDER = "#2a2a4a"
CHART_ACCENT = "#00d4aa"
CHART_WARN   = "#ff6b6b"
CHART_AMBER  = "#ffd93d"
CHART_PURPLE = "#a78bfa"


def _apply_dark_style() -> None:
    plt.rcParams.update({
        "figure.facecolor":  CHART_BG,
        "axes.facecolor":    CHART_PANEL,
        "axes.edgecolor":    CHART_FG,
        "axes.labelcolor":   CHART_FG,
        "text.color":        CHART_FG,
        "xtick.color":       CHART_FG,
        "ytick.color":       CHART_FG,
        "grid.color":        CHART_BORDER,
        "grid.alpha":        0.3,
        "font.size":         10,
    })


def _save(fig_dir: Path, filename: str) -> None:
    plt.tight_layout()
    plt.savefig(fig_dir / filename, dpi=CHART_DPI, bbox_inches="tight")
    plt.close()


# ── Chart functions ───────────────────────────────────────────────────────────

def chart_trust_distribution(df: pd.DataFrame, fig_dir: Path) -> None:
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(12, 6))
    scores = df["call_trust_score"].dropna()
    ax.hist(scores, bins=40, color=CHART_ACCENT, alpha=0.75, edgecolor="none")
    ax.axvline(scores.mean(),   color=CHART_WARN,  ls="--", lw=2, label=f"Mean: {scores.mean():.1f}")
    ax.axvline(scores.median(), color=CHART_AMBER, ls=":",  lw=2, label=f"Median: {scores.median():.1f}")
    ax.set_xlabel("Call Trust Score (0–100)")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of Call Trust Scores")
    ax.legend(facecolor=CHART_PANEL, edgecolor=CHART_FG)
    ax.grid(True, axis="y")
    _save(fig_dir, "trust_score_distribution.png")


def chart_proxy_truth_gap(df: pd.DataFrame, fig_dir: Path) -> None:
    if "scenario" not in df.columns:
        return
    _apply_dark_style()
    from .integrity import _coerce_flag

    scen = (
        df.groupby("scenario")
        .agg(
            proxy=("resolution_flag",  lambda s: _coerce_flag(s).mean()),
            true =("true_resolution",  lambda s: _coerce_flag(s).mean()),
        )
        .reset_index()
        .sort_values("proxy", ascending=True)
    )
    fig, ax = plt.subplots(figsize=(12, max(5, 0.55 * len(scen) + 1)))
    y = np.arange(len(scen)); h = 0.35
    ax.barh(y - h/2, scen["proxy"], h, label="Proxy Resolution", color=CHART_WARN,  alpha=0.85)
    ax.barh(y + h/2, scen["true"],  h, label="True Resolution",  color=CHART_ACCENT, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(scen["scenario"])
    ax.set_xlabel("Rate")
    ax.set_title("Proxy vs True Resolution by Scenario — The Gap is Goodhart's Law")
    ax.legend(facecolor=CHART_PANEL, edgecolor=CHART_FG)
    ax.grid(True, axis="x")
    _save(fig_dir, "proxy_vs_true_by_scenario.png")


def chart_rep_landscape(rep_summary: pd.DataFrame, fig_dir: Path) -> None:
    if rep_summary.empty:
        return
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(12, 7))
    colors = rep_summary["trust_score_avg"].apply(
        lambda t: CHART_WARN if t < 50 else CHART_AMBER if t < 65 else CHART_ACCENT
    )
    ax.scatter(
        rep_summary.get("resolution_gap", 0),
        rep_summary["trust_score_avg"],
        c=colors, s=40, alpha=0.75, edgecolors="none",
    )
    ax.axhline(65, color=CHART_AMBER, ls="--", lw=1, alpha=0.7, label="WATCH (65)")
    ax.axhline(50, color=CHART_WARN,  ls="--", lw=1, alpha=0.7, label="VETO (50)")
    ax.set_xlabel("Resolution Gap (proxy − true rate)")
    ax.set_ylabel("Mean Trust Score")
    ax.set_title("Rep Trust Landscape — Trust Score vs Resolution Gap")
    ax.legend(facecolor=CHART_PANEL, edgecolor=CHART_FG)
    ax.grid(True, alpha=0.3)
    _save(fig_dir, "rep_trust_landscape.png")


def chart_scenario_drift_heatmap(scenario_summary: pd.DataFrame, fig_dir: Path) -> None:
    if scenario_summary.empty:
        return
    _apply_dark_style()
    cols = [c for c in [
        "trust_score_avg", "resolution_gap", "bandaid_rate",
        "detection_density_avg", "outcome_risk_avg",
    ] if c in scenario_summary.columns]
    if not cols:
        return

    data = scenario_summary.set_index("scenario")[cols]
    fig, ax = plt.subplots(figsize=(12, max(5, 0.55 * len(data) + 1)))
    im = ax.imshow(data.values, cmap="RdYlGn_r", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c.replace("_", "\n") for c in cols], fontsize=9)
    ax.set_yticks(range(len(data)))
    ax.set_yticklabels(data.index, fontsize=9)
    ax.set_title("Scenario Signal Heatmap — Normalized Risk (Red = Worse)")
    plt.colorbar(im, ax=ax, fraction=0.03)
    for i in range(len(data)):
        for j, col in enumerate(cols):
            v = data.iloc[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    fontsize=7, color="white" if v > 0.5 else "black")
    _save(fig_dir, "scenario_drift_heatmap.png")


def chart_credit_analysis(df: pd.DataFrame, fig_dir: Path) -> None:
    if "credit_type" not in df.columns or "scenario" not in df.columns:
        return
    _apply_dark_style()
    ct = (
        df.groupby(["scenario", "credit_type"])
        .size()
        .unstack(fill_value=0)
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(13, max(5, 0.55 * len(ct) + 1)))
    ct.plot(kind="barh", stacked=True, ax=ax, colormap="tab10", alpha=0.85)
    ax.set_xlabel("Call Count")
    ax.set_title("Credit Type Distribution by Scenario")
    ax.legend(title="Credit Type", facecolor=CHART_PANEL, edgecolor=CHART_FG,
              loc="lower right", fontsize=9)
    ax.grid(True, axis="x", alpha=0.3)
    _save(fig_dir, "credit_type_by_scenario.png")


def chart_corr_heatmap(rep_summary: pd.DataFrame, fig_dir: Path) -> None:
    if rep_summary.empty:
        return
    _apply_dark_style()
    num_cols = [c for c in [
        "trust_score_avg", "resolution_gap", "rep_drift_avg",
        "credit_risk_avg", "detection_density_avg", "outcome_risk_avg",
        "repeat_31_60d_rate", "bandaid_rate",
    ] if c in rep_summary.columns]
    if len(num_cols) < 3:
        return

    corr = rep_summary[num_cols].corr()
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(num_cols)))
    ax.set_yticks(range(len(num_cols)))
    labels = [c.replace("_", "\n") for c in num_cols]
    ax.set_xticklabels(labels, fontsize=8, rotation=45, ha="right")
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_title("Rep-Level Signal Correlations")
    plt.colorbar(im, ax=ax, fraction=0.04)
    for i in range(len(num_cols)):
        for j in range(len(num_cols)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center",
                    fontsize=7, color="white" if abs(corr.iloc[i, j]) > 0.5 else "black")
    _save(fig_dir, "rep_signal_correlations.png")


def chart_monthly_trust_trend(monthly_trends: pd.DataFrame, fig_dir: Path) -> None:
    if monthly_trends.empty:
        return
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(monthly_trends["_month"], monthly_trends["trust_score_avg"],
            color=CHART_ACCENT, lw=2.5, marker="o", ms=5, label="Mean Trust Score")
    ax.axhline(65, color=CHART_AMBER, ls="--", lw=1.5, alpha=0.8, label="WATCH threshold (65)")
    ax.axhline(50, color=CHART_WARN,  ls="--", lw=1.5, alpha=0.8, label="VETO threshold (50)")
    ax.fill_between(
        monthly_trends["_month"],
        monthly_trends["trust_score_avg"],
        alpha=0.12, color=CHART_ACCENT,
    )
    ax.set_xlabel("Month"); ax.set_ylabel("Mean Trust Score")
    ax.set_title("Monthly Trust Score Trend — Signal Velocity Over Time")
    ax.legend(facecolor=CHART_PANEL, edgecolor=CHART_FG)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45, ha="right")
    _save(fig_dir, "monthly_trust_trend.png")


def chart_monthly_gap_trend(monthly_trends: pd.DataFrame, fig_dir: Path) -> None:
    if monthly_trends.empty or "resolution_gap" not in monthly_trends.columns:
        return
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(monthly_trends["_month"], monthly_trends["resolution_gap"] * 100,
            color=CHART_WARN, lw=2.5, marker="s", ms=5)
    ax.fill_between(
        monthly_trends["_month"],
        monthly_trends["resolution_gap"] * 100,
        alpha=0.15, color=CHART_WARN,
    )
    ax.set_xlabel("Month"); ax.set_ylabel("Resolution Gap (pp)")
    ax.set_title(
        "Monthly Goodhart Gap — Proxy FCR minus True CRT\n"
        "Rising gap = AI is increasingly training on corrupted labels"
    )
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45, ha="right")
    _save(fig_dir, "monthly_gap_trend.png")


def chart_churn_by_trust_decile(churn_decile: pd.DataFrame, fig_dir: Path) -> None:
    if churn_decile.empty:
        return
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(churn_decile["trust_decile"], churn_decile["churn_rate"] * 100,
           color=CHART_WARN, alpha=0.80, edgecolor="none", width=0.75)
    corr = churn_decile.attrs.get("trust_churn_correlation", None)
    title = "Churn Rate by Trust Score Decile"
    if corr is not None:
        title += f"  (trust–churn r = {corr:.3f})"
    ax.set_xlabel("Trust Decile (1 = lowest trust, 10 = highest)")
    ax.set_ylabel("Churn Rate (%)")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig_dir, "churn_by_trust_decile.png")


def chart_rep_dar_ranking(rep_summary: pd.DataFrame, fig_dir: Path) -> None:
    if rep_summary.empty or "rep_dar" not in rep_summary.columns:
        return
    _apply_dark_style()
    data = rep_summary.dropna(subset=["rep_dar"]).nlargest(20, "rep_dar")
    if data.empty:
        return
    fig, ax = plt.subplots(figsize=(12, max(5, 0.45 * len(data) + 1)))
    colors = [CHART_WARN if v > 0.25 else CHART_AMBER if v > 0.10 else CHART_ACCENT
              for v in data["rep_dar"]]
    ax.barh(data["rep_id"], data["rep_dar"] * 100, color=colors, alpha=0.85, edgecolor="none")
    ax.axvline(25, color=CHART_WARN,  ls="--", lw=1.5, alpha=0.7, label="WATCH 25%")
    ax.set_xlabel("Rep-Level DAR — Delayed Adverse Rate (%)")
    ax.set_title(
        "Rep DAR Ranking (Top 20)\n"
        "F/D: repeat contacts 31–60d after labeled resolution"
    )
    ax.legend(facecolor=CHART_PANEL, edgecolor=CHART_FG)
    ax.grid(True, axis="x", alpha=0.3)
    _save(fig_dir, "rep_dar_ranking.png")


def chart_scenario_dov(scenario_summary: pd.DataFrame, fig_dir: Path) -> None:
    if scenario_summary.empty or "scenario_dov" not in scenario_summary.columns:
        return
    _apply_dark_style()
    data = scenario_summary.dropna(subset=["scenario_dov"]).sort_values(
        "scenario_dov", ascending=True
    )
    fig, ax = plt.subplots(figsize=(12, max(5, 0.55 * len(data) + 1)))
    colors = [CHART_WARN if v > 0.35 else CHART_AMBER if v > 0.15 else CHART_ACCENT
              for v in data["scenario_dov"]]
    ax.barh(range(len(data)), data["scenario_dov"], color=colors, alpha=0.85, edgecolor="none")

    if "resolution_gap" in data.columns:
        ax2 = ax.twiny()
        ax2.plot(data["resolution_gap"], range(len(data)), "D", color=CHART_PURPLE,
                 ms=8, alpha=0.8, label="Resolution Gap (proxy − true)")
        ax2.set_xlabel("Resolution Gap (proxy − true rate)", color=CHART_PURPLE)
        ax2.legend(loc="lower right", facecolor=CHART_PANEL, edgecolor=CHART_FG, fontsize=9)

    ax.set_yticks(range(len(data)))
    ax.set_yticklabels(data["scenario"], fontsize=9)
    ax.set_xlabel("Scenario DOV — Proxy Label Error Rate (higher = worse)")
    ax.set_title(
        "Scenario-Level DOV\n"
        "Which call types are corrupting the measurement environment?"
    )
    ax.grid(True, axis="x", alpha=0.3)
    _save(fig_dir, "scenario_dov.png")


def chart_scripted_language(
    df:               pd.DataFrame,
    scenario_summary: pd.DataFrame,
    fig_dir:          Path,
) -> None:
    if "scripted_window_flag" not in df.columns or "scenario" not in df.columns:
        return
    _apply_dark_style()
    from .integrity import _coerce_flag

    scen_scripted = (
        df.groupby("scenario")
        .agg(
            scripted_rate=("scripted_window_flag", lambda s: _coerce_flag(s).mean()),
            repeat_31_60d=(
                "repeat_contact_31_60d", lambda s: _coerce_flag(s).mean()
            ) if "repeat_contact_31_60d" in df.columns else (
                "scripted_window_flag", lambda s: np.nan
            ),
            calls=("call_id", "count"),
        )
        .reset_index()
        .sort_values("scripted_rate", ascending=True)
    )

    fig, ax1 = plt.subplots(figsize=(12, max(5, 0.55 * len(scen_scripted) + 1)))
    y = np.arange(len(scen_scripted))
    ax1.barh(y, scen_scripted["scripted_rate"], color=CHART_WARN, alpha=0.75, edgecolor="none")
    ax1.set_xlabel("Rate")
    ax1.set_title(
        "Scripted Window-Management Language by Scenario\n"
        "(Patterns identified in paper as FCR gaming mechanism)"
    )
    ax1.set_yticks(y)
    ax1.set_yticklabels(scen_scripted["scenario"], fontsize=9)

    if scen_scripted["repeat_31_60d"].notna().any():
        ax2 = ax1.twiny()
        ax2.plot(scen_scripted["repeat_31_60d"], y, "s", color=CHART_ACCENT,
                 ms=8, alpha=0.85, label="31–60d Repeat Rate")
        ax2.set_xlabel("31–60d Repeat Contact Rate", color=CHART_ACCENT)
        ax2.legend(loc="lower right", facecolor=CHART_PANEL, edgecolor=CHART_FG, fontsize=9)

    ax1.legend(loc="upper left", facecolor=CHART_PANEL, edgecolor=CHART_FG, fontsize=9)
    ax1.grid(True, axis="x", alpha=0.3)
    _save(fig_dir, "scripted_language_by_scenario.png")


def chart_kardashev_tier(
    system_result: Any,   # KardashevResult | None
    rep_summary:   pd.DataFrame,
    fig_dir:       Path,
    sii_gated:     Optional[float] = None,
) -> None:
    """
    Kardashev Trust Classification chart (Aulabaugh 2026, Section 7).

    Two panels:
      Left  — system-level tier badge with SII and Goodhart Gap
      Right — rep-level tier distribution (if Kardashev applied at rep level)
    """
    if system_result is None:
        return

    _apply_dark_style()

    TIER_COLORS = {
        "PLANETARY": CHART_WARN,    # Type I — red
        "STELLAR":   CHART_AMBER,   # Type II — amber
        "GALACTIC":  CHART_ACCENT,  # Type III — green
    }

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # ── Left: system-level badge ──────────────────────────────────────────────
    ax = axes[0]
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    tier_color = TIER_COLORS.get(system_result.kardashev_tier, CHART_FG)

    ax.add_patch(plt.Rectangle(
        (0.05, 0.30), 0.90, 0.55,
        facecolor=tier_color, alpha=0.12,
        linewidth=2, edgecolor=tier_color,
    ))
    ax.text(0.50, 0.78, system_result.kardashev_label,
            ha="center", va="center", fontsize=16, fontweight="bold", color=tier_color)

    sii_display = sii_gated if sii_gated is not None else 0.0
    ax.text(0.50, 0.63,
            f"SII = {sii_display:.1f}  |  Goodhart Gap = {system_result.goodhart_gap:.1%}",
            ha="center", va="center", fontsize=12, color=CHART_FG)
    ax.text(0.50, 0.50,
            f"Circuit breaker: {system_result.circuit_breaker}",
            ha="center", va="center", fontsize=11,
            color=CHART_WARN if system_result.circuit_breaker != "CLEAR" else CHART_ACCENT)

    reason_short = (
        system_result.reason[:110] + "…"
        if len(system_result.reason) > 110 else system_result.reason
    )
    ax.text(0.50, 0.22, reason_short,
            ha="center", va="center", fontsize=7.5, color="#aaaaaa",
            wrap=True, multialignment="center")

    ax.set_title(
        "System-Level Kardashev Trust Classification\n"
        "Aulabaugh (2026), Section 7",
        color=CHART_FG, fontsize=10,
    )

    # ── Right: rep-level tier distribution ───────────────────────────────────
    ax2 = axes[1]
    if not rep_summary.empty and "kardashev_type" in rep_summary.columns:
        counts     = rep_summary["kardashev_type"].value_counts().sort_index()
        labels_map = {
            1: "Type I\nProxy Mastery",
            2: "Type II\nResolution Mastery",
            3: "Type III\nSystemic Integrity",
        }
        colors_map = {1: CHART_WARN, 2: CHART_AMBER, 3: CHART_ACCENT}
        bars       = [counts.get(t, 0) for t in [1, 2, 3]]
        bar_colors = [colors_map[t] for t in [1, 2, 3]]

        x = np.arange(3)
        ax2.bar(x, bars, color=bar_colors, alpha=0.80, edgecolor="none", width=0.55)
        ax2.set_xticks(x)
        ax2.set_xticklabels([labels_map[t] for t in [1, 2, 3]], fontsize=9)
        ax2.set_ylabel("Rep Count")
        ax2.set_title("Rep-Level Kardashev Distribution", color=CHART_FG)
        ax2.grid(True, axis="y", alpha=0.3)
        for xi, v in zip(x, bars):
            if v > 0:
                ax2.text(xi, v + 0.25, str(v), ha="center", fontsize=10, color=CHART_FG)
    else:
        ax2.axis("off")
        ax2.text(
            0.5, 0.5,
            "Rep-level Kardashev\nnot available\n\n"
            "(apply_kardashev_classification\nrequires rep_summary with\n"
            "sii_score, proxy_kpi, true_crt,\nrepeat_rate, drift_score)",
            ha="center", va="center", color="#888888", fontsize=11,
        )

    _save(fig_dir, "kardashev_trust_classification.png")
