from pathlib import Path

def find_repo_root() -> Path:
    markers = ("app.py", "requirements.txt", ".git")
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if any((current / m).exists() for m in markers):
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path.cwd()

REPO_ROOT   = find_repo_root()
UPLOADS_DIR = REPO_ROOT / "data"   / "uploads"
REPORTS_DIR = REPO_ROOT / "output" / "reports"

def ensure_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)