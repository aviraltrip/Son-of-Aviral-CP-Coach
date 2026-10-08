"""Tutor agent stub: drafts progressive hints blind to the reference solution."""
from typing import Any
from app.state import CoachState, HintDraft

FALLBACK_HINTS = {
    1: "Think about the problem constraints and what each state or choice represents. Write down a few small cases on paper.",
    2: "Break down the subproblems: what information do you need at each node or step to make an optimal local decision?",
    3: "Maintain a recursive state dp[u] representing the minimum changes needed in the subtree rooted at u, then transition based on whether u has left or right children."
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

def draft_targeted_hint(verdict: str, state: CoachState) -> HintDraft:
    """Draft a targeted hint addressing a specific submission failure verdict."""
    text = TARGETED_DIAGNOSTICS.get(
        verdict,
        f"Diagnostic Hint: Submission received verdict {verdict}. Review base cases and edge conditions."
    )
    return HintDraft(level=1, text=text)

def tutor_node(state: CoachState) -> dict[str, Any]:
    """Draft a hint according to the requested hint level, submission verdict, or feedback."""
    level = state.get("hint_level", 1)
    revisions = state.get("revisions", 0)
    verdict = state.get("verdict")
    last_sub = state.get("last_submission_verdict")
    
    # If the user failed a submission, generate targeted advice
    if last_sub and last_sub != "OK" and state.get("user_action") == "submitted":
        draft = draft_targeted_hint(last_sub, state)
        text = draft.text
    elif verdict and not verdict.approved:
        # If revising after keeper rejection, produce a more conservative hint
        text = f"[Revision {revisions}] {FALLBACK_HINTS.get(level, FALLBACK_HINTS[1])}"
        draft = HintDraft(level=level, text=text)
    else:
        if level == 1:
            text = "Notice that from any node, you want to reach any valid leaf with the minimum operations. What does the optimal path from root to leaf look like?"
        elif level == 2:
            text = "Consider defining a tree traversal (like DFS). At each vertex, calculate the cost of moving to the left child vs right child."
        else:
            text = "Let dp[u] be min modifications to reach a leaf from u. If u is a leaf, dp[u] = 0. Else dp[u] = min(dp[left] + (s[u]!='L'), dp[right] + (s[u]!='R'))."
        draft = HintDraft(level=level, text=text)

    # Update compact history
    history = list(state.get("history", []))
    history.append({
        "role": "assistant",
        "type": "draft",
        "level": level,
        "text": text,
        "revision": revisions
    })
    
    return {
        "draft": draft,
        "history": history
    }
