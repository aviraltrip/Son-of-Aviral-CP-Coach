"""Unit tests for Differential Stress Fuzzer and Test Case Management (Phase 8.2)."""
import pytest
from app.judge.fuzzer import (
    InputGenerators,
    find_counterexample,
    stress_test_problem_submission,
    FuzzResult
)
from app.judge.runner import ExecutionConfig
from app.data.db import (
    init_db,
    save_reference_solution,
    upsert_problems,
    seed_dataset_test_cases,
    get_problem_test_cases
)


def test_input_generators():
    # Array generator
    arr_in = InputGenerators.random_int_array(min_n=3, max_n=5, min_val=1, max_val=10)
    lines = arr_in.strip().split("\n")
    assert len(lines) == 2
    n = int(lines[0])
    elements = list(map(int, lines[1].split()))
    assert len(elements) == n

    # Queries generator
    q_in = InputGenerators.random_queries(num_queries=4, min_val=1, max_val=50)
    q_lines = q_in.strip().split("\n")
    assert len(q_lines) == 5
    assert q_lines[0] == "4"

    # String generator
    s_in = InputGenerators.random_string(min_len=5, max_len=10)
    assert len(s_in.strip()) >= 5

    # Tree generator
    tree_in = InputGenerators.random_tree(min_n=4, max_n=6)
    t_lines = tree_in.strip().split("\n")
    n_nodes = int(t_lines[0])
    assert len(t_lines) == n_nodes  # 1 line for n, n-1 lines for edges


def test_differential_fuzzer_matching_solutions():
    # Reference: sums array
    ref_code = """
import sys
data = sys.stdin.read().split()
if data:
    n = int(data[0])
    nums = [int(x) for x in data[1:n+1]]
    print(sum(nums))
"""
    # User: loop sum
    user_code = """
import sys
data = sys.stdin.read().split()
if data:
    n = int(data[0])
    nums = [int(x) for x in data[1:n+1]]
    total = 0
    for x in nums:
        total += x
    print(total)
"""
    res = find_counterexample(
        user_code=user_code,
        user_lang="python3",
        reference_code=ref_code,
        reference_lang="python3",
        max_trials=10
    )
    assert res.counterexample_found is False
    assert res.user_verdict == "AC"
    assert res.trials_run == 10


def test_differential_fuzzer_detects_buggy_solution():
    # Problem: sum of array. Reference is correct.
    ref_code = """
import sys
data = sys.stdin.read().split()
if data:
    n = int(data[0])
    nums = [int(x) for x in data[1:n+1]]
    print(sum(nums))
"""
    # Buggy user code: sums all except ignores negative numbers
    buggy_code = """
import sys
data = sys.stdin.read().split()
if data:
    n = int(data[0])
    nums = [int(x) for x in data[1:n+1]]
    print(sum(x for x in nums if x > 0))
"""
    res = find_counterexample(
        user_code=buggy_code,
        user_lang="python3",
        reference_code=ref_code,
        reference_lang="python3",
        input_generator=lambda: InputGenerators.random_int_array(min_n=2, max_n=5, min_val=-20, max_val=20),
        max_trials=20
    )
    # When random array has negative number, mismatch will trigger
    assert res.counterexample_found is True
    assert res.user_verdict == "WA"
    assert res.failing_input is not None
    assert res.expected_output != res.user_output


def test_differential_fuzzer_detects_timeout():
    ref_code = "print(42)"
    # Buggy code has infinite loop
    buggy_code = """
import time
while True:
    time.sleep(0.05)
"""
    cfg = ExecutionConfig(time_limit_ms=300)
    res = find_counterexample(
        user_code=buggy_code,
        user_lang="python3",
        reference_code=ref_code,
        reference_lang="python3",
        input_generator=lambda: "1\n",
        max_trials=2,
        config=cfg
    )
    assert res.counterexample_found is True
    assert res.user_verdict == "TLE"


def test_stress_test_problem_submission_with_db(temp_db):
    upsert_problems([{"contestId": 2000, "index": "A", "name": "Sum Problem", "rating": 800, "tags": ["math"]}], db_path=temp_db)
    ref_py = """
import sys
data = sys.stdin.read().split()
if data:
    print(int(data[0]) + int(data[1]))
"""
    save_reference_solution(2000, "A", ref_py, "Add two numbers", db_path=temp_db)

    # Buggy user code (multiplies instead of adds)
    user_py = """
import sys
data = sys.stdin.read().split()
if data:
    print(int(data[0]) * int(data[1]))
"""
    res = stress_test_problem_submission(
        contest_id=2000,
        idx="A",
        user_code=user_py,
        user_lang="python3",
        max_trials=10,
        db_path=temp_db
    )
    assert res.counterexample_found is True
    assert res.user_verdict == "WA"


def test_seed_dataset_test_cases(temp_db):
    count = seed_dataset_test_cases(db_path=temp_db)
    assert count > 0
    # Check problem 1900C test case
    cases = get_problem_test_cases(1900, "C", samples_only=True, db_path=temp_db)
    assert len(cases) >= 1
    assert cases[0]["expected_output"] is not None
