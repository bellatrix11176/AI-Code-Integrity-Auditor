"""
src/charts.py

Phase 3: matplotlib chart generation from scan findings.

All charts are returned as PNG bytes so the caller (app.py or a test)
decides where to write or display them. Nothing is written to disk here.

Public API:
  chart_by_severity(findings) -> bytes
  chart_by_category(findings) -> bytes
  chart_by_file(findings)     -> bytes
"""

import io
from typing import List

import matplotlib
matplotlib.use("Agg")  # non-interactive backend; safe inside Streamlit
import matplotlib.pyplot as plt

from src.core.models import Finding


# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------

_BG      = "#0f1117"   # figure background
_PANEL   = "#1a1d27"   # axes background
_TEXT    = "#c9d1d9"   # tick labels, titles
_GRID    = "#2a2d3a"   # grid lines

_SEV_COLORS = {
    "high":   "#e74c3c",
    "medium": "#e67e22",
    "low":    "#3498db",
}

_CAT_PALETTE = [
    "#7c5cbf", "#3498db", "#2ecc71",
    "#e74c3c", "#e67e22", "#1abc9c",
]

# Human-readable labels for category slugs
_CAT_LABEL = {
    "structural_hallucination": "Structural\nHallucination",
    "silent_failure_risk":      "Silent\nFailure Risk",
    "placeholder_logic":        "Placeholder\nLogic",
    "terminal_state_failure":   "Terminal\nState Failure",
    "narrative_state_risk":     "Narrative\nState Risk",
    "json_integrity_issue":     "JSON\nIntegrity",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _style_axes(fig: plt.Figure, ax: plt.Axes) -> None:
    """Apply the dark theme to a figure/axes pair."""
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_PANEL)
    ax.tick_params(colors=_TEXT, labelsize=8)
    ax.xaxis.label.set_color(_TEXT)
    ax.yaxis.label.set_color(_TEXT)
    ax.title.set_color(_TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID)
    ax.yaxis.get_major_locator().set_params(integer=True)


def _to_png(fig: plt.Figure) -> bytes:
    """Render figure to PNG bytes and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=_BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _empty_chart(title: str) -> bytes:
    """Return a minimal chart with a 'no findings' message."""
    fig, ax = plt.subplots(figsize=(5, 3))
    _style_axes(fig, ax)
    ax.set_title(title, fontsize=11, pad=10)
    ax.text(0.5, 0.5, "No findings", transform=ax.transAxes,
            ha="center", va="center", color="#555", fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    return _to_png(fig)


# ---------------------------------------------------------------------------
# Public chart functions
# ---------------------------------------------------------------------------

def chart_by_severity(findings: List[Finding]) -> bytes:
    """
    Vertical bar chart: High / Medium / Low finding counts.
    Returns PNG bytes.
    """
    if not findings:
        return _empty_chart("Findings by Severity")

    counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        key = f.severity.lower()
        counts[key] = counts.get(key, 0) + 1

    labels = ["High", "Medium", "Low"]
    values = [counts["high"], counts["medium"], counts["low"]]
    colors = [_SEV_COLORS["high"], _SEV_COLORS["medium"], _SEV_COLORS["low"]]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    _style_axes(fig, ax)

    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=3)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=_GRID, linewidth=0.6, linestyle="--")
    ax.set_title("Findings by Severity", fontsize=11, pad=10)
    ax.set_ylabel("Count", fontsize=9)

    for bar, val in zip(bars, values):
        if val:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.08,
                str(val),
                ha="center", va="bottom",
                color=_TEXT, fontsize=10, fontweight="bold",
            )

    return _to_png(fig)


def chart_by_category(findings: List[Finding]) -> bytes:
    """
    Horizontal bar chart: count per rule category.
    Returns PNG bytes.
    """
    if not findings:
        return _empty_chart("Findings by Category")

    counts: dict = {}
    for f in findings:
        counts[f.category] = counts.get(f.category, 0) + 1

    # Sort ascending so the longest bar sits at the top
    items   = sorted(counts.items(), key=lambda x: x[1])
    slugs   = [k for k, _ in items]
    values  = [v for _, v in items]
    labels  = [_CAT_LABEL.get(s, s) for s in slugs]
    colors  = [_CAT_PALETTE[i % len(_CAT_PALETTE)] for i in range(len(slugs))]

    fig_h   = max(3.5, len(slugs) * 0.6 + 1.0)
    fig, ax = plt.subplots(figsize=(6, fig_h))
    _style_axes(fig, ax)

    bars = ax.barh(labels, values, color=colors, height=0.55, zorder=3)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=_GRID, linewidth=0.6, linestyle="--")
    ax.set_title("Findings by Category", fontsize=11, pad=10)
    ax.set_xlabel("Count", fontsize=9)
    ax.tick_params(axis="y", labelsize=7.5)
    ax.xaxis.get_major_locator().set_params(integer=True)

    for bar, val in zip(bars, values):
        if val:
            ax.text(
                bar.get_width() + 0.05,
                bar.get_y() + bar.get_height() / 2,
                str(val),
                va="center", color=_TEXT, fontsize=9, fontweight="bold",
            )

    return _to_png(fig)


def chart_by_file(findings: List[Finding]) -> bytes:
    """
    Horizontal bar chart: finding count per filename.
    Returns PNG bytes.
    """
    if not findings:
        return _empty_chart("Findings by File")

    counts: dict = {}
    for f in findings:
        counts[f.file] = counts.get(f.file, 0) + 1

    items   = sorted(counts.items(), key=lambda x: x[1])
    files   = [k for k, _ in items]
    values  = [v for _, v in items]

    # Truncate very long filenames for display
    labels  = [fn if len(fn) <= 28 else "…" + fn[-26:] for fn in files]

    fig_h   = max(3.5, len(files) * 0.6 + 1.0)
    fig, ax = plt.subplots(figsize=(6, fig_h))
    _style_axes(fig, ax)

    bars = ax.barh(labels, values, color="#7c5cbf", height=0.55, zorder=3)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=_GRID, linewidth=0.6, linestyle="--")
    ax.set_title("Findings by File", fontsize=11, pad=10)
    ax.set_xlabel("Count", fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    ax.xaxis.get_major_locator().set_params(integer=True)

    for bar, val in zip(bars, values):
        if val:
            ax.text(
                bar.get_width() + 0.05,
                bar.get_y() + bar.get_height() / 2,
                str(val),
                va="center", color=_TEXT, fontsize=9, fontweight="bold",
            )

    return _to_png(fig)
