<p align="center">
  <img src="assets/AI_Code_Auditor.png" width="160" alt="AI Code Integrity Auditor Logo">
</p>
# AI Code Integrity Auditor

A local tool to detect integrity issues in AI-generated Python and JSON files.

---

## Current Status — Phase 1 (Skeleton Only)

This is the repo skeleton. No scanning logic exists yet.

What is present:
- Repo-root architecture with relative paths throughout
- Directory layout enforced on launch (`data/uploads/`, `output/reports/`)
- Data types for scan findings (`src/scanner.py`)
- Stub `scan()` function that raises `NotImplementedError`
- Minimal Streamlit app that launches and confirms the structure

What is NOT present yet:
- Python file analysis
- JSON file analysis
- Any detection logic
- Report generation
- Charts or visualizations
- File upload UI

---

## Directory Layout

```
ai-code-integrity-auditor/
├── app.py                  # Streamlit entry point
├── requirements.txt
├── README.md
├── src/
│   └── scanner.py          # Finding types + scan stub
├── data/
│   └── uploads/            # Uploaded files go here (created on launch)
└── output/
    └── reports/            # Generated reports go here (created on launch)
```

---

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Architecture Note

All paths are resolved relative to the repo root. No absolute paths are used anywhere.
The repo root is detected at runtime by walking upward from `app.py` until a known
marker file is found.
