<p align="center">
  <img src="assets/logo.svg" width="120" alt="AI Code Integrity Auditor Logo">
</p>

# AI Code Integrity Auditor (ACIA)

A specialized static analysis tool designed to detect integrity failures and "hallucinations" in AI-generated code (Python and JSON). It focuses on structural correctness, logic completeness, and narrative consistency rather than syntax or style.

This is **not a linter**. It is a governance layer designed to catch the specific failure patterns that AI code generators (like ChatGPT and Claude) produce — code that looks correct but is logically unreliable, incomplete, or fabricated.

---

## 🛡️ Core Detections

### Python Analysis
*   **Structural Hallucination:** Names used but never defined or imported.
*   **Silent Failure Risk:** Bare `except:` blocks and `except ... pass` (swallowed exceptions).
*   **Placeholder Logic:** `pass` statements, `NotImplementedError`, TODO/FIXME/HACK comments, and placeholder string literals.
*   **Control Flow Drift:** Unreachable code after `return`, `raise`, `break`, or `continue`.
*   **Narrative State Risk:** Logs or docstrings claiming completion without actual state changes (e.g., claiming to save a file without a matching write operation).

### JSON Analysis
*   **Integrity Issues:** Invalid JSON, placeholder values (`todo`, `temp`, `your-api-key`), and sample credentials.
*   **Schema Drift:** Duplicate keys, inconsistent naming conventions (camelCase vs snake_case), and high null density.

---

## 🏗️ Project Structure

The project is organized into a modular monorepo structure:

```text
acia/
├── backend/            # Python Backend (FastAPI & Streamlit)
│   ├── api/            # FastAPI Modern Web Backend
│   ├── src/            # Core Modular Logic
│   │   ├── core/       # Models and Constants
│   │   ├── scanner/    # Specialized Scanning Engines (Python, JSON)
│   │   ├── reporter.py # JSON + HTML Report Generation
│   │   └── charts.py   # Matplotlib Visualizations
│   ├── tests/          # Unit Tests (pytest)
│   ├── app.py          # Streamlit UI (Legacy/Local)
│   └── data/           # Uploads and generated reports
├── frontend/           # Next.js Modern Web UI
├── assets/             # Global visual assets
└── paper/              # Research documentation
```

---

## 🚀 Getting Started

### 1. Backend Setup
The backend requires **Python 3.13+**. We recommend using `uv` for dependency management.

```bash
cd backend

# Install dependencies and setup venv
uv sync

# Run the FastAPI Server (Modern API)
uv run uvicorn api.main:app --reload --port 8000

# OR Run the Streamlit UI (Local Dashboard)
uv run streamlit run app.py
```

### 2. Frontend Setup
The modern web UI is built with Next.js 16 and Tailwind CSS.

```bash
cd frontend

# Install dependencies
bun install

# Run in development mode
bun dev
```
The dashboard will be available at `http://localhost:3000`.

---

## 🎨 Design & Aesthetics
The application features a modern "Cyber-Peach" aesthetic:
*   **Color Palette:** `#264259` (Deep Blue), `#355c7d` (Muted Indigo), `#f58e65` (Primary Coral), `#f8b195` (Accent Peach), `#fbd4c5` (Text Shell).
*   **Interface:** Glassmorphism cards, steep border radii for a sharp professional look, and a responsive grid layout.

---

## 🧪 Testing
The backend includes a suite of unit tests for the scanning logic.
```bash
cd backend
uv run pytest tests/
```

---

## 📄 License
Copyright (c) 2026 PixelKraze, LLC. Author: Gina Aulabaugh.
Licensed under the [Apache License 2.0](LICENSE).
