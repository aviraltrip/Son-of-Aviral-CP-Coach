"""Differential Stress Fuzzer and Counterexample Generator for CP Coach.

Generates random structured test inputs, compares candidate code against
the ground-truth reference solution, and isolates minimal failing counterexamples.
"""
import os
import random
import string
import tempfile
from pathlib import Path
from typing import Callable, Literal, Any
from pydantic import BaseModel, Field

from app.judge.runner import (
    ExecutionConfig,
    ExecutionResult,
    compile_code,
    run_isolated,
    normalize_output,
    LanguageType,
    VerdictType
)
from app.data.db import get_reference_solution, DEFAULT_DB_PATH


class FuzzResult(BaseModel):
    """Result of a differential fuzzing session."""
    counterexample_found: bool = Field(False, description="Whether a failing counterexample was detected")
    trials_run: int = Field(0, description="Number of fuzzing test trials executed")
    user_verdict: VerdictType | None = Field(None, description="Verdict on the failing counterexample")
    failing_input: str | None = Field(None, description="Input string triggering the discrepancy")
    expected_output: str | None = Field(None, description="Output produced by reference solution")
    user_output: str | None = Field(None, description="Output produced by user submission")
    error_message: str | None = Field(None, description="Diagnostic error description")


class InputGenerators:
    """Standard competitive programming input generators."""

    @staticmethod
    def random_int_array(
        min_n: int = 1,
        max_n: int = 10,
        min_val: int = -100,
        max_val: int = 100
    ) -> str:
        """Generates: n \n a_1 a_2 ... a_n"""
        n = random.randint(min_n, max_n)
        arr = [random.randint(min_val, max_val) for _ in range(n)]
        return f"{n}\n" + " ".join(map(str, arr)) + "\n"

    @staticmethod
    def random_queries(
        num_queries: int = 5,
        min_val: int = 1,
        max_val: int = 1000
    ) -> str:
        """Generates: t \n q_1 \n q_2 ... q_t"""
        t = num_queries
        lines = [str(t)]
        for _ in range(t):
            lines.append(f"{random.randint(min_val, max_val)} {random.randint(min_val, max_val)}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def random_string(
        min_len: int = 1,
        max_len: int = 20,
        charset: str = string.ascii_lowercase
    ) -> str:
        """Generates a random string."""
        length = random.randint(min_len, max_len)
        s = "".join(random.choice(charset) for _ in range(length))
        return f"{s}\n"

    @staticmethod
    def random_tree(
        min_n: int = 2,
        max_n: int = 10
    ) -> str:
        """Generates a valid unweighted tree on n vertices: n \n u_1 v_1 ..."""
        n = random.randint(min_n, max_n)
        edges = []
        for i in range(2, n + 1):
            p = random.randint(1, i - 1)
            edges.append(f"{p} {i}")
        return f"{n}\n" + "\n".join(edges) + "\n"


def find_counterexample(
    user_code: str,
    user_lang: LanguageType,
    reference_code: str,
    reference_lang: LanguageType = "cpp",
    input_generator: Callable[[], str] | None = None,
    max_trials: int = 30,
    config: ExecutionConfig | None = None
) -> FuzzResult:
    """Stress tests user code against a reference solution using random fuzzing.
    
    Returns:
        FuzzResult indicating whether a bug/counterexample was discovered.
    """
    cfg = config or ExecutionConfig(time_limit_ms=2000)
    gen = input_generator or InputGenerators.random_int_array

    with tempfile.TemporaryDirectory(prefix="fuzz_user_") as user_dir_str, \
         tempfile.TemporaryDirectory(prefix="fuzz_ref_") as ref_dir_str:
        
        user_dir = Path(user_dir_str)
        ref_dir = Path(ref_dir_str)

        # 1. Compile both solutions
        u_ok, u_cmd, u_err = compile_code(user_code, user_lang, user_dir)
        if not u_ok:
            return FuzzResult(
                counterexample_found=True,
                trials_run=0,
                user_verdict="CE",
                error_message=f"User compilation error: {u_err}"
            )

        r_ok, r_cmd, r_err = compile_code(reference_code, reference_lang, ref_dir)
        if not r_ok:
            return FuzzResult(
                counterexample_found=False,
                trials_run=0,
                error_message=f"Reference compilation error: {r_err}"
            )

        # 2. Run trials
        for trial in range(1, max_trials + 1):
            test_input = gen()

            # Execute Reference
            ref_res = run_isolated(r_cmd, input_data=test_input, config=cfg, cwd=ref_dir)
            if ref_res.verdict in ("TLE", "MLE", "RE"):
                continue  # Skip if generator created invalid input for reference

            # Execute User
            user_res = run_isolated(u_cmd, input_data=test_input, config=cfg, cwd=user_dir)

            if user_res.verdict in ("TLE", "MLE", "RE"):
                return FuzzResult(
                    counterexample_found=True,
                    trials_run=trial,
                    user_verdict=user_res.verdict,
                    failing_input=test_input,
                    expected_output=normalize_output(ref_res.stdout),
                    user_output=normalize_output(user_res.stdout),
                    error_message=user_res.error_message
                )

            norm_user = normalize_output(user_res.stdout)
            norm_ref = normalize_output(ref_res.stdout)

            if norm_user != norm_ref:
                return FuzzResult(
                    counterexample_found=True,
                    trials_run=trial,
                    user_verdict="WA",
                    failing_input=test_input,
                    expected_output=norm_ref,
                    user_output=norm_user,
                    error_message="Output mismatch on generated test case."
                )

        return FuzzResult(
            counterexample_found=False,
            trials_run=max_trials,
            user_verdict="AC",
            error_message=f"No counterexample found across {max_trials} randomized trials."
        )


def stress_test_problem_submission(
    contest_id: int,
    idx: str,
    user_code: str,
    user_lang: LanguageType,
    max_trials: int = 30,
    db_path: str | None = None
) -> FuzzResult:
    """Fetch reference solution from DB and stress test user code."""
    db = db_path or DEFAULT_DB_PATH
    ref_row = get_reference_solution(contest_id, idx, db_path=db)
    if not ref_row or not ref_row.get("solution_code"):
        return FuzzResult(
            counterexample_found=False,
            trials_run=0,
            error_message=f"No reference solution available in DB for {contest_id}{idx}."
        )

    ref_code = ref_row["solution_code"]
    # Infer reference language (default C++ if includes iostream/vector, else python)
    ref_lang = "cpp" if ("#include" in ref_code or "using namespace" in ref_code) else "python3"

    return find_counterexample(
        user_code=user_code,
        user_lang=user_lang,
        reference_code=ref_code,
        reference_lang=ref_lang,
        max_trials=max_trials
    )
