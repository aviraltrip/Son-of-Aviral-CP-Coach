"""Unit and integration tests for Tutor and Keeper nodes."""
from app.state import CoachState, HintDraft, ProblemChoice
from app.agents.tutor import tutor_node
from app.agents.keeper import keeper_node, parse_keeper_verdict

def test_parse_keeper_verdict():
    raw_json = '{"approved": true, "reason": "Looks good", "leak_severity": "none"}'
    v = parse_keeper_verdict(raw_json, 1)
    assert v.approved is True
    assert v.reason == "Looks good"
    assert v.leak_severity == "none"

def test_tutor_node_llm_flow():
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": ProblemChoice(contest_id=1900, index="C", name="Tree", rating=1500, tags=["dp"], reason="weak area"),
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "request_hint",
        "last_submission_verdict": None
    }
    res = tutor_node(state)
    assert res["draft"] is not None
    assert len(res["draft"].text) > 0

def test_keeper_node_audit_flow(tmp_path, monkeypatch):
    db_file = str(tmp_path / "keeper_test.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": ProblemChoice(contest_id=1900, index="C", name="Tree", rating=1500, tags=["dp"], reason="weak area"),
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": HintDraft(level=1, text="Look for the monotonic property"),
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "request_hint",
        "last_submission_verdict": None
    }
    
    res = keeper_node(state)
    assert res["verdict"] is not None
    assert res["verdict"].approved is True
