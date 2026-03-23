from src.scanner.python import scan_python
from src.core.models import Finding

def test_structural_hallucination():
    source_code = """def my_func():
    return hallucinated_variable
"""
    findings = scan_python(source_code, "test.py")
    assert len(findings) == 1
    assert findings[0].category == "structural_hallucination"
    assert findings[0].line == 2

def test_silent_failure_risk():
    source_code = """try:
    do_something()
except Exception:
    pass
"""
    findings = scan_python(source_code, "test.py")
    assert any(f.category == "silent_failure_risk" for f in findings)
