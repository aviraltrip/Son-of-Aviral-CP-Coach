"""Tutor agent: drafts progressive hints strictly solution-blind using LLM prompts."""
import os
import logging
from typing import Any

from app.state import CoachState, HintDraft
from app.prompts.tutor_prompt import TUTOR_SYSTEM_PROMPT, build_tutor_prompt
from app.prompts.targeted_hint_prompt import TARGETED_HINT_SYSTEM_PROMPT, build_targeted_hint_prompt
from app.agents.llm import get_llm
from app.data.db import get_cached_hint
from app.config import settings

logger = logging.getLogger(__name__)

FALLBACK_HINTS = {
    1: "Think about the problem constraints and what each state represents. Try writing out small test cases on paper.",
    2: "Break down the subproblems: what information is required at each step to make an optimal local decision?",
    3: "Maintain a recursive state dp[u] representing minimum operations for the subtree rooted at u."
}

TARGETED_DIAGNOSTICS = {
    "WRONG_ANSWER": (
        "Diagnostic Hint: Your logic may miss key edge cases. "
        "Check: 1) What if the root is already a leaf? 2) Are single-child nodes handled correctly? "
        "3) Did you account for direction changes properly ('L' vs 'R')?"
    ),
    "WA": (
        "Diagnostic Hint: Your solution produces a Wrong Answer on a test case. "
        "Check boundary conditions, zero values, off-by-one loops, and 64-bit integer overflow."
    ),
    "TIME_LIMIT_EXCEEDED": (
        "Diagnostic Hint: Your solution might be recomputing subtree values repeatedly. "
        "Aim for a single tree traversal (DFS) that computes the answer in O(N) time."
    ),
    "TLE": (
        "Diagnostic Hint: Time Limit Exceeded. Review your time complexity. "
        "Ensure your algorithm runs within O(N log N) or O(N) and avoid nested quadratic loops."
    ),
    "MEMORY_LIMIT_EXCEEDED": (
        "Diagnostic Hint: Deep tree recursion or large allocations might exceed memory limits. "
        "Ensure vectors/lists are passed by reference and memory is allocated linearly."
    ),
    "MLE": (
        "Diagnostic Hint: Memory Limit Exceeded. Check for memory leaks or excessive dynamic array allocations."
    ),
    "COMPILATION_ERROR": (
        "Diagnostic Hint: Compilation failed. Check syntax, headers, type conversions, and semicolons."
    ),
    "CE": (
        "Diagnostic Hint: Compilation Error. Inspect compiler error messages for missing declarations or typos."
    ),
    "RUNTIME_ERROR": (
        "Diagnostic Hint: Runtime Crash (SIGSEGV/RE). Check for out-of-bounds array access, null pointer dereference, or division by zero."
    ),
    "RE": (
        "Diagnostic Hint: Runtime Error. Verify array indexing bounds, stack depth recursion limits, and non-zero divisors."
    )
}

def draft_targeted_hint(verdict: str, state: CoachState | None = None) -> HintDraft:
    """Draft a targeted hint addressing a specific submission failure verdict."""
    text = TARGETED_DIAGNOSTICS.get(
        verdict,
        f"Diagnostic Hint: Submission received verdict {verdict}. Review base cases, edge constraints, and array indexing."
    )
    return HintDraft(level=1, text=text)

def extract_text(resp: Any) -> str:
    if hasattr(resp, "content"):
        c = resp.content
        if isinstance(c, list):
            return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c).strip()
        return str(c).strip()
    return str(resp).strip()

def tutor_node(state: CoachState) -> dict[str, Any]:
    """Draft a hint according to requested level, feedback, or submission errors."""
    level = state.get("hint_level", 1)
    revisions = state.get("revisions", 0)
    verdict = state.get("verdict")
    last_sub = state.get("last_submission_verdict")
    user_action = state.get("user_action")
    problem = state.get("problem")
    problem_stmt = state.get("problem_statement", "No problem statement provided.")
    history = state.get("history", [])
    db_path = os.getenv("DATABASE_PATH", settings.database_path)

    if revisions == 0 and not (last_sub and last_sub not in ("OK", "AC") and user_action in ("submitted", "submit_code", "judge")):
        if problem:
            cached_text = get_cached_hint(problem.contest_id, problem.index, level, db_path=db_path)
            if cached_text:
                logger.info(f"[Tutor] Serving approved hint from SQLite cache for Problem {problem.contest_id}{problem.index} Level {level}")
                draft = HintDraft(level=level, text=cached_text)
                new_history = list(history)
                new_history.append({
                    "role": "assistant",
                    "type": "draft",
                    "level": level,
                    "text": cached_text,
                    "revision": 0
                })
                return {"draft": draft, "history": new_history}

    llm = get_llm(model_type="tutor")

    try:
        if last_sub and last_sub not in ("OK", "AC") and user_action in ("submitted", "submit_code", "judge"):
            prompt = build_targeted_hint_prompt(problem_stmt, last_sub, history)
            resp = llm.invoke([{"role": "system", "content": TARGETED_HINT_SYSTEM_PROMPT}, {"role": "user", "content": prompt}])
            text = extract_text(resp)
        else:
            keeper_feedback = verdict.reason if (verdict and not verdict.approved) else None
            prompt = build_tutor_prompt(problem_stmt, level, history, keeper_feedback=keeper_feedback)
            resp = llm.invoke([{"role": "system", "content": TUTOR_SYSTEM_PROMPT}, {"role": "user", "content": prompt}])
            text = extract_text(resp)
    except Exception as e:
        logger.warning(f"Tutor LLM invocation failed: {e}. Utilizing fallback rubric.")
        if last_sub and last_sub not in ("OK", "AC"):
            text = draft_targeted_hint(last_sub).text
        else:
            text = FALLBACK_HINTS.get(level, FALLBACK_HINTS[1])

    draft = HintDraft(level=level, text=text)
    
    new_history = list(history)
    new_history.append({
        "role": "assistant",
        "type": "draft",
        "level": level,
        "text": text,
        "revision": revisions
    })
    
    return {
        "draft": draft,
        "history": new_history
    }
