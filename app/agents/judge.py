"""Sandbox Judge Node for LangGraph State Machine (Phase 8.3).

Executes user code against test cases in an isolated sandbox, determines verdicts
(AC, WA, TLE, MLE, CE, RE), records outcomes, and populates JudgeVerdict state.
"""
import os
import time
import logging
import tempfile
from pathlib import Path
from typing import Any

from app.state import CoachState, CodeSubmission, JudgeVerdict, TestCaseResult
from app.judge.runner import (
    ExecutionConfig,
    compile_code,
    run_isolated,
    normalize_output
)
from app.data.db import (
    get_problem_test_cases,
    seed_dataset_test_cases,
    record_problem_submission,
    DEFAULT_DB_PATH
)

logger = logging.getLogger(__name__)

def judge_node(state: CoachState) -> dict[str, Any]:
    """LangGraph node executing submitted user code against problem test cases."""
    problem = state.get("problem")
    sub_code: CodeSubmission | dict[str, Any] | None = state.get("submission_code")
    handle = state.get("handle", "anonymous")
    history = list(state.get("history", []))

    if not problem:
        logger.warning("No active problem found in state for judge_node.")
        return {
            "judge_verdict": JudgeVerdict(status="UNKNOWN", compiler_output="No active problem selected."),
            "last_submission_verdict": "UNKNOWN"
        }

    contest_id = problem.contest_id if hasattr(problem, "contest_id") else problem.get("contest_id")
    idx = problem.index if hasattr(problem, "index") else (problem.get("index") or problem.get("idx"))

    if not sub_code:
        logger.warning("No code submission present in state.")
        return {
            "judge_verdict": JudgeVerdict(status="UNKNOWN", compiler_output="No code submission provided."),
            "last_submission_verdict": "UNKNOWN"
        }

    if isinstance(sub_code, dict):
        source = sub_code.get("source_code", "")
        lang = sub_code.get("language", "cpp")
    else:
        source = sub_code.source_code
        lang = sub_code.language

    db_path = os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)

    test_cases = get_problem_test_cases(contest_id, idx, db_path=db_path)
    if not test_cases:
        seed_dataset_test_cases(db_path=db_path)
        test_cases = get_problem_test_cases(contest_id, idx, db_path=db_path)

    if not test_cases:
        test_cases = [{
            "contest_id": contest_id,
            "idx": idx,
            "test_index": 1,
            "input_data": "1\n",
            "expected_output": "1\n",
            "is_sample": 1
        }]

    config = ExecutionConfig(time_limit_ms=2000, memory_limit_mb=256)
    detailed_results: list[TestCaseResult] = []
    total_time_ms = 0.0
    max_memory_bytes = 0
    overall_status = "AC"
    failing_case_idx: int | None = None
    failing_case_result: TestCaseResult | None = None

    with tempfile.TemporaryDirectory(prefix=f"judge_{contest_id}{idx}_") as temp_dir_str:
        work_dir = Path(temp_dir_str)

        success, cmd, comp_err = compile_code(source, lang, work_dir)
        if not success:
            verdict = JudgeVerdict(
                status="CE",
                passed_count=0,
                total_count=len(test_cases),
                compiler_output=comp_err or "Compilation failed."
            )
            record_problem_submission(
                handle=handle,
                contest_id=contest_id,
                idx=idx,
                verdict="COMPILATION_ERROR",
                programming_language=lang,
                db_path=db_path
            )
            history.append({
                "role": "assistant",
                "content": f"**Sandbox Judge Verdict**: Compilation Error (CE)\n```\n{comp_err}\n```",
                "timestamp": time.time()
            })
            return {
                "judge_verdict": verdict,
                "last_submission_verdict": "CE",
                "history": history
            }

        for tc in test_cases:
            t_idx = tc.get("test_index", len(detailed_results) + 1)
            inp = tc.get("input_data", "")
            exp = tc.get("expected_output", "")

            exec_res = run_isolated(cmd, input_data=inp, config=config, cwd=work_dir)
            total_time_ms = max(total_time_ms, exec_res.time_ms)
            max_memory_bytes = max(max_memory_bytes, int(exec_res.memory_kb * 1024))

            norm_user = normalize_output(exec_res.stdout)
            norm_exp = normalize_output(exp)

            if exec_res.verdict == "TLE":
                t_verdict = "TLE"
                err_msg = f"Time Limit Exceeded (> {config.time_limit_ms}ms)"
            elif exec_res.verdict == "RE":
                t_verdict = "RE"
                err_msg = exec_res.error_message or f"Runtime error: {exec_res.stderr}"
            elif norm_user == norm_exp:
                t_verdict = "AC"
                err_msg = ""
            else:
                t_verdict = "WA"
                err_msg = f"Output mismatch on test {t_idx}."

            res_item = TestCaseResult(
                test_index=t_idx,
                verdict=t_verdict,
                time_ms=exec_res.time_ms,
                memory_kb=exec_res.memory_kb,
                input_snippet=inp[:100] + ("..." if len(inp) > 100 else ""),
                user_output=norm_user[:200],
                expected_output=norm_exp[:200],
                error_message=err_msg
            )
            detailed_results.append(res_item)

            if t_verdict != "AC" and overall_status == "AC":
                overall_status = t_verdict
                failing_case_idx = t_idx
                failing_case_result = res_item

    passed_count = sum(1 for r in detailed_results if r.verdict == "AC")
    verdict = JudgeVerdict(
        status=overall_status,
        passed_count=passed_count,
        total_count=len(detailed_results),
        time_consumed_ms=round(total_time_ms, 2),
        memory_consumed_bytes=max_memory_bytes,
        failing_test_index=failing_case_idx,
        failing_test_result=failing_case_result,
        detailed_results=detailed_results
    )

    cf_verdict_map = {
        "AC": "OK",
        "WA": "WRONG_ANSWER",
        "TLE": "TIME_LIMIT_EXCEEDED",
        "MLE": "MEMORY_LIMIT_EXCEEDED",
        "RE": "RUNTIME_ERROR",
        "CE": "COMPILATION_ERROR"
    }
    record_problem_submission(
        handle=handle,
        contest_id=contest_id,
        idx=idx,
        verdict=cf_verdict_map.get(overall_status, "WRONG_ANSWER"),
        programming_language=lang,
        pass_count=passed_count,
        time_consumed_ms=int(total_time_ms),
        memory_consumed_bytes=max_memory_bytes,
        db_path=db_path
    )

    if overall_status == "AC":
        msg_content = f"**Sandbox Judge Verdict**: Accepted! ({passed_count}/{len(detailed_results)} tests passed in {total_time_ms:.1f}ms)"
    else:
        msg_content = (
            f"**Sandbox Judge Verdict**: {overall_status} on Test {failing_case_idx} "
            f"({passed_count}/{len(detailed_results)} passed)"
        )
    history.append({
        "role": "assistant",
        "content": msg_content,
        "timestamp": time.time()
    })

    return {
        "judge_verdict": verdict,
        "last_submission_verdict": overall_status,
        "history": history
    }
