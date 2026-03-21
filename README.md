<p align="center">
  <img src="assets/AI_Code_Auditor.png" width="160" alt="AI Code Integrity Auditor Logo">
</p>

# AI Code Integrity Auditor

A local static analysis tool that detects integrity failures in AI-generated Python and JSON files.

This is **not a linter**. It does not check syntax or style. It is a governance layer designed to catch the specific failure patterns that AI code generators produce — code that looks correct but is logically unreliable, incomplete, or fabricated.

---

## What it detects

### Python files

| Category | What it catches |
|---|---|
| `structural_hallucination` | Names used but never defined or imported |
| `silent_failure_risk` | Bare `except:` blocks and `except … pass` (swallowed exceptions) |
| `placeholder_logic` | `pass` statements, `NotImplementedError`, TODO/FIXME/HACK comments, placeholder string literals |
| `terminal_state_failure` | Functions whose names imply a return value but have no `return` statement, or inconsistent return paths |
| `narrative_state_risk` | `print("success")` or log calls that claim completion without a matching write or state change; docstrings that claim to save/write but the function doesn't |
| `control_flow_drift` | Unreachable code after `return`, `raise`, `break`, or `continue` |
| `path_to_nowhere` | References to local file paths that were not part of the uploaded batch |

### JSON files

| Category | What it catches |
|---|---|
| `json_integrity_issue` | Invalid JSON, placeholder values (`todo`, `temp`, `your-api-key`, etc.), sample credentials or URLs |
| `schema_drift` | Duplicate keys, mixed camelCase/snake_case naming, high null density (≥ 35% of values are null) |

---

## Known behavior — self-referential findings

> **Scanning the tool's own source files will produce expected self-referential findings.**
>
> `scanner.py` contains the detection patterns it scans for — placeholder string lists, success message examples, TODO/FIXME markers used in comment detection — so it will always flag itself. This is **expected and correct behavior**, not a bug. A scanner that cannot detect its own patterns would not be detecting anyone else's either.
>
> All findings produced when scanning `scanner.py` against itself are low or medium severity and are documented as known self-referential results.

---

## Known limitation — Microsoft OneDrive

> ⚠️ **Do not run this tool from a Microsoft OneDrive folder.**
>
> OneDrive's background sync process holds file locks that conflict with the app's startup cleanup routine, causing `PermissionError` on launch. Clone or move the project to a local folder outside OneDrive before running.
>
> Example: `C:\Projects\AI-Code-Integrity-Auditor`

---

## Project structure

```
AI-Code-Integrity-Auditor/
├── app.py                  # Streamlit entry point
├── requirements.txt
├── README.md
├── LICENSE
├── assets/
│   └── AI_Code_Auditor.png
├── src/
│   ├── __init__.py
│   ├── scanner.py          # All detection logic
│   ├── reporter.py         # JSON + HTML report generation
│   ├── charts.py           # Matplotlib visualizations
│   └── paths.py            # Repo-root detection + shared path constants
├── data/
│   └── uploads/            # Cleared on every launch
└── output/
    └── reports/            # Cleared on every launch
```

All paths are resolved relative to the repo root. No absolute paths are used anywhere. The tool works wherever you clone it.

---

## Setup

```bash
# Windows
py -m venv venv
venv\Scripts\activate
py -m pip install -r requirements.txt
py -m streamlit run app.py

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens automatically at `http://localhost:8501`.

---

## System requirements

- **Python 3.10 or higher**
- **Windows, Mac, or Linux**
- **4GB RAM minimum** recommended
- **Must run from a local folder — not Microsoft OneDrive**

To check your Python version:
```bash
py --version
```

---

## How to use it

1. Open the app in your browser
2. Upload one or more `.py` or `.json` files
3. The scanner runs automatically on upload
4. Review findings in the table — filter by severity, category, or file
5. Review the three charts (by severity, by category, by file)
6. Download the JSON or HTML report

Uploaded files are scanned in memory and never saved to disk. Reports are written to `output/reports/` and cleared on next launch.

---

## Output

Each finding includes:

| Field | Description |
|---|---|
| File | Which file the issue was found in |
| Line | Line number (1-based; 0 means file-level) |
| Category | One of the nine detection categories |
| Severity | `high`, `medium`, or `low` |
| Message | Description of the issue |
| Title | Short label for the finding type |
| Evidence | The source line that triggered the finding |
| Suggestion | Recommended fix |

Reports are exported as structured JSON and a self-contained HTML file.

---

## Dependencies

| Package | Purpose |
|---|---|
| `streamlit >= 1.35.0` | Web UI |
| `matplotlib >= 3.7.0` | Charts |

All other analysis uses Python standard library only (`ast`, `tokenize`, `json`, `re`).

---

## Architecture

- **`src/scanner.py`** — all detection logic. Pure functions, no side effects. Accepts file objects directly — nothing is written to disk during scanning.
- **`src/reporter.py`** — writes JSON and HTML reports to `output/reports/`.
- **`src/charts.py`** — returns PNG bytes; does not write to disk.
- **`src/paths.py`** — single source of truth for `REPO_ROOT`, `UPLOADS_DIR`, `REPORTS_DIR`.
- **`app.py`** — thin UI layer only. Clears all previous outputs on every launch. All logic lives in `src/`.

---

## License

Copyright (c) 2026 PixelKraze, LLC. Author: Gina Aulabaugh.
Licensed under the [Apache License 2.0](LICENSE).
