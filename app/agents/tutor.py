"""Tutor agent: drafts progressive hints strictly solution-blind using LLM prompts."""
import logging
from typing import Any

from app.state import CoachState, HintDraft
from app.prompts.tutor_prompt import TUTOR_SYSTEM_PROMPT, build_tutor_prompt
from app.prompts.targeted_hint_prompt import TARGETED_HINT_SYSTEM_PROMPT, build_targeted_hint_prompt
from app.agents.llm import get_llm

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
    "TIME_LIMIT_EXCEEDED": (
        "Diagnostic Hint: Your solution might be recomputing subtree values repeatedly. "
        "Aim for a single tree traversal (DFS) that computes the answer in O(N) time."
    ),
    "MEMORY_LIMIT_EXCEEDED": (
        "Diagnostic Hint: Deep tree recursion might cause stack overflow. "
        "Ensure vectors/lists are passed by reference and memory is allocated linearly."
    )
}

def draft_targeted_hint(verdict: str, state: CoachState | None = None) -> HintDraft:
    """Draft a targeted hint addressing a specific submission failure verdict."""
    text = TARGETED_DIAGNOSTICS.get(
        verdict,
        f"Diagnostic Hint: Submission received verdict {verdict}. Review base cases and edge conditions."
    )
    return HintDraft(level=1, text=text)

def tutor_node(state: CoachState) -> dict[str, Any]:
    """Draft a hint according to requested level, feedback, or submission errors."""
    level = state.get("hint_level", 1)
    revisions = state.get("revisions", 0)
    verdict = state.get("verdict")
    last_sub = state.get("last_submission_verdict")
    user_action = state.get("user_action")
    problem_stmt = state.get("problem_statement", "No problem statement provided.")
    history = state.get("history", [])

    llm = get_llm(model_type="tutor")

    try:
        if last_sub and last_sub != "OK" and user_action == "submitted":
            prompt = build_targeted_hint_prompt(problem_stmt, last_sub, history)
            resp = llm.invoke([{"role": "system", "content": TARGETED_HINT_SYSTEM_PROMPT}, {"role": "user", "content": prompt}])
            text = resp.content.strip() if hasattr(resp, "content") else str(resp)
        else:
            keeper_feedback = verdict.reason if (verdict and not verdict.approved) else None
            prompt = build_tutor_prompt(problem_stmt, level, history, keeper_feedback=keeper_feedback)
            resp = llm.invoke([{"role": "system", "content": TUTOR_SYSTEM_PROMPT}, {"role": "user", "content": prompt}])
            text = resp.content.strip() if hasattr(resp, "content") else str(resp)
    except Exception as e:
        logger.warning(f"Tutor LLM invocation failed: {e}. Utilizing fallback rubric.")
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
