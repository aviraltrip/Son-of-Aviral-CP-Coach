"""Keeper agent stub: audits hint drafts against reference solution & rubric."""
from typing import Any
from app.state import CoachState, HintVerdict

SAFE_FALLBACK_HINT = (
    "Safe Guidance: Consider simplifying the problem constraints and simulating the process on a small example tree."
)

def keeper_node(state: CoachState) -> dict[str, Any]:
    """Audit the tutor's hint draft for leakage and rubric compliance."""
    draft = state.get("draft")
    revisions = state.get("revisions", 0)
    level = state.get("hint_level", 1)
    
    if not draft:
        return {
            "verdict": HintVerdict(approved=False, reason="No draft provided", leak_severity="minor"),
            "revisions": revisions + 1
        }
    
    # Simulate audit logic for Phase 1:
    # If the draft contains direct formula or keywords at Level 1, reject to test revision loop
    if level == 1 and "dp[" in draft.text:
        approved = False
        reason = "Level 1 hint leaked dynamic programming recurrence notation (dp[...])."
        severity = "major"
    else:
        approved = True
        reason = f"Hint adheres to Level {level} safety guidelines."
        severity = "none"
        
    verdict = HintVerdict(approved=approved, reason=reason, leak_severity=severity)
    
    new_revisions = revisions if approved else revisions + 1
    
    # If we hit max revisions (3), inject safe fallback
    updates: dict[str, Any] = {
        "verdict": verdict,
        "revisions": new_revisions
    }
    
    if not approved and new_revisions >= 3:
        # Fallback triggered
        draft.text = SAFE_FALLBACK_HINT
        verdict.approved = True
        verdict.reason = "Approved via Safe Generic Fallback (Max revisions reached)."
        updates["draft"] = draft
        updates["verdict"] = verdict
        
    return updates
