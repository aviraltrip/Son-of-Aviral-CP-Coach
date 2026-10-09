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
    # If g++ is present, it will be AC
    if res.verdict == "CE" and "No C++ compiler" in res.error_message:
        pytest.skip("g++ not available on host system")
    assert res.verdict == "AC"
    assert res.stdout.strip() == "56"
