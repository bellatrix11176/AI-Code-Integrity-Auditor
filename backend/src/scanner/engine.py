from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, List

from src.core.models import Finding, ScanSummary
from src.scanner.python import scan_python
from src.scanner.json import scan_json

def scan(file_path: Path, uploaded_names: set[str] | None = None) -> List[Finding]:
    """
    Scan a single file and return all findings.
    """
    suffix = file_path.suffix.lower()
    uploaded_names = uploaded_names or {file_path.name}

    if suffix == ".py":
        source = file_path.read_text(encoding="utf-8", errors="replace")
        return scan_python(source, file_path.name, uploaded_names)

    if suffix == ".json":
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        return scan_json(raw, file_path.name)

    raise ValueError(
        f"Unsupported file type: '{suffix}'. Only .py and .json are supported."
    )


class ScanEngine:
    """
    Entry point for scanning multiple files.
    """

    supported_suffixes = {".py", ".json"}

    def scan_uploaded_files(self, files: Iterable[Any]) -> dict[str, Any]:
        """
        Accepts objects that have 'name' (or 'filename') and 'read()' or 'getvalue()'.
        Or a list of dicts/objects with 'filename' and 'content'.
        """
        uploaded_files = list(files)
        
        # Helper to get filename and content
        processed_files = []
        for f in uploaded_files:
            # Handle dictionary
            if isinstance(f, dict):
                name = f.get("filename") or f.get("name")
                content = f.get("content")
            else:
                # Handle objects (like UploadFile or Streamlit UploadedFile)
                name = getattr(f, "filename", getattr(f, "name", "unknown"))
                if hasattr(f, "getvalue"):
                    content = f.getvalue()
                elif hasattr(f, "read"):
                    # Some objects might need await f.read() if they are async, 
                    # but here we assume sync read or pre-read content.
                    content = f.read()
                else:
                    content = str(f)
            
            if isinstance(content, (bytes, bytearray)):
                content = content.decode("utf-8", errors="replace")
            
            processed_files.append((name, content))

        uploaded_names = {name for name, _ in processed_files}
        findings: list[Finding] = []
        file_results: dict[str, list[Finding]] = {}

        for file_name, text in processed_files:
            suffix = Path(file_name).suffix.lower()

            if suffix not in self.supported_suffixes:
                findings.append(Finding(
                    file=file_name, line=1,
                    category="unsupported_file_type", severity="low",
                    message=f"Skipped '{file_name}' — only .py and .json are supported.",
                    title="Unsupported file type",
                    suggestion="Upload Python or JSON files for analysis.",
                ))
                continue

            if suffix == ".py":
                these = scan_python(text, file_name, uploaded_names)
            else:
                these = scan_json(text, file_name)

            file_results[file_name] = these
            findings.extend(these)

        summary = ScanSummary(
            total_findings=len(findings),
            files_scanned=len(processed_files),
            by_severity=dict(Counter(f.severity for f in findings)),
            by_category=dict(Counter(f.category for f in findings)),
        )

        return {
            "summary":  summary.to_dict(),
            "findings": [f.to_dict() for f in findings],
            "files":    {n: [f.to_dict() for f in g]
                         for n, g in file_results.items()},
        }
