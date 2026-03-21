"""
scanner.py — Merged integrity scanner.

Combines detection logic from two independent AI code auditors:
  - Base system (repo-root auditor): strong allowlist, path-based entry point,
    regex narrative checks, structured Finding type.
  - Donor system (ChatGPT auditor): control-flow drift, docstring/write mismatch,
    path-to-nowhere, schema drift, evidence/suggestion fields, ScanEngine class.

Public API
----------
  scan(file_path: Path) -> List[Finding]          # path-based, used by app.py
  ScanEngine().scan_uploaded_files(files) -> dict  # Streamlit file-object based
"""

from __future__ import annotations

import ast
import io
import json
import keyword
import re
import tokenize
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, List


# ---------------------------------------------------------------------------
# Finding schema
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Category constants
# ---------------------------------------------------------------------------

STRUCTURAL_HALLUCINATION  = "structural_hallucination"
SILENT_FAILURE_RISK       = "silent_failure_risk"
PLACEHOLDER_LOGIC         = "placeholder_logic"
TERMINAL_STATE_FAILURE    = "terminal_state_failure"
NARRATIVE_STATE_RISK      = "narrative_state_risk"
CONTROL_FLOW_DRIFT        = "control_flow_drift"       # unreachable code
PATH_TO_NOWHERE           = "path_to_nowhere"           # ref to file not uploaded
SCHEMA_DRIFT              = "schema_drift"              # JSON structure issues
JSON_INTEGRITY_ISSUE      = "json_integrity_issue"      # kept for backwards compat


# ---------------------------------------------------------------------------
# Allowlists
# ---------------------------------------------------------------------------

# Comprehensive Python builtin allowlist — intentionally broad to minimise
# false positives on legitimate code.
_PYTHON_BUILTINS: frozenset[str] = frozenset({
    # keywords covered by keyword.kwlist but handy to include explicitly
    "None", "True", "False",
    # builtins
    "abs","all","any","ascii","bin","bool","breakpoint","bytearray","bytes",
    "callable","chr","classmethod","compile","complex","copyright","credits",
    "delattr","dict","dir","divmod","enumerate","eval","exec","exit",
    "filter","float","format","frozenset","getattr","globals","hasattr",
    "hash","help","hex","id","input","int","isinstance","issubclass","iter",
    "len","license","list","locals","map","max","memoryview","min","next",
    "object","oct","open","ord","pow","print","property","quit","range",
    "repr","reversed","round","set","setattr","slice","sorted","staticmethod",
    "str","sum","super","tuple","type","vars","zip",
    # common exceptions
    "ArithmeticError","AssertionError","AttributeError","BaseException",
    "BlockingIOError","BrokenPipeError","BufferError","BytesWarning",
    "ChildProcessError","ConnectionAbortedError","ConnectionError",
    "ConnectionRefusedError","ConnectionResetError","DeprecationWarning",
    "EOFError","EnvironmentError","Exception","FileExistsError",
    "FileNotFoundError","FloatingPointError","FutureWarning","GeneratorExit",
    "IOError","ImportError","ImportWarning","IndentationError","IndexError",
    "InterruptedError","IsADirectoryError","KeyError","KeyboardInterrupt",
    "LookupError","MemoryError","ModuleNotFoundError","NameError",
    "NotADirectoryError","NotImplemented","NotImplementedError","OSError",
    "OverflowError","PendingDeprecationWarning","PermissionError",
    "ProcessLookupError","RecursionError","ReferenceError","ResourceWarning",
    "RuntimeError","RuntimeWarning","StopAsyncIteration","StopIteration",
    "SyntaxError","SyntaxWarning","SystemError","SystemExit","TimeoutError",
    "TypeError","UnboundLocalError","UnicodeDecodeError","UnicodeEncodeError",
    "UnicodeError","UnicodeTranslateError","UnicodeWarning","UserWarning",
    "ValueError","Warning","ZeroDivisionError",
    # module-level dunders
    "__name__","__file__","__doc__","__package__","__spec__",
    "__loader__","__builtins__","__all__","__version__","__author__",
    # common implicit names
    "self","cls",
    # frequently used without explicit import in type hints / common patterns
    "Path","logging","logger","log","dataclass","field",
})

# Python placeholder string literals
_PY_PLACEHOLDER_STRINGS: frozenset[str] = frozenset({
    "todo","fixme","dummy","placeholder","your_api_key_here","your-key-here",
    "changeme","mock","sample","example","lorem ipsum","tbd","temp","temporary",
    "test","foo","bar","baz","n/a","na","xxx","...",
})

# JSON placeholder values
_JSON_PLACEHOLDER_STRINGS: frozenset[str] = _PY_PLACEHOLDER_STRINGS | frozenset({
    "<insert>","<todo>","<value>","<placeholder>","replace_me",
    "none","null","undefined",
})

# JSON sample credential / URL tokens
_JSON_CREDENTIAL_TOKENS: tuple[str, ...] = (
    "http://example.com","https://example.com",
    "your-api-key","your_api_key","insert-key","replace_me",
    "api_key_here","secret_here","token_here",
)

# Success-narration regex (line-level fallback)
_SUCCESS_PRINT_RE = re.compile(
    r"""(?:print|logging\.\w+|logger\.\w+|log\.\w+)\s*\([^)]*
    \b(?:success|succeeded|completed|done|finished|saved|written|created|uploaded)\b""",
    re.IGNORECASE | re.VERBOSE,
)

_WRITE_SIGNALS: frozenset[str] = frozenset({
    "write","save","dump","export","return","commit",
    "insert","update","upload","send","put","post",
    "write_text","write_bytes","to_csv","to_json","savefig",
})


# ---------------------------------------------------------------------------
# Path-based public entry point  (used by app.py)
# ---------------------------------------------------------------------------

def scan(file_path: Path, uploaded_names: set[str] | None = None) -> List[Finding]:
    """
    Scan a single file and return all findings.

    Args:
        file_path:      Path to the saved file.
        uploaded_names: Set of filenames present in the same upload batch.
                        Used for path-to-nowhere detection. Defaults to
                        {file_path.name} when not supplied.
    """
    suffix = file_path.suffix.lower()
    uploaded_names = uploaded_names or {file_path.name}

    if suffix == ".py":
        source = file_path.read_text(encoding="utf-8", errors="replace")
        return _scan_python(source, file_path.name, uploaded_names)

    if suffix == ".json":
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        return _scan_json(raw, file_path.name)

    raise ValueError(
        f"Unsupported file type: '{suffix}'. Only .py and .json are supported."
    )


# ---------------------------------------------------------------------------
# ScanEngine  (Streamlit file-object based entry point from donor system)
# ---------------------------------------------------------------------------

class ScanEngine:
    """
    Accepts Streamlit UploadedFile objects directly.
    Returns a dict compatible with the donor system's reporting layer.
    """

    supported_suffixes = {".py", ".json"}

    def scan_uploaded_files(self, uploaded_files: Iterable[Any]) -> dict[str, Any]:
        files = list(uploaded_files)
        uploaded_names = {getattr(f, "name", "unknown") for f in files}
        findings: list[Finding] = []
        file_results: dict[str, list[Finding]] = {}

        for file_obj in files:
            file_name = getattr(file_obj, "name", "uploaded_file")
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

            raw = (file_obj.getvalue()
                   if hasattr(file_obj, "getvalue") else file_obj.read())
            text = (raw.decode("utf-8", errors="replace")
                    if isinstance(raw, (bytes, bytearray)) else str(raw))

            if suffix == ".py":
                these = _scan_python(text, file_name, uploaded_names)
            else:
                these = _scan_json(text, file_name)

            file_results[file_name] = these
            findings.extend(these)

        summary = ScanSummary(
            total_findings=len(findings),
            files_scanned=len(files),
            by_severity=dict(Counter(f.severity for f in findings)),
            by_category=dict(Counter(f.category for f in findings)),
        )

        return {
            "summary":  summary.to_dict(),
            "findings": [f.to_dict() for f in findings],
            "files":    {n: [f.to_dict() for f in g]
                         for n, g in file_results.items()},
        }


# ---------------------------------------------------------------------------
# Python scanning — internal
# ---------------------------------------------------------------------------

def _scan_python(
    source: str,
    filename: str,
    uploaded_names: set[str] | None = None,
) -> List[Finding]:
    uploaded_names = uploaded_names or {filename}
    findings: List[Finding] = []

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        lines = source.splitlines()
        lineno = exc.lineno or 1
        evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
        findings.append(Finding(
            file=filename, line=lineno,
            category=STRUCTURAL_HALLUCINATION, severity="high",
            title="Syntax error",
            message=f"File could not be parsed: {exc.msg}",
            evidence=evidence,
            suggestion="Fix syntax first, then re-run the scan.",
        ))
        return findings

    findings.extend(_check_undefined_names(tree, source, filename))
    findings.extend(_check_except_rules(tree, source, filename))
    findings.extend(_check_placeholder_nodes(tree, source, filename))
    findings.extend(_check_placeholder_literals(tree, source, filename))
    findings.extend(_check_terminal_state(tree, source, filename))
    findings.extend(_check_unreachable_code(tree, source, filename))
    findings.extend(_check_docstring_write_mismatch(tree, source, filename))
    findings.extend(_check_narrative_state(tree, source, filename))
    findings.extend(_check_path_to_nowhere(tree, source, filename, uploaded_names))
    findings.extend(_check_todo_comments(source, filename))

    findings.sort(key=lambda f: f.line)
    return findings


# ── Undefined names ──────────────────────────────────────────────────────────

def _collect_definitions(tree: ast.Module) -> set[str]:
    defined: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                defined.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    defined.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                defined.update(_names_in_target(t))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            defined.update(_names_in_target(node.target))
        elif isinstance(node, ast.NamedExpr):
            defined.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            args = node.args
            for arg in args.args + args.posonlyargs + args.kwonlyargs:
                defined.add(arg.arg)
            if args.vararg:  defined.add(args.vararg.arg)
            if args.kwarg:   defined.add(args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            defined.update(_names_in_target(node.target))
        elif isinstance(node, ast.withitem):
            if node.optional_vars:
                defined.update(_names_in_target(node.optional_vars))
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                defined.add(node.name)
        elif isinstance(node, ast.comprehension):
            defined.update(_names_in_target(node.target))
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            defined.update(node.names)
        # Lambda parameters — e.g. lambda x: x[1]
        elif isinstance(node, ast.Lambda):
            args = node.args
            for arg in args.args + args.posonlyargs + args.kwonlyargs:
                defined.add(arg.arg)
            if args.vararg: defined.add(args.vararg.arg)
            if args.kwarg:  defined.add(args.kwarg.arg)
    return defined


def _names_in_target(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        out: list[str] = []
        for elt in node.elts:
            out.extend(_names_in_target(elt))
        return out
    if isinstance(node, ast.Starred):
        return _names_in_target(node.value)
    return []


def _check_undefined_names(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
    lines = source.splitlines()
    known = (
        _collect_definitions(tree)
        | _PYTHON_BUILTINS
        | set(keyword.kwlist)
    )
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id not in known
            and not node.id.startswith("__")
        ):
            lineno = node.lineno
            evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
            findings.append(Finding(
                file=filename, line=lineno,
                category=STRUCTURAL_HALLUCINATION, severity="high",
                title="Name used but not defined",
                message=(
                    f"'{node.id}' is used but was not found in local "
                    f"definitions, imports, or the builtin allowlist."
                ),
                evidence=evidence,
                suggestion="Define it, import it, or check for a typo.",
            ))
    return findings


# ── Except rules ─────────────────────────────────────────────────────────────

def _check_except_rules(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
    lines = source.splitlines()
    findings: List[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        lineno = node.lineno
        evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""

        # Bare except:
        if node.type is None:
            findings.append(Finding(
                file=filename, line=lineno,
                category=SILENT_FAILURE_RISK, severity="high",
                title="Bare except block",
                message=(
                    "Bare 'except:' catches every exception including "
                    "KeyboardInterrupt and SystemExit — can mask real failures."
                ),
                evidence=evidence,
                suggestion="Catch specific exceptions and log or re-raise unexpected ones.",
            ))

        # Except-pass (body is only pass)
        if all(isinstance(s, ast.Pass) for s in node.body):
            findings.append(Finding(
                file=filename, line=lineno,
                category=SILENT_FAILURE_RISK, severity="high",
                title="Exception swallowed with pass",
                message=(
                    "Exception handler body is only 'pass' — the exception "
                    "is silently swallowed with no logging or re-raise."
                ),
                evidence=evidence,
                suggestion=(
                    "Return an explicit failure object, log the error, "
                    "or re-raise a meaningful exception."
                ),
            ))

    return findings


# ── Placeholder nodes ─────────────────────────────────────────────────────────

def _check_placeholder_nodes(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
    lines = source.splitlines()
    findings: List[Finding] = []

    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", 0)
        evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""

        if isinstance(node, ast.Pass):
            findings.append(Finding(
                file=filename, line=lineno,
                category=PLACEHOLDER_LOGIC, severity="medium",
                title="Pass statement",
                message=(
                    "'pass' found — body may be intentionally empty "
                    "or implementation is incomplete."
                ),
                evidence=evidence,
                suggestion="Replace with real logic or remove the enclosing block.",
            ))

        if isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc
            name = None
            if isinstance(exc, ast.Name):
                name = exc.id
            elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                name = exc.func.id
            if name == "NotImplementedError":
                findings.append(Finding(
                    file=filename, line=lineno,
                    category=PLACEHOLDER_LOGIC, severity="high",
                    title="NotImplementedError stub",
                    message=(
                        "NotImplementedError raised — this function is a stub "
                        "and has not been implemented."
                    ),
                    evidence=evidence,
                    suggestion=(
                        "Implement the function body before treating "
                        "this code as production-ready."
                    ),
                ))

    return findings


# ── Placeholder string literals (from donor system) ──────────────────────────

def _check_placeholder_literals(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
    """Flag string constants that look like AI-generated placeholder values."""
    lines = source.splitlines()
    findings: List[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        val = node.value.strip().lower()
        if val in _PY_PLACEHOLDER_STRINGS:
            lineno = node.lineno
            evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
            findings.append(Finding(
                file=filename, line=lineno,
                category=PLACEHOLDER_LOGIC, severity="low",
                title="Placeholder string literal",
                message=f"String literal '{node.value}' looks like a placeholder value.",
                evidence=evidence,
                suggestion=(
                    "Replace with a real config value, validated default, "
                    "or document it explicitly as a sample."
                ),
            ))

    return findings


# ── Terminal state failure ────────────────────────────────────────────────────

_OUTPUT_PREFIXES = (
    "get_","fetch_","load_","read_","build_","create_","generate_",
    "compute_","calculate_","find_","search_","parse_","extract_","make_",
    "scan_",
)
_OUTPUT_SUFFIXES = ("_result","_value","_data","_output","_response")
_ACTION_VERBS    = ("get","load","build","create","fetch","parse","scan","read")


def _check_terminal_state(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
    lines = source.splitlines()
    findings: List[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        lineno = node.lineno
        evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""

        # Name implies it returns a value
        implies_output = (
            any(name.startswith(p) for p in _OUTPUT_PREFIXES)
            or any(name.endswith(s) for s in _OUTPUT_SUFFIXES)
            or name.lower().startswith(_ACTION_VERBS)
        )
        if not implies_output:
            continue

        all_returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
        has_value_return = any(r.value is not None for r in all_returns)
        has_empty_return = any(r.value is None for r in all_returns)

        # No return at all
        if not all_returns:
            findings.append(Finding(
                file=filename, line=lineno,
                category=TERMINAL_STATE_FAILURE, severity="medium",
                title="Possible missing return",
                message=(
                    f"Function '{name}' name implies it returns a value "
                    f"but contains no return statement."
                ),
                evidence=evidence,
                suggestion=(
                    "Return a concrete value on all branches or rename "
                    "the function to reflect it only produces side effects."
                ),
            ))
        # Mixed: some branches return values, others return None implicitly
        elif has_value_return and has_empty_return:
            findings.append(Finding(
                file=filename, line=lineno,
                category=TERMINAL_STATE_FAILURE, severity="medium",
                title="Inconsistent return paths",
                message=(
                    f"Function '{name}' has branches that return a value "
                    f"and branches that return None implicitly."
                ),
                evidence=evidence,
                suggestion="Ensure all code paths return a consistent type.",
            ))

    return findings


# ── Unreachable code (from donor system) ─────────────────────────────────────

def _block_has_unreachable(stmts: list[ast.stmt]) -> bool:
    terminated = False
    for stmt in stmts:
        if terminated:
            return True
        if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            terminated = True
    return False


def _check_unreachable_code(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
    lines = source.splitlines()
    findings: List[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        lineno = node.lineno
        evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""

        for child in ast.walk(node):
            for attr in ("body", "orelse", "finalbody"):
                block = getattr(child, attr, None)
                if (
                    isinstance(block, list)
                    and block
                    and all(isinstance(x, ast.stmt) for x in block)
                    and _block_has_unreachable(block)
                ):
                    findings.append(Finding(
                        file=filename, line=lineno,
                        category=CONTROL_FLOW_DRIFT, severity="medium",
                        title="Possible unreachable code",
                        message=(
                            f"Function '{node.name}' contains statements "
                            f"after a return/raise/break/continue in the same block."
                        ),
                        evidence=evidence,
                        suggestion=(
                            "Remove the dead branch or refactor the "
                            "control flow so all statements are reachable."
                        ),
                    ))
                    # One finding per function is enough
                    break
            else:
                continue
            break

    return findings


# ── Docstring / write mismatch (from donor system) ───────────────────────────

_WRITE_MARKERS: frozenset[str] = frozenset({
    "open","write_text","write_bytes","to_csv","to_json","dump","savefig",
})
_DOC_WRITE_TOKENS: tuple[str, ...] = ("save","write","export","output file")


def _check_docstring_write_mismatch(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
    lines = source.splitlines()
    findings: List[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node)
        if not doc:
            continue
        doc_lower = doc.lower()
        claims_write = any(tok in doc_lower for tok in _DOC_WRITE_TOKENS)
        if not claims_write:
            continue

        actually_writes = any(
            isinstance(child, ast.Call)
            and (
                (isinstance(child.func, ast.Name) and child.func.id in _WRITE_MARKERS)
                or (isinstance(child.func, ast.Attribute) and child.func.attr in _WRITE_MARKERS)
            )
            for child in ast.walk(node)
        )

        if not actually_writes:
            lineno = node.lineno
            evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
            findings.append(Finding(
                file=filename, line=lineno,
                category=NARRATIVE_STATE_RISK, severity="medium",
                title="Docstring/output mismatch",
                message=(
                    f"Function '{node.name}' docstring claims to save or "
                    f"write output, but no file-write call was detected."
                ),
                evidence=evidence,
                suggestion=(
                    "Update the docstring to reflect actual behavior, "
                    "or implement the missing write path."
                ),
            ))

    return findings


# ── Narrative state risk ──────────────────────────────────────────────────────

def _check_narrative_state(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
    """
    Two-pass check:
      1. AST: print() calls with success-string literals (precise).
      2. Regex: broader log/print patterns (catches f-strings, variables).
    """
    lines = source.splitlines()
    findings: List[Finding] = []
    flagged_lines: set[int] = set()

    _SUCCESS_WORDS = {"success","completed","done","saved","finished","created","uploaded"}

    # Pass 1 — AST: print("...success...")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "print"):
            continue
        for arg in node.args:
            if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                continue
            if any(w in arg.value.lower() for w in _SUCCESS_WORDS):
                lineno = node.lineno
                evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
                findings.append(Finding(
                    file=filename, line=lineno,
                    category=NARRATIVE_STATE_RISK, severity="low",
                    title="Success narration detected",
                    message=(
                        "This print() claims success/completion. Verify the code "
                        "actually changes state or writes output before printing it."
                    ),
                    evidence=evidence,
                    suggestion=(
                        "Log success only after validating the expected "
                        "artifact or state exists."
                    ),
                ))
                flagged_lines.add(lineno)

    # Pass 2 — regex: broader log/print patterns not caught by AST
    for i, line in enumerate(lines, start=1):
        if i in flagged_lines:
            continue
        if not _SUCCESS_PRINT_RE.search(line):
            continue
        window = "\n".join(lines[max(0, i - 4):min(len(lines), i + 2)])
        if not any(sig in window for sig in _WRITE_SIGNALS):
            findings.append(Finding(
                file=filename, line=i,
                category=NARRATIVE_STATE_RISK, severity="medium",
                title="Unverified success message",
                message=(
                    "A success/completion message is logged without a "
                    "nearby write, save, or state-change operation."
                ),
                evidence=line.strip(),
                suggestion=(
                    "Confirm state was actually changed before logging success."
                ),
            ))

    return findings


# ── Path-to-nowhere (from donor system) ──────────────────────────────────────

def _check_path_to_nowhere(
    tree: ast.Module,
    source: str,
    filename: str,
    uploaded_names: set[str],
) -> List[Finding]:
    """
    Flag open() calls and string literals that look like local file paths
    where the referenced file was not part of the upload batch.
    """
    lines = source.splitlines()
    findings: List[Finding] = []
    candidates: list[tuple[int, str]] = []

    # Collect line numbers of docstrings to exclude from path scanning
    docstring_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef, ast.Module)):
            doc_node = (node.body[0] if node.body and
                        isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, ast.Constant) and
                        isinstance(node.body[0].value.value, str)
                        else None)
            if doc_node:
                docstring_lines.add(doc_node.lineno)

    for node in ast.walk(tree):
        # open("some_file.csv")
        if isinstance(node, ast.Call):
            func = node.func
            is_open = (isinstance(func, ast.Name) and func.id == "open") or (
                isinstance(func, ast.Attribute) and func.attr == "open"
            )
            if is_open and node.args:
                lit = node.args[0]
                if isinstance(lit, ast.Constant) and isinstance(lit.value, str):
                    candidates.append((node.lineno, lit.value))

        # string literals that look like paths (contain / or \)
        # Skip docstrings — slashes in docstrings are prose, not paths
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            lineno = getattr(node, "lineno", 0)
            if (("/" in val or "\\" in val) and len(val) > 3
                    and lineno not in docstring_lines):
                candidates.append((lineno, val))

    for lineno, path in candidates:
        # Skip template placeholders — strings containing < or > are
        # clearly not real file paths (e.g. "scan_<timestamp>/")
        if "<" in path or ">" in path:
            continue

        clean = Path(path).name
        looks_local = (
            not path.startswith(("http://", "https://"))
            and "." in clean
            and len(clean) > 1
        )
        if looks_local and clean not in uploaded_names:
            evidence = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
            findings.append(Finding(
                file=filename, line=lineno,
                category=PATH_TO_NOWHERE, severity="medium",
                title="Referenced file not uploaded",
                message=(
                    f"Code references '{path}' but that file was not "
                    f"among the uploaded artifacts."
                ),
                evidence=evidence,
                suggestion=(
                    "Upload the referenced file too, or make the path "
                    "configurable and validate its existence at runtime."
                ),
            ))

    return findings


# ── TODO / FIXME comments ────────────────────────────────────────────────────

def _check_todo_comments(source: str, filename: str) -> List[Finding]:
    findings: List[Finding] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok_type, tok_str, start, _, _ in tokens:
            if tok_type != tokenize.COMMENT:
                continue
            upper = tok_str.upper()
            if any(m in upper for m in ("TODO","FIXME","HACK","TEMPORARY")):
                findings.append(Finding(
                    file=filename, line=start[0],
                    category=PLACEHOLDER_LOGIC, severity="low",
                    title="Suspicious comment marker",
                    message=f"Comment suggests unfinished or temporary logic: {tok_str.strip()}",
                    evidence=tok_str.strip(),
                    suggestion=(
                        "Verify this branch is production-safe and not "
                        "an AI-generated placeholder."
                    ),
                ))
    except tokenize.TokenError:
        pass
    return findings


# ---------------------------------------------------------------------------
# JSON scanning — internal
# ---------------------------------------------------------------------------

class _DuplicateKeyDetector:
    def __init__(self):
        self.duplicates: list[tuple[str, int]] = []

    def hook(self, pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        counts = Counter(key for key, _ in pairs)
        for key, count in counts.items():
            if count > 1:
                self.duplicates.append((key, count))
        return dict(pairs)


def _scan_json(raw: str, filename: str) -> List[Finding]:
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

    # 4. Null density (35% threshold — catches partially-generated schemas)
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
        # Mixed key naming convention
        key_styles: dict[str, int] = defaultdict(int)
        for key, value in data.items():
            if "_" in key:
                key_styles["snake_case"] += 1
            elif any(ch.isupper() for ch in key[1:]):
                key_styles["camelCase"] += 1
            else:
                key_styles["other"] += 1
            _walk_json(value, findings, filename, f"{path}.{key}")

        if path == "$":  # only flag at root level to avoid noise
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

        # Placeholder values
        if val in _JSON_PLACEHOLDER_STRINGS:
            findings.append(Finding(
                file=filename, line=1,
                category=JSON_INTEGRITY_ISSUE, severity="medium",
                title="Placeholder JSON value",
                message=f"Placeholder value '{data}' found at {path}.",
                evidence=path,
                suggestion="Replace with a validated real value.",
            ))

        # Sample credentials / URLs
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
