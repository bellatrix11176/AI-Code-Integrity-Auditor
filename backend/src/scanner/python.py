from __future__ import annotations
import ast
import io
import keyword
import tokenize
from pathlib import Path
from typing import List

from src.core.models import Finding
from src.core.constants import (
    STRUCTURAL_HALLUCINATION,
    SILENT_FAILURE_RISK,
    PLACEHOLDER_LOGIC,
    TERMINAL_STATE_FAILURE,
    NARRATIVE_STATE_RISK,
    CONTROL_FLOW_DRIFT,
    PATH_TO_NOWHERE,
    _PYTHON_BUILTINS,
    _PY_PLACEHOLDER_STRINGS,
    _SUCCESS_PRINT_RE,
    _WRITE_SIGNALS,
    _WRITE_MARKERS,
    _DOC_WRITE_TOKENS,
    _OUTPUT_PREFIXES,
    _OUTPUT_SUFFIXES,
    _ACTION_VERBS,
)

def scan_python(
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


def _check_placeholder_literals(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
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
                    break
            else:
                continue
            break

    return findings


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


def _check_narrative_state(
    tree: ast.Module, source: str, filename: str
) -> List[Finding]:
    lines = source.splitlines()
    findings: List[Finding] = []
    flagged_lines: set[int] = set()

    _SUCCESS_WORDS = {"success","completed","done","saved","finished","created","uploaded"}

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


def _check_path_to_nowhere(
    tree: ast.Module,
    source: str,
    filename: str,
    uploaded_names: set[str],
) -> List[Finding]:
    lines = source.splitlines()
    findings: List[Finding] = []
    candidates: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            is_open = (isinstance(func, ast.Name) and func.id == "open") or (
                isinstance(func, ast.Attribute) and func.attr == "open"
            )
            if is_open and node.args:
                lit = node.args[0]
                if isinstance(lit, ast.Constant) and isinstance(lit.value, str):
                    candidates.append((node.lineno, lit.value))

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            if ("/" in val or "\\" in val) and len(val) > 3:
                candidates.append((getattr(node, "lineno", 0), val))

    for lineno, path in candidates:
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
