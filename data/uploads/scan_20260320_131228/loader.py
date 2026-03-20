"""
novawireless.pipeline.loader
----------------------------
Data ingestion helpers and repo-root path resolution.

Expected data layout:
    <repo_root>/
    └── data/
        └── raw/
            ├── calls_sanitized_2025-01.csv
            ├── calls_sanitized_2025-02.csv
            └── ...

All CSV files must match the 54-column calls_sanitized schema
(see docs/schema/calls_sanitized_schema.md).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd


# ── Repo-root discovery ───────────────────────────────────────────────────────

def find_repo_root(start: Path) -> Path:
    """
    Walk upward from ``start`` until the novawireless-governance-pipeline repo
    root is found.

    A valid repo root is identified by the presence of ALL THREE of:
      - ``data/``        (monthly CSV inputs)
      - ``src/``         (Python package)
      - ``README.md``    (repo identity anchor)

    Requiring all three prevents accidental stops at unrelated directories
    that happen to contain a ``data/`` subdirectory (e.g. a stale ``{src``
    folder or any other leftover from prior repo states).

    Parameters
    ----------
    start : Path
        Starting directory. Pass ``Path.cwd()`` when invoking from the CLI.

    Returns
    -------
    Path
        The confirmed repo root directory.

    Raises
    ------
    FileNotFoundError
        If no qualifying directory is found within 50 levels.
    """
    cur = start.resolve()
    for _ in range(50):
        if (
            (cur / "data").is_dir()
            and (cur / "src").is_dir()
            and (cur / "README.md").is_file()
        ):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    raise FileNotFoundError(
        f"Could not locate novawireless-governance-pipeline repo root "
        f"starting from: {start}\n"
        "The repo root must contain data/, src/, and README.md.\n"
        "Run the pipeline from within the repo:\n"
        "  python src/run_pipeline.py"
    )


# ── Output directory setup ────────────────────────────────────────────────────

def ensure_output_dirs(repo_root: Path) -> Dict[str, Path]:
    """
    Create (if absent) and return the four output subdirectories.

    Output layout::

        <repo_root>/output/
        ├── data/     ← scored CSVs, summaries, trends
        ├── figures/  ← PNG charts
        └── reports/  ← JSON + TXT governance reports

    Parameters
    ----------
    repo_root : Path

    Returns
    -------
    dict[str, Path]
        Keys: ``"base"``, ``"data"``, ``"figures"``, ``"reports"``
    """
    base = repo_root / "output"
    dirs: Dict[str, Path] = {
        "base":    base,
        "data":    base / "data",
        "figures": base / "figures",
        "reports": base / "reports",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


# ── JSON serialisation helper ─────────────────────────────────────────────────

def save_json(path: Path, obj: dict) -> None:
    """
    Serialise ``obj`` to a JSON file at ``path``, creating parent dirs as needed.

    Uses ``default=str`` so datetime objects and Path objects serialise cleanly.

    Parameters
    ----------
    path : Path
    obj  : dict
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, default=str),
        encoding="utf-8",
    )


# ── Monthly file loader ───────────────────────────────────────────────────────

def load_monthly_files(data_dir: Path) -> pd.DataFrame:
    """
    Load all ``calls_sanitized_*.csv`` files from ``data_dir`` into a single
    DataFrame, adding a ``_source_file`` column for per-file traceability.

    Files are sorted alphabetically before loading, so that
    ``calls_sanitized_2025-01.csv`` is always month 1 regardless of filesystem
    ordering.

    Parameters
    ----------
    data_dir : Path
        Directory containing the monthly CSV files.

    Returns
    -------
    pd.DataFrame
        Combined DataFrame with all monthly records and a ``_source_file``
        column set to the originating filename.

    Raises
    ------
    FileNotFoundError
        If no matching files are found in ``data_dir``.
    """
    files = sorted(data_dir.glob("calls_sanitized_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"No calls_sanitized_*.csv files found in {data_dir}.\n"
            "Place monthly data files in data/raw/ and re-run."
        )

    frames = []
    for f in files:
        df = pd.read_csv(f, low_memory=False, encoding="utf-8-sig")
        df.columns = [c.strip() for c in df.columns]
        df["_source_file"] = f.name
        frames.append(df)
        print(f"  Loaded {f.name}: {len(df):,} rows")

    combined = pd.concat(frames, ignore_index=True)
    print(f"  Combined: {len(combined):,} rows from {len(files)} file(s)\n")
    return combined
