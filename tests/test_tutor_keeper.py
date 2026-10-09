"""Unit tests for Tutor ⇄ Keeper verification loop, hint escalation and targeted diagnostics."""
import pytest
from app.state import HintDraft, HintVerdict, CoachState
from app.agents.tutor import tutor_node, draft_targeted_hint
from app.agents.keeper import keeper_node, SAFE_FALLBACK_HINT

def test_progressive_hint_level_1():
    """Verify Level 1 hint does not contain code or recurrence formulas."""
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": None,
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "request_hint",
        "last_submission_verdict": None,
    }
    
    tutor_res = tutor_node(state)
    assert tutor_res["draft"] is not None
    assert tutor_res["draft"].level == 1
    assert "dp[" not in tutor_res["draft"].text
    
    # Keeper audit
    state["draft"] = tutor_res["draft"]
    keeper_res = keeper_node(state)
    assert keeper_res["verdict"].approved is True

def test_progressive_hint_level_3():
    """Verify Level 3 hint provides algorithmic recurrence/pseudocode."""
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": None,
        "problem_statement": "Sample problem statement",
        "hint_level": 3,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "request_hint",
        "last_submission_verdict": None,
    }
    
    tutor_res = tutor_node(state)
    assert tutor_res["draft"] is not None
    assert tutor_res["draft"].level == 3
    assert "dp[" in tutor_res["draft"].text

def test_targeted_hint_on_wrong_answer():
    """Verify tutor generates targeted diagnostic advice for Wrong Answer."""
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": None,
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "submitted",
        "last_submission_verdict": "WRONG_ANSWER",
    }
    
    res = tutor_node(state)
    assert "Diagnostic Hint" in res["draft"].text
    assert "edge cases" in res["draft"].text.lower() or "root" in res["draft"].text.lower()

def test_targeted_hint_on_time_limit():
    """Verify tutor generates targeted complexity advice for TLE."""
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": None,
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "submitted",
        "last_submission_verdict": "TIME_LIMIT_EXCEEDED",
    }
    
    res = tutor_node(state)
    assert "Diagnostic Hint" in res["draft"].text
    assert "O(N)" in res["draft"].text

def test_multi_round_revision_safety():
    """Verify that keeper rejections increment revision count and terminate with safe fallback."""
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": None,
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": HintDraft(level=1, text="Direct leak: dp[u] = min(left, right)"),
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "request_hint",
        "last_submission_verdict": None,
    }
    
    # Turn 1: Rejected
    r1 = keeper_node(state)
    assert r1["verdict"].approved is False
    assert r1["revisions"] == 1
    
    # Turn 2: Tutor revises
    state["revisions"] = r1["revisions"]
    state["verdict"] = r1["verdict"]
    tutor_r2 = tutor_node(state)
    assert "[Revision 1]" in tutor_r2["draft"].text
    
    # Turn 3: 3rd rejection triggers safe fallback
    state["revisions"] = 2
    state["draft"] = HintDraft(level=1, text="Another leak: dp[u] = ...")
    r3 = keeper_node(state)
    assert r3["verdict"].approved is True
    assert "Safe Generic Fallback" in r3["verdict"].reason
    assert r3["draft"].text == SAFE_FALLBACK_HINT

def test_keeper_dual_mode_heuristic_audit():
    """Verify Keeper operates in zero-shot heuristic mode when problem has no reference solution."""
    from app.state import ProblemChoice
    from app.prompts.keeper_prompt import build_heuristic_keeper_prompt
    
    prompt = build_heuristic_keeper_prompt("Sample Statement", 1, "Consider binary search on the answer range.")
    assert "Zero-Shot Heuristic Rubric Audit" in prompt
    assert "Level 1" in prompt
    
    # State with an unseen problem that has no reference in DB
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": ProblemChoice(contest_id=9999, index="Z", name="Unseen Problem", rating=1600, tags=["binary search"], reason="Targeted practice"),
        "problem_statement": "An unseen problem statement without database editorial.",
        "hint_level": 1,
        "draft": HintDraft(level=1, text="Consider whether the check function is monotonic across the search space."),
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "request_hint",
        "last_submission_verdict": None,
    }
    
    res = keeper_node(state)
    assert res["verdict"].approved is True
    assert res["verdict"].leak_severity == "none"
