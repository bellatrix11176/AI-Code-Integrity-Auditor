from __future__ import annotations
import json
from collections import Counter, defaultdict
from typing import Any, List

from src.core.models import Finding
from src.core.constants import (
    JSON_INTEGRITY_ISSUE,
    SCHEMA_DRIFT,
    _JSON_PLACEHOLDER_STRINGS,
    _JSON_CREDENTIAL_TOKENS,
)

class _DuplicateKeyDetector:
    def __init__(self):
        self.duplicates: list[tuple[str, int]] = []

    def hook(self, pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        counts = Counter(key for key, _ in pairs)
        for key, count in counts.items():
            if count > 1:
                self.duplicates.append((key, count))
        return dict(pairs)


def scan_json(raw: str, filename: str) -> List[Finding]:
    findings: List[Finding] = []

    # 1. Validity
    detector = _DuplicateKeyDetector()
    try:
        data = json.loads(raw, object_pairs_hook=detector.hook)
    except json.JSONDecodeError as exc:
        lines = exc.doc.splitlines() if exc.doc else []
        evidence = lines[exc.lineno - 1].strip() if lines and exc.lineno <= len(lines) else ""
        findings.append(Finding(
            file=filename, line=exc.lineno,
            category=JSON_INTEGRITY_ISSUE, severity="high",
            title="Invalid JSON",
            message=f"JSON parse error: {exc.msg} (line {exc.lineno}, col {exc.colno})",
            evidence=evidence,
            suggestion="Fix JSON syntax first, then re-run the scan.",
        ))
        return findings

    # 2. Duplicate keys
    for key, count in detector.duplicates:
        findings.append(Finding(
            file=filename, line=1,
            category=SCHEMA_DRIFT, severity="high",
            title="Duplicate JSON key",
            message=(
                f"Key '{key}' appears {count} times. "
                f"JSON parsers silently keep only the last value."
            ),
            evidence=key,
            suggestion="Remove duplicates and keep one authoritative key.",
        ))

    # 3. Walk values
    _walk_json(data, findings, filename)

    # 4. Null density
    null_ratio = _compute_null_ratio(data)
    if null_ratio > 0.35:
        findings.append(Finding(
            file=filename, line=1,
            category=SCHEMA_DRIFT, severity="medium",
            title="High null density",
            message=(
                f"{null_ratio:.0%} of terminal values are null. "
                f"This can indicate a partial or AI-generated schema."
            ),
            evidence=filename,
            suggestion="Verify whether nulls are intentional and document them.",
        ))

    findings.sort(key=lambda f: f.line)
    return findings


def _walk_json(
    data: Any,
    findings: list[Finding],
    filename: str,
    path: str = "$",
) -> None:
    if isinstance(data, dict):
        key_styles: dict[str, int] = defaultdict(int)
        for key, value in data.items():
            if "_" in key:
                key_styles["snake_case"] += 1
            elif any(ch.isupper() for ch in key[1:]):
                key_styles["camelCase"] += 1
            else:
                key_styles["other"] += 1
            _walk_json(value, findings, filename, f"{path}.{key}")

        if path == "$":
            active = [k for k, v in key_styles.items() if v > 0 and k != "other"]
            if len(active) > 1:
                findings.append(Finding(
                    file=filename, line=1,
                    category=SCHEMA_DRIFT, severity="low",
                    title="Mixed key naming styles",
                    message=(
                        "Top-level JSON keys mix snake_case and camelCase. "
                        "This often signals AI-generated schema drift."
                    ),
                    evidence=path,
                    suggestion="Standardize naming conventions before other code depends on the schema.",
                ))

    elif isinstance(data, list):
        for i, value in enumerate(data):
            _walk_json(value, findings, filename, f"{path}[{i}]")

    elif isinstance(data, str):
        val = data.strip().lower()

        if val in _JSON_PLACEHOLDER_STRINGS:
            findings.append(Finding(
                file=filename, line=1,
                category=JSON_INTEGRITY_ISSUE, severity="medium",
                title="Placeholder JSON value",
                message=f"Placeholder value '{data}' found at {path}.",
                evidence=path,
                suggestion="Replace with a validated real value.",
            ))

        if any(tok in val for tok in _JSON_CREDENTIAL_TOKENS):
            findings.append(Finding(
                file=filename, line=1,
                category=JSON_INTEGRITY_ISSUE, severity="medium",
                title="Sample credential or URL",
                message=f"Sample-looking URL or credential found at {path}.",
                evidence=data,
                suggestion=(
                    "Swap examples for real configuration values, "
                    "or document them clearly as samples."
                ),
            ))


def _compute_null_ratio(data: Any) -> float:
    total = nulls = 0

    def walk(value: Any) -> None:
        nonlocal total, nulls
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        else:
            total += 1
            if value is None:
                nulls += 1

    walk(data)
    return (nulls / total) if total else 0.0
