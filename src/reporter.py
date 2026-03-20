"""
src/reporter.py

Phase 3: export scan results to JSON and HTML files.

Both writers resolve output paths through src/paths.py — no absolute
paths are constructed here.

Public API:
  write_json_report(findings, run_id) -> Path
  write_html_report(findings, run_id) -> Path
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from src.paths import REPORTS_DIR
from src.scanner import Finding


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _severity_order(s: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(s.lower(), 9)


def _sorted(findings: List[Finding]) -> List[Finding]:
    """Return findings sorted by severity then file then line."""
    return sorted(findings, key=lambda f: (_severity_order(f.severity), f.file, f.line))


def _counts(findings: List[Finding]) -> dict:
    severity = {"high": 0, "medium": 0, "low": 0}
    category: dict = {}
    by_file:  dict = {}

    for f in findings:
        sev = f.severity.lower()
        severity[sev] = severity.get(sev, 0) + 1
        category[f.category] = category.get(f.category, 0) + 1
        by_file[f.file]      = by_file.get(f.file, 0) + 1

    return {"severity": severity, "category": category, "file": by_file}


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def write_json_report(findings: List[Finding], run_id: str) -> Path:
    """
    Serialize findings to a JSON file in output/reports/.

    Args:
        findings: list of Finding objects from the scanner.
        run_id:   short identifier for this run (e.g. a timestamp string).

    Returns:
        Path to the written file, relative anchor is REPO_ROOT.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"report_{run_id}.json"

    counts = _counts(findings)
    payload = {
        "run_id":       run_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total":        len(findings),
        "by_severity":  counts["severity"],
        "by_category":  counts["category"],
        "by_file":      counts["file"],
        "findings": [
            {
                "file":     f.file,
                "line":     f.line,
                "category": f.category,
                "severity": f.severity,
                "message":  f.message,
            }
            for f in _sorted(findings)
        ],
    }

    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

# Severity colours used in the HTML table badges
_SEV_COLOR = {
    "high":   "#e74c3c",
    "medium": "#e67e22",
    "low":    "#3498db",
}

# Display label per category slug
_CAT_LABEL = {
    "structural_hallucination": "Structural Hallucination",
    "silent_failure_risk":      "Silent Failure Risk",
    "placeholder_logic":        "Placeholder Logic",
    "terminal_state_failure":   "Terminal State Failure",
    "narrative_state_risk":     "Narrative State Risk",
    "json_integrity_issue":     "JSON Integrity Issue",
}


def _badge(severity: str) -> str:
    color = _SEV_COLOR.get(severity.lower(), "#888")
    label = severity.upper()
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.75rem;font-weight:600">{label}</span>'
    )


def _esc(text: str) -> str:
    """Minimal HTML escaping for user-supplied strings."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_html_report(findings: List[Finding], run_id: str) -> Path:
    """
    Write a self-contained HTML summary to output/reports/.

    Args:
        findings: list of Finding objects from the scanner.
        run_id:   short identifier for this run.

    Returns:
        Path to the written file.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"report_{run_id}.html"

    counts    = _counts(findings)
    sorted_f  = _sorted(findings)
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    high   = counts["severity"].get("high",   0)
    medium = counts["severity"].get("medium", 0)
    low    = counts["severity"].get("low",    0)
    total  = len(findings)

    # Build findings table rows
    rows = ""
    for f in sorted_f:
        cat_label = _CAT_LABEL.get(f.category, f.category)
        rows += (
            f"<tr>"
            f"<td><code>{_esc(f.file)}</code></td>"
            f"<td style='text-align:center'>{f.line or '—'}</td>"
            f"<td>{_esc(cat_label)}</td>"
            f"<td>{_badge(f.severity)}</td>"
            f"<td>{_esc(f.message)}</td>"
            f"</tr>\n"
        )

    if not rows:
        rows = (
            "<tr><td colspan='5' style='text-align:center;color:#6a9153'>"
            "✓ No findings — no integrity issues detected."
            "</td></tr>"
        )

    # Summary cards
    def card(label: str, value: int, color: str) -> str:
        return (
            f"<div class='card'>"
            f"<div class='card-label'>{label}</div>"
            f"<div class='card-value' style='color:{color}'>{value}</div>"
            f"</div>"
        )

    cards = (
        card("Total", total, "#fff")
        + card("High",   high,   _SEV_COLOR["high"])
        + card("Medium", medium, _SEV_COLOR["medium"])
        + card("Low",    low,    _SEV_COLOR["low"])
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Integrity Report {run_id}</title>
<style>
  body {{
    margin: 0; padding: 2rem;
    font-family: system-ui, sans-serif;
    background: #0f1117; color: #c9d1d9;
    font-size: 0.9rem;
  }}
  h1 {{ color: #fff; margin: 0 0 0.25rem; font-size: 1.4rem; }}
  .meta {{ color: #555; margin-bottom: 1.5rem; font-size: 0.8rem; }}
  .cards {{ display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }}
  .card {{
    background: #1a1d27; border: 1px solid #2a2d3a;
    border-radius: 8px; padding: 1rem 1.5rem; min-width: 100px;
  }}
  .card-label {{ font-size: 0.7rem; color: #666; text-transform: uppercase;
                 letter-spacing: 0.08em; margin-bottom: 0.25rem; }}
  .card-value {{ font-size: 1.8rem; font-weight: 700; }}
  table {{
    width: 100%; border-collapse: collapse;
    background: #1a1d27; border-radius: 8px; overflow: hidden;
  }}
  th {{
    text-align: left; padding: 0.6rem 0.75rem;
    background: #13151e; color: #555;
    font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
    border-bottom: 1px solid #2a2d3a;
  }}
  td {{
    padding: 0.55rem 0.75rem;
    border-bottom: 1px solid #1e2130;
    vertical-align: top;
  }}
  tr:last-child td {{ border-bottom: none; }}
  code {{
    background: #0f1117; padding: 0.1em 0.35em;
    border-radius: 3px; font-size: 0.8rem; color: #79b8ff;
  }}
  .footer {{ margin-top: 2rem; color: #333; font-size: 0.75rem; }}
</style>
</head>
<body>

<h1>🔍 AI Code Integrity Auditor</h1>
<div class="meta">Run <code>{run_id}</code> · Generated {generated}</div>

<div class="cards">{cards}</div>

<table>
  <thead>
    <tr>
      <th>File</th>
      <th>Line</th>
      <th>Category</th>
      <th>Severity</th>
      <th>Message</th>
    </tr>
  </thead>
  <tbody>
{rows}
  </tbody>
</table>

<div class="footer">
  AI Code Integrity Auditor — Phase 3 report · output/reports/{out.name}
</div>

</body>
</html>
"""

    out.write_text(html, encoding="utf-8")
    return out
