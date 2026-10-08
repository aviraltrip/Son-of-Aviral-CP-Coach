"""Integration tests for end-to-end submission flows in LangGraph state machine."""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.state import CoachState
from app.graph import create_coach_graph
from app.data.db import init_db, upsert_user

@pytest.fixture
def test_graph(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_graph_sub.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    init_db(db_file)
    upsert_user("tourist", 3800, 4000, db_path=db_file)
    
    checkpointer = MemorySaver()
    graph = create_coach_graph(checkpointer=checkpointer)
    return graph, {"configurable": {"thread_id": "test_sub_flow_thread"}}

def test_e2e_wrong_answer_triggers_targeted_hint(test_graph):
    """Verify that a Wrong Answer submission transitions to Tutor for a targeted diagnostic hint."""
    graph, config = test_graph
    
    # 1. Start Session
    initial_state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": None,
        "problem_statement": "",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": None,
        "last_submission_verdict": None,
    }
    graph.invoke(initial_state, config=config)
    
    state = graph.get_state(config)
    assert state.values.get("problem") is not None
    initial_problem = state.values["problem"]
    
    # 2. Submit Wrong Answer
    graph.update_state(config, {
        "user_action": "submitted",
        "last_submission_verdict": "WRONG_ANSWER"
    }, as_node="wait_for_user")
    graph.invoke(None, config=config)
    
    state_after_wa = graph.get_state(config)
    assert state_after_wa.values.get("last_submission_verdict") == "WRONG_ANSWER"
    assert state_after_wa.values.get("draft") is not None
    assert "Diagnostic Hint" in state_after_wa.values["draft"].text or "edge" in state_after_wa.values["draft"].text.lower()
    assert state_after_wa.values["problem"].contest_id == initial_problem.contest_id

def test_e2e_accepted_submission_advances_to_next_problem(test_graph):
    """Verify that an Accepted submission updates state and Analyst presents the next problem."""
    graph, config = test_graph
    
    # 1. Start Session
    initial_state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": None,
        "problem_statement": "",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": None,
        "last_submission_verdict": None,
    }
    graph.invoke(initial_state, config=config)
    
    state = graph.get_state(config)
    assert state.values.get("problem") is not None
    
    # 2. Submit AC
    graph.update_state(config, {
        "user_action": "submitted",
        "last_submission_verdict": "OK"
    }, as_node="wait_for_user")
    graph.invoke(None, config=config)
    
    state_after_ac = graph.get_state(config)
    # Analyst should have picked a problem and updated diagnosis
    assert state_after_ac.values.get("problem") is not None
    assert state_after_ac.values.get("diagnosis") is not None
    assert state_after_ac.values.get("draft") is None
