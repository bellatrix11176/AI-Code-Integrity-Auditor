from pathlib import Path

def find_backend_root() -> Path:
    # This file is in backend/src/paths.py, so parent.parent is backend/
    return Path(__file__).resolve().parent.parent

BACKEND_ROOT = find_backend_root()
PROJECT_ROOT = BACKEND_ROOT.parent

UPLOADS_DIR = BACKEND_ROOT / "data"   / "uploads"
REPORTS_DIR = BACKEND_ROOT / "output" / "reports"

def ensure_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)