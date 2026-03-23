from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass
class Finding:
    """
    A single integrity issue detected in a file.

    Core fields (used by reporter + charts):
      file, line, category, severity, message

    Extended fields (from donor system — used in detailed views):
      title      short label for the finding type
      evidence   the raw source line that triggered the finding
      suggestion actionable fix recommendation
    """
    file:       str
    line:       int        # 1-based; 0 = file-level
    category:   str
    severity:   str        # "low" | "medium" | "high"
    message:    str
    title:      str = ""
    evidence:   str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanSummary:
    total_findings: int
    files_scanned:  int
    by_severity:    dict[str, int]
    by_category:    dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
