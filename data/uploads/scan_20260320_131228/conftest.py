"""
conftest.py — pytest configuration for the NovaWireless governance pipeline.

Adds src/ to sys.path so tests can import novawireless.* without installation.
"""

import sys
from pathlib import Path

# Add src/ to path so `novawireless` is importable from tests/
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
