"""
novawireless.pipeline.alerts
------------------------------
Governance threshold alert evaluation (Section 6 — Governance Architecture).

Produces WATCH and VETO alerts for:
  - scenario trust scores and resolution gaps
  - bandaid credit rates
  - rep-level trust scores and resolution gaps
  - month-over-month trust velocity

Circuit breaker semantics (paper Section 6):
    VETO  — halt AI optimization; re-audit measurement environment before
            any further model retraining.
    WATCH — drift detected; human review required before the next
            optimization cycle.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from .integrity import ThresholdConfig


# ── Single alert check ────────────────────────────────────────────────────────

def _check_threshold(
    alerts:    List[Dict],
    level:     str,
    etype:     str,
    entity:    Any,
    signal:    str,
    val:       float,
    th:        float,
    direction: str,
) -> None:
    """
    Append an alert dict to ``alerts`` if the threshold is breached.

    Parameters
    ----------
    direction : str — ``"below"`` (alert when val < th) or ``"above"``
    """
    triggered = (val < th) if direction == "below" else (val > th)
    if not triggered:
        return

    fmt    = f"{val:.1f}"  if signal == "trust_score" else f"{val:.1%}"
    th_fmt = f"{th}"       if signal == "trust_score" else f"{th:.0%}"
    alerts.append({
        "level":       level,
        "entity_type": etype,
        "entity":      entity,
        "signal":      signal,
        "value":       round(val, 4),
        "threshold":   th,
        "message": (
            f"{etype.title()} '{entity}' {signal} {fmt} "
            f"{'below' if direction == 'below' else 'above'} "
            f"{level} threshold {th_fmt}"
        ),
    })


# ── Alert orchestrator ────────────────────────────────────────────────────────

def run_threshold_alerts(
    scenario_summary: pd.DataFrame,
    rep_summary:      pd.DataFrame,
    monthly_trends:   pd.DataFrame,
    thresholds:       ThresholdConfig,
) -> Dict:
    """
    Evaluate all governance thresholds and return a deduped alert summary.

    Deduplication rule: for any (entity_type, entity, signal) triple,
    only the highest-severity alert is kept (VETO > WATCH).

    Parameters
    ----------
    scenario_summary : output of summarize_by_scenario()
    rep_summary      : output of summarize_by_rep()
    monthly_trends   : output of compute_monthly_trends()
    thresholds       : ThresholdConfig

    Returns
    -------
    dict with keys: timestamp, total_alerts, veto_count, watch_count,
                    thresholds_used, alerts
    """
    alerts: List[Dict] = []

    # ── Scenario alerts ───────────────────────────────────────────────────────
    if not scenario_summary.empty:
        for _, r in scenario_summary.iterrows():
            s = r["scenario"]
            t = r.get("trust_score_avg", 100)
            g = r.get("resolution_gap",  0)
            b = r.get("bandaid_rate",    0)

            _check_threshold(alerts, "VETO",  "scenario", s, "trust_score",    t, thresholds.trust_score_veto,    "below")
            _check_threshold(alerts, "WATCH", "scenario", s, "trust_score",    t, thresholds.trust_score_watch,   "below")
            _check_threshold(alerts, "VETO",  "scenario", s, "resolution_gap", g, thresholds.resolution_gap_veto, "above")
            _check_threshold(alerts, "WATCH", "scenario", s, "resolution_gap", g, thresholds.resolution_gap_watch,"above")
            _check_threshold(alerts, "VETO",  "scenario", s, "bandaid_rate",   b, thresholds.bandaid_rate_veto,   "above")
            _check_threshold(alerts, "WATCH", "scenario", s, "bandaid_rate",   b, thresholds.bandaid_rate_watch,  "above")

    # ── Rep alerts ────────────────────────────────────────────────────────────
    if not rep_summary.empty:
        for _, r in rep_summary.iterrows():
            rid = r["rep_id"]
            t   = r.get("trust_score_avg", 100)
            g   = r.get("resolution_gap",  0)

            _check_threshold(alerts, "VETO",  "rep", rid, "trust_score",    t, thresholds.rep_trust_veto,  "below")
            _check_threshold(alerts, "WATCH", "rep", rid, "trust_score",    t, thresholds.rep_trust_watch, "below")
            _check_threshold(alerts, "VETO",  "rep", rid, "resolution_gap", g, thresholds.rep_gap_veto,   "above")
            _check_threshold(alerts, "WATCH", "rep", rid, "resolution_gap", g, thresholds.rep_gap_watch,  "above")

    # ── Monthly drift velocity alerts ─────────────────────────────────────────
    if not monthly_trends.empty and "trust_velocity" in monthly_trends.columns:
        for _, r in monthly_trends.iterrows():
            vel = r.get("trust_velocity", 0)
            if pd.notna(vel) and vel < -thresholds.drift_velocity_watch:
                alerts.append({
                    "level":       "WATCH",
                    "entity_type": "month",
                    "entity":      str(r["_month"]),
                    "signal":      "trust_velocity",
                    "value":       round(vel, 3),
                    "threshold":   -thresholds.drift_velocity_watch,
                    "message": (
                        f"Month {r['_month']}: trust dropped {abs(vel):.2f} pts "
                        f"(>{thresholds.drift_velocity_watch}/month)"
                    ),
                })

    # ── Deduplication: keep highest severity per (entity_type, entity, signal) ─
    seen: Dict = {}
    for a in alerts:
        key = (a["entity_type"], a["entity"], a["signal"])
        if key not in seen or (
            a["level"] == "VETO" and seen[key]["level"] == "WATCH"
        ):
            seen[key] = a

    deduped = sorted(
        seen.values(),
        key=lambda a: (0 if a["level"] == "VETO" else 1, a["entity_type"], str(a["entity"])),
    )

    return {
        "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_alerts":    len(deduped),
        "veto_count":      sum(1 for a in deduped if a["level"] == "VETO"),
        "watch_count":     sum(1 for a in deduped if a["level"] == "WATCH"),
        "thresholds_used": asdict(thresholds),
        "alerts":          deduped,
    }


# ── Plain-text alert report ───────────────────────────────────────────────────

def write_threshold_alerts_txt(
    alert_summary: Dict,
    outpath:       Path,
) -> None:
    """Write a human-readable governance alert report to ``outpath``."""
    th = alert_summary["thresholds_used"]
    lines = [
        "GOVERNANCE THRESHOLD ALERTS",
        "=" * 60,
        f"Generated: {alert_summary['timestamp']}",
        f"Total alerts: {alert_summary['total_alerts']}",
        f"  VETO:  {alert_summary['veto_count']}",
        f"  WATCH: {alert_summary['watch_count']}",
        "",
    ]

    if alert_summary["veto_count"]:
        lines.append("─── VETO ALERTS (optimization halted) ───")
        for a in alert_summary["alerts"]:
            if a["level"] == "VETO":
                lines.append(f"  [{a['entity_type'].upper()}] {a['message']}")
        lines.append("")

    if alert_summary["watch_count"]:
        lines.append("─── WATCH ALERTS (human review required) ───")
        for a in alert_summary["alerts"]:
            if a["level"] == "WATCH":
                lines.append(f"  [{a['entity_type'].upper()}] {a['message']}")
        lines.append("")

    if alert_summary["total_alerts"] == 0:
        lines.append(
            "No threshold alerts triggered. "
            "All governance signals within bounds.\n"
        )

    lines += [
        "THRESHOLD CONFIGURATION",
        f"  Scenario trust    VETO/WATCH: < {th['trust_score_veto']} / < {th['trust_score_watch']}",
        f"  Scenario gap      VETO/WATCH: > {th['resolution_gap_veto']:.0%} / > {th['resolution_gap_watch']:.0%}",
        f"  Bandaid rate      VETO/WATCH: > {th['bandaid_rate_veto']:.0%} / > {th['bandaid_rate_watch']:.0%}",
        f"  Rep trust         VETO/WATCH: < {th['rep_trust_veto']} / < {th['rep_trust_watch']}",
        f"  Rep gap           VETO/WATCH: > {th['rep_gap_veto']:.0%} / > {th['rep_gap_watch']:.0%}",
        f"  Drift velocity    WATCH:      > {th['drift_velocity_watch']} pts/month",
    ]

    outpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
