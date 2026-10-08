"""Tutor agent stub: drafts progressive hints blind to the reference solution."""
from typing import Any
from app.state import CoachState, HintDraft

FALLBACK_HINTS = {
    1: "Think about the problem constraints and what each state or choice represents. Write down a few small cases on paper.",
    2: "Break down the subproblems: what information do you need at each node or step to make an optimal local decision?",
    3: "Maintain a recursive state dp[u] representing the minimum changes needed in the subtree rooted at u, then transition based on whether u has left or right children."
}

def tutor_node(state: CoachState) -> dict[str, Any]:
    """Draft a hint according to the requested hint level and previous feedback."""
    level = state.get("hint_level", 1)
    revisions = state.get("revisions", 0)
    verdict = state.get("verdict")
    
    # Phase 1 stubbed draft logic
    if verdict and not verdict.approved:
        # If revising after keeper rejection, produce a more conservative hint
        text = f"[Revision {revisions}] {FALLBACK_HINTS.get(level, FALLBACK_HINTS[1])}"
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
