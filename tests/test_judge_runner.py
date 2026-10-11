"""Unit tests for Sandboxed Code Execution and Runner (Phase 8.1)."""
import pytest
from app.judge.runner import (
    ExecutionConfig,
    ExecutionResult,
    compile_code,
    run_isolated,
    evaluate_test_case,
    normalize_output
)

def test_normalize_output():
    raw = "  123 456   \r\n789   \n\n\n"
    assert normalize_output(raw) == "  123 456\n789"

def test_python_syntax_error_compilation():
    bad_py = "def broken_code(\n  print('missing paren'"
    res = evaluate_test_case(
        source_code=bad_py,
        language="python3",
        input_data="",
        expected_output=""
    )
    assert res.verdict == "CE"
    assert "Syntax" in res.error_message or "syntax" in res.error_message.lower() or "error" in res.error_message.lower()

def test_python_accepted_execution():
    code = """
import sys
data = sys.stdin.read().split()
if data:
    a, b = int(data[0]), int(data[1])
    print(a + b)
"""
    res = evaluate_test_case(
        source_code=code,
        language="python3",
        input_data="15 27\n",
        expected_output="42\n"
    )
    assert res.verdict == "AC"
    assert res.stdout.strip() == "42"
    assert res.time_ms >= 0.0

def test_python_wrong_answer_execution():
    code = "print(100)"
    res = evaluate_test_case(
        source_code=code,
        language="python3",
        input_data="",
        expected_output="200"
    )
    assert res.verdict == "WA"
    assert "Expected" in res.error_message

def test_python_time_limit_exceeded():
    code = """
import time
while True:
    time.sleep(0.1)
"""
    config = ExecutionConfig(time_limit_ms=500)
    res = evaluate_test_case(
        source_code=code,
        language="python3",
        input_data="",
        expected_output="done",
        config=config
    )
    assert res.verdict == "TLE"
    assert "Time Limit Exceeded" in res.error_message

def test_python_runtime_error():
    code = "print(1 / 0)"
    res = evaluate_test_case(
        source_code=code,
        language="python3",
        input_data="",
        expected_output="10"
    )
    assert res.verdict == "RE"
    assert res.exit_code != 0
    assert "ZeroDivisionError" in res.stderr

def test_cpp_accepted_execution():
    cpp_code = r"""
#include <iostream>
using namespace std;
int main() {
    long long a, b;
    if (cin >> a >> b) {
        cout << a * b << "\n";
    }
    return 0;
}
"""
    res = evaluate_test_case(
        source_code=cpp_code,
        language="cpp",
        input_data="7 8\n",
        expected_output="56\n"
    )
    if res.verdict == "CE" and "No C++ compiler" in res.error_message:
        pytest.skip("g++ not available on host system")
    assert res.verdict == "AC"
    assert res.stdout.strip() == "56"

def test_sandbox_security_guard_blocks_malicious_code():
    from app.judge.runner import validate_source_code_safety
    
    safe_py = "import sys\nprint(42)"
    is_safe, err = validate_source_code_safety(safe_py, "python")
    assert is_safe is True
    assert err is None
    
    bad_py_os = "import os\nos.system('dir')"
    is_safe, err = validate_source_code_safety(bad_py_os, "python")
    assert is_safe is False
    assert "Forbidden import 'os'" in err

    bad_py_sub = "from subprocess import Popen"
    is_safe, err = validate_source_code_safety(bad_py_sub, "python")
    assert is_safe is False
    assert "Forbidden import from 'subprocess'" in err

    bad_py_exec = "exec('print(1)')"
    is_safe, err = validate_source_code_safety(bad_py_exec, "python")
    assert is_safe is False
    assert "Forbidden built-in function 'exec'" in err

    safe_cpp = "#include <iostream>\nint main() { return 0; }"
    is_safe, err = validate_source_code_safety(safe_cpp, "cpp")
    assert is_safe is True

    bad_cpp_sys = "#include <iostream>\nint main() { system(\"rm -rf\"); }"
    is_safe, err = validate_source_code_safety(bad_cpp_sys, "cpp")
    assert is_safe is False
    assert "Forbidden C++ system operation" in err

    bad_cpp_hdr = "#include <cstdlib>\nint main() { return 0; }"
    is_safe, err = validate_source_code_safety(bad_cpp_hdr, "cpp")
    assert is_safe is False

    bad_java = "public class Solution { public static void main(String[] args) { Runtime.getRuntime().exec(\"calc\"); } }"
    is_safe, err = validate_source_code_safety(bad_java, "java")
    assert is_safe is False
    assert "Forbidden Java system operation" in err

    res = evaluate_test_case(bad_py_os, language="python3", input_data="", expected_output="")
    assert res.verdict == "CE"
    assert "Security Violation" in res.error_message

def test_subclasses_introspection_blocked():
    """Verify that dynamic introspection payloads attempting to access builtins are blocked."""
    from app.judge.runner import validate_source_code_safety
    payload = "s = [c for c in ().__class__.__base__.__subclasses__() if c.__name__ == 'BuiltinImporter']"
    is_safe, err = validate_source_code_safety(payload, "python")
    assert is_safe is False
    assert "Forbidden" in err

def test_environment_sanitization_in_execution(monkeypatch):
    """Verify that execution subprocesses cannot read secrets from parent process environment."""
    from app.judge.runner import evaluate_test_case
    monkeypatch.setenv("LEAK_TEST_SECRET_API_KEY", "top_secret_token_12345")
    
    code = """
import os
val = os.environ.get('LEAK_TEST_SECRET_API_KEY', 'NOT_FOUND')
print(val)
"""
    from app.judge.runner import get_sanitized_execution_env
    clean_env = get_sanitized_execution_env()
    assert "LEAK_TEST_SECRET_API_KEY" not in clean_env
    assert "OPENROUTER_API_KEY" not in clean_env

def test_disabled_judge_backend_routing():
    """Verify that when backend is disabled, evaluate_test_case returns a safe UNKNOWN verdict."""
    from app.judge.runner import evaluate_test_case
    res = evaluate_test_case("print(1)", language="python3", input_data="", expected_output="", backend="disabled")
    assert res.verdict == "UNKNOWN"
    assert "disabled" in res.error_message.lower()

def test_judge0_backend_routing_fallback(monkeypatch):
    """Verify Judge0 routing gracefully handles network connection failures."""
    from app.judge.runner import evaluate_test_case
    monkeypatch.setenv("JUDGE0_URL", "http://127.0.0.1:59999")
    res = evaluate_test_case("print(1)", language="python3", input_data="", expected_output="", backend="judge0")
    assert res.verdict == "UNKNOWN"
    assert "Failed to communicate with Judge0" in res.error_message
