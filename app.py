"""
app.py
AI Code Integrity Auditor — Streamlit UI.
"""

import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if any((current / m).exists() for m in ("requirements.txt", ".git")):
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path.cwd()

REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import streamlit as st

from src.paths import UPLOADS_DIR, REPORTS_DIR, ensure_dirs
from src.scanner import Finding, scan
from src.reporter import write_json_report, write_html_report
from src.charts import chart_by_severity, chart_by_category, chart_by_file

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CAT_LABEL = {
    "structural_hallucination": "Structural Hallucination",
    "silent_failure_risk":      "Silent Failure Risk",
    "placeholder_logic":        "Placeholder Logic",
    "terminal_state_failure":   "Terminal State Failure",
    "narrative_state_risk":     "Narrative State Risk",
    "control_flow_drift":       "Control Flow Drift",
    "path_to_nowhere":          "Path to Nowhere",
    "schema_drift":             "Schema Drift",
    "json_integrity_issue":     "JSON Integrity Issue",
}

_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Code Integrity Auditor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
  /* ── Base ── */
  html, body, [data-testid="stAppViewContainer"] {
    background: #080c14;
  }
  [data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #080c14 0%, #0d1220 50%, #080c14 100%);
  }
  [data-testid="stHeader"] { background: transparent; }
  [data-testid="stSidebar"] { background: #0d1220; }

  /* ── Global text ── */
  html, body, p, span, div, label {
    color: #c9d1d9;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
  }

  /* ── Center wrapper ── */
  .block-container {
    max-width: 960px !important;
    padding: 2rem 2rem 4rem !important;
    margin: 0 auto !important;
  }

  /* ── Hero header ── */
  .hero {
    text-align: center;
    padding: 2.5rem 0 1.5rem;
  }
  .hero-logo {
    width: 88px;
    height: 88px;
    border-radius: 18px;
    margin: 0 auto 1.2rem;
    display: block;
    box-shadow: 0 0 32px rgba(56, 182, 255, 0.35);
  }
  .hero-logo-emoji {
    font-size: 5rem;
    display: block;
    text-align: center;
    margin-bottom: 0.75rem;
    filter: drop-shadow(0 0 18px rgba(56,182,255,0.5));
  }
  .hero h1 {
    font-size: 2.6rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, #ffffff 30%, #38b6ff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.5rem;
  }
  .hero p {
    font-size: 1rem;
    color: #6b7a99;
    margin: 0;
    letter-spacing: 0.01em;
  }

  /* ── Upload card ── */
  .upload-card {
    background: linear-gradient(135deg, #111827 0%, #0f1623 100%);
    border: 1px solid #1e2d45;
    border-radius: 16px;
    padding: 2rem 2rem 1.5rem;
    margin: 1.5rem 0;
    box-shadow:
      0 0 0 1px rgba(56, 182, 255, 0.06),
      0 8px 32px rgba(0, 0, 0, 0.4),
      0 0 60px rgba(56, 182, 255, 0.04);
  }
  .upload-card-title {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #38b6ff;
    margin-bottom: 0.4rem;
  }
  .upload-card-desc {
    font-size: 0.92rem;
    color: #6b7a99;
    margin-bottom: 1.2rem;
  }

  /* ── Streamlit uploader override ── */
  [data-testid="stFileUploaderDropzone"] {
    background: #0a0f1a !important;
    border: 2px dashed #1e3a5f !important;
    border-radius: 12px !important;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  [data-testid="stFileUploaderDropzone"]:hover {
    border-color: #38b6ff !important;
    box-shadow: 0 0 24px rgba(56, 182, 255, 0.12) !important;
  }
  [data-testid="stFileUploaderDropzoneInstructions"] span {
    color: #6b7a99 !important;
    font-size: 0.9rem !important;
  }

  /* ── Section labels ── */
  .section-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #38b6ff;
    margin: 2rem 0 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #1a2035;
  }

  /* ── Metric cards ── */
  [data-testid="metric-container"] {
    background: #111827;
    border: 1px solid #1a2035;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    transition: border-color 0.2s;
  }
  [data-testid="metric-container"]:hover {
    border-color: #2a3a55;
  }
  [data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    color: #6b7a99 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  [data-testid="stMetricValue"] {
    font-size: 1.9rem !important;
    font-weight: 800 !important;
    color: #ffffff !important;
  }

  /* ── Dataframe ── */
  [data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #1a2035;
  }

  /* ── Download buttons ── */
  .stDownloadButton > button {
    background: #111827 !important;
    border: 1px solid #1e3a5f !important;
    color: #c9d1d9 !important;
    border-radius: 10px !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.2s !important;
  }
  .stDownloadButton > button:hover {
    border-color: #38b6ff !important;
    color: #fff !important;
    box-shadow: 0 0 16px rgba(56, 182, 255, 0.2) !important;
  }

  /* ── Selectbox ── */
  [data-testid="stSelectbox"] > div > div {
    background: #111827 !important;
    border: 1px solid #1a2035 !important;
    border-radius: 8px !important;
    color: #c9d1d9 !important;
  }

  /* ── Divider ── */
  hr {
    border: none;
    border-top: 1px solid #1a2035 !important;
    margin: 1.5rem 0 !important;
  }

  /* ── Success / error ── */
  [data-testid="stAlertContainer"] {
    border-radius: 10px !important;
  }

  /* ── Caption / small text ── */
  [data-testid="stCaptionContainer"] p {
    color: #3d4f6e !important;
    font-size: 0.78rem !important;
  }

  /* ── Expander ── */
  [data-testid="stExpander"] {
    background: #111827 !important;
    border: 1px solid #1a2035 !important;
    border-radius: 10px !important;
  }

  /* ── Hide Streamlit branding ── */
  #MainMenu { visibility: hidden; }
  footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Ensure output dirs
# ---------------------------------------------------------------------------

ensure_dirs()

# ---------------------------------------------------------------------------
# Logo path
# ---------------------------------------------------------------------------

LOGO_PATH = REPO_ROOT / "assets" / "AI Code Auditor.png"

# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------

st.markdown("<div style='padding-top: 2.5rem'></div>", unsafe_allow_html=True)

_, col_logo, _ = st.columns([2, 1, 2])
with col_logo:
    logo = REPO_ROOT / "assets" / "AI_Code_Auditor.png"
    if logo.exists():
        st.image(str(logo), width=200)

st.markdown("<div style='padding-top: 0.75rem'></div>", unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; padding-bottom: 0.4rem;">
  <h1 style="
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, #ffffff 30%, #38b6ff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.4rem;
    line-height: 1.15;
  ">AI Code Integrity Auditor</h1>
  <p style="
    font-size: 0.98rem;
    color: #6b7a99;
    margin: 0;
    letter-spacing: 0.01em;
  ">Detect hallucinations, drift, and silent failures in AI-generated code</p>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='padding-bottom: 1.5rem'></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Upload card
# ---------------------------------------------------------------------------

st.markdown("""
<div class="upload-card">
  <div class="upload-card-title">Scan files</div>
  <div class="upload-card-desc">
    Upload <code>.py</code> or <code>.json</code> files to check for structural hallucinations,
    silent failures, placeholder logic, and integrity issues.
  </div>
""", unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    label="Drag and drop files here, or click to browse",
    type=["py", "json"],
    accept_multiple_files=True,
    help="Files are saved to data/uploads/scan_<timestamp>/ and never modified.",
    label_visibility="visible",
)

st.markdown("</div>", unsafe_allow_html=True)

if not uploaded_files:
    st.markdown("""
    <div style="text-align:center; padding: 2rem 0 1rem; color: #3d4f6e; font-size: 0.85rem;">
      Supported detections &nbsp;·&nbsp;
      <span style="color:#38b6ff">Structural Hallucination</span> &nbsp;·&nbsp;
      <span style="color:#38b6ff">Silent Failure Risk</span> &nbsp;·&nbsp;
      <span style="color:#38b6ff">Placeholder Logic</span> &nbsp;·&nbsp;
      <span style="color:#38b6ff">Control Flow Drift</span> &nbsp;·&nbsp;
      <span style="color:#38b6ff">Schema Drift</span>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# Run scan
# ---------------------------------------------------------------------------

upload_key = tuple(sorted((f.name, f.size) for f in uploaded_files))

if st.session_state.get("upload_key") != upload_key:
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id      = f"scan_{timestamp}"
    session_dir = UPLOADS_DIR / run_id
    session_dir.mkdir(parents=True, exist_ok=True)

    all_findings: list[Finding] = []
    scan_errors:  list[str]     = []

    with st.spinner("Scanning files for integrity issues…"):
        for uf in uploaded_files:
            dest = session_dir / uf.name
            dest.write_bytes(uf.read())
            try:
                found = scan(dest)
                all_findings.extend(found)
            except Exception as exc:
                scan_errors.append(f"{uf.name}: {exc}")

    all_findings.sort(
        key=lambda f: (_SEV_ORDER.get(f.severity.lower(), 9), f.file, f.line)
    )

    json_path = write_json_report(all_findings, run_id)
    html_path = write_html_report(all_findings, run_id)

    st.session_state.update({
        "upload_key":  upload_key,
        "run_id":      run_id,
        "findings":    all_findings,
        "scan_errors": scan_errors,
        "json_path":   json_path,
        "html_path":   html_path,
        "files":       [f.name for f in uploaded_files],
    })

findings:      list[Finding] = st.session_state["findings"]
scan_errors:   list[str]     = st.session_state["scan_errors"]
json_path:     Path          = st.session_state["json_path"]
html_path:     Path          = st.session_state["html_path"]
run_id:        str           = st.session_state["run_id"]
files_scanned: list[str]     = st.session_state["files"]

# ---------------------------------------------------------------------------
# Scan errors
# ---------------------------------------------------------------------------

for err in scan_errors:
    st.error(f"Scan error — {err}")

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">Scan summary</div>', unsafe_allow_html=True)

high   = sum(1 for f in findings if f.severity.lower() == "high")
medium = sum(1 for f in findings if f.severity.lower() == "medium")
low    = sum(1 for f in findings if f.severity.lower() == "low")
total  = len(findings)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Files scanned", len(files_scanned))
c2.metric("Total findings", total)
c3.metric("🔴 High",   high)
c4.metric("🟡 Medium", medium)
c5.metric("🔵 Low",    low)

if total == 0:
    st.success("✅ No integrity issues detected in the uploaded files.")

# ---------------------------------------------------------------------------
# Findings table
# ---------------------------------------------------------------------------

if findings:
    st.markdown('<div class="section-label">Findings</div>', unsafe_allow_html=True)

    col_sev, col_cat, col_file = st.columns(3)
    with col_sev:
        sev_choice = st.selectbox("Severity", ["All", "high", "medium", "low"])
    with col_cat:
        cat_options = ["All"] + sorted({f.category for f in findings})
        cat_choice  = st.selectbox("Category", cat_options)
    with col_file:
        file_options = ["All"] + sorted({f.file for f in findings})
        file_choice  = st.selectbox("File", file_options)

    visible = findings
    if sev_choice  != "All":
        visible = [f for f in visible if f.severity.lower() == sev_choice]
    if cat_choice  != "All":
        visible = [f for f in visible if f.category == cat_choice]
    if file_choice != "All":
        visible = [f for f in visible if f.file == file_choice]

    rows = [
        {
            "File":       f.file,
            "Line":       f.line if f.line else "—",
            "Category":   _CAT_LABEL.get(f.category, f.category),
            "Severity":   f.severity.upper(),
            "Message":    f.message,
        }
        for f in visible
    ]

    st.caption(f"Showing {len(visible)} of {total} findings")

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "File":     st.column_config.TextColumn("File",     width="small"),
            "Line":     st.column_config.TextColumn("Line",     width="small"),
            "Category": st.column_config.TextColumn("Category", width="medium"),
            "Severity": st.column_config.TextColumn("Severity", width="small"),
            "Message":  st.column_config.TextColumn("Message",  width="large"),
        },
    )

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">Visualizations</div>', unsafe_allow_html=True)

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.image(chart_by_severity(findings), use_column_width=True)
with col_b:
    st.image(chart_by_category(findings), use_column_width=True)
with col_c:
    st.image(chart_by_file(findings), use_column_width=True)

# ---------------------------------------------------------------------------
# Download reports
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">Export reports</div>', unsafe_allow_html=True)

dl1, dl2, _ = st.columns([1, 1, 3])
with dl1:
    st.download_button(
        label="⬇ JSON report",
        data=json_path.read_bytes(),
        file_name=json_path.name,
        mime="application/json",
    )
with dl2:
    st.download_button(
        label="⬇ HTML report",
        data=html_path.read_bytes(),
        file_name=html_path.name,
        mime="text/html",
    )

st.markdown("<br>", unsafe_allow_html=True)
st.caption(
    f"Run ID: `{run_id}` · "
    f"Reports → `output/reports/` · "
    f"Uploads → `data/uploads/{run_id}/`"
)
