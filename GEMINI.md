# AI Code Integrity Auditor (ACIA)

A specialized static analysis tool designed to detect integrity failures and "hallucinations" in AI-generated code (Python and JSON). It focuses on structural correctness, logic completeness, and narrative consistency rather than syntax or style.

## Project Overview

ACIA provides a governance layer for AI-assisted development. It identifies patterns typical of LLMs, such as:
- **Structural Hallucination:** Using undefined variables or imports.
- **Silent Failure Risk:** Bare `except:` blocks or swallowed exceptions.
- **Placeholder Logic:** Unimplemented code (`pass`, `TODO`, `NotImplementedError`).
- **Control Flow Drift:** Unreachable code or inconsistent return paths.
- **Narrative State Risk:** Comments or logs claiming completion without actual state changes.

### Tech Stack
- **Backend Core:** Python 3.13+ (AST analysis, Tokenization).
- **Backend Framework:** FastAPI & Streamlit.
- **Web Frontend:** Next.js with TypeScript and Tailwind CSS.
- **Visualizations:** Matplotlib & Recharts.

## Project Structure

```text
acia/
├── backend/            # Python Backend
│   ├── app.py          # Streamlit entry point (Legacy/Local UI)
│   ├── api/            # FastAPI entry point (Modern Web Backend)
│   ├── src/            # Core logic (Scanner, Reporter, Charts)
│   ├── tests/          # Unit tests
│   ├── data/uploads/   # Temporary storage for scanned files
│   └── output/reports/ # Generated analysis reports
├── frontend/           # Next.js Frontend
├── assets/             # Global visual assets
├── paper/              # Research documentation
└── README.md           # Root documentation
```

## Building and Running

### 1. Backend & Local UI (Streamlit)
The backend requires **Python 3.13+**. This project uses `uv` for dependency management.

```bash
cd backend

# Setup environment (uv)
uv sync

# Run Local Streamlit UI
uv run streamlit run app.py

# Run FastAPI Server
uv run uvicorn api.main:app --reload --port 8000
```

### 2. Web Frontend (Next.js)
The frontend is built with Next.js 16.

```bash
cd frontend
bun install
bun dev
```

## Development Conventions

- **Modular Logic:** Core detection logic belongs in `backend/src/scanner/`.
- **Path Handling:** Always use `backend/src/paths.py` for resolving directories.
- **Frontend Styles:** The web frontend uses a dark "cyber" aesthetic with custom gradients and Tailwind CSS.
- **API Wrapper:** When adding new scanner features, ensure the `ScanEngine` in `backend/src/scanner/engine.py` handles them.
