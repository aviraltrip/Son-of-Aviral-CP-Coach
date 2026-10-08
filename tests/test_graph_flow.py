"""Tests for the LangGraph state machine flow and routing."""
import pytest
from app.graph import create_coach_graph
from app.state import HintDraft, HintVerdict
from app.agents.keeper import keeper_node, SAFE_FALLBACK_HINT

def test_graph_compilation():
    """Verify that the state graph compiles successfully."""
    graph = create_coach_graph()
    assert graph is not None

def test_initial_analyst_flow():
    """Verify that starting the graph runs Analyst and pauses at wait_for_user."""
    graph = create_coach_graph()
    config = {"configurable": {"thread_id": "test_thread_1"}}
    
    initial_state = {
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
    }
    
    events = list(graph.stream(initial_state, config=config))
    state = graph.get_state(config)
    
    assert state.next == ("wait_for_user",)
    assert state.values["diagnosis"] is not None
    assert state.values["problem"] is not None
    assert state.values["problem"].name == "Anji's Binary Tree"

def test_hint_request_flow():
    """Verify requesting a hint triggers Tutor ⇄ Keeper loop and pauses at wait_for_user."""
    graph = create_coach_graph()
    config = {"configurable": {"thread_id": "test_thread_2"}}
    
    # 1. Initialize
    graph.invoke({
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
    }, config=config)
    
    # 2. User requests Hint Level 1
    graph.update_state(config, {"user_action": "request_hint", "hint_level": 1}, as_node="wait_for_user")
    graph.invoke(None, config=config)
    
    state = graph.get_state(config)
    assert state.next == ("wait_for_user",)
    assert state.values["draft"] is not None
    assert state.values["verdict"] is not None
    assert state.values["verdict"].approved is True

def test_keeper_rejection_and_fallback():
    """Verify that keeper rejections increment revisions and trigger safe fallback on 3rd attempt."""
    state = {
        "handle": "test_user",
        "diagnosis": None,
        "problem": None,
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": HintDraft(level=1, text="Use dp[i][j] = min(...) to solve it"),
        "verdict": None,
        "revisions": 2, # 2 previous rejections, this is 3rd
        "history": [],
        "user_action": None,
    }
    
    res = keeper_node(state)
    assert res["verdict"].approved is True
    assert "Approved via Safe Generic Fallback" in res["verdict"].reason
    assert res["draft"].text == SAFE_FALLBACK_HINT
