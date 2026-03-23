from __future__ import annotations
import re

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

# Comprehensive Python builtin allowlist
_PYTHON_BUILTINS: frozenset[str] = frozenset({
    "None", "True", "False",
    "abs","all","any","ascii","bin","bool","breakpoint","bytearray","bytes",
    "callable","chr","classmethod","compile","complex","copyright","credits",
    "delattr","dict","dir","divmod","enumerate","eval","exec","exit",
    "filter","float","format","frozenset","getattr","globals","hasattr",
    "hash","help","hex","id","input","int","isinstance","issubclass","iter",
    "len","license","list","locals","map","max","memoryview","min","next",
    "object","oct","open","ord","pow","print","property","quit","range",
    "repr","reversed","round","set","setattr","slice","sorted","staticmethod",
    "str","sum","super","tuple","type","vars","zip",
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
    "__name__","__file__","__doc__","__package__","__spec__",
    "__loader__","__builtins__","__all__","__version__","__author__",
    "self","cls",
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

# Success-narration regex
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

_WRITE_MARKERS: frozenset[str] = frozenset({
    "open","write_text","write_bytes","to_csv","to_json","dump","savefig",
})
_DOC_WRITE_TOKENS: tuple[str, ...] = ("save","write","export","output file")

_OUTPUT_PREFIXES = (
    "get_","fetch_","load_","read_","build_","create_","generate_",
    "compute_","calculate_","find_","search_","parse_","extract_","make_",
    "scan_",
)
_OUTPUT_SUFFIXES = ("_result","_value","_data","_output","_response")
_ACTION_VERBS    = ("get","load","build","create","fetch","parse","scan","read")
