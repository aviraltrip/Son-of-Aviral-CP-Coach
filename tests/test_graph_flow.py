import uuid
from app.graph import create_coach_graph
from app.state import HintDraft
from app.agents.keeper import keeper_node, SAFE_FALLBACK_HINT

def test_graph_compilation():
    """Verify that the state graph compiles successfully."""
    graph = create_coach_graph()
    assert graph is not None

def test_initial_analyst_flow():
    """Verify that starting the graph runs Analyst and pauses at wait_for_user."""
    graph = create_coach_graph()
    config = {"configurable": {"thread_id": f"test_thread_1_{uuid.uuid4().hex[:8]}"}}
    
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
        "revisions": 2,
        "history": [],
        "user_action": None,
    }
    
    res = keeper_node(state)
    assert res["verdict"].approved is True
    assert "Approved via Safe Generic Fallback" in res["verdict"].reason
    assert res["draft"].text == SAFE_FALLBACK_HINT

def test_skip_problem_selects_new_problem():
    """Verify that updating state with user_action='skip' selects an alternative problem."""
    graph = create_coach_graph()
    config = {"configurable": {"thread_id": "test_thread_skip"}}
    
    initial_state = {
        "handle": "test_skip_user",
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
    
    graph.invoke(initial_state, config=config)
    state1 = graph.get_state(config)
    prob1 = state1.values["problem"]
    assert prob1 is not None

    graph.update_state(config, {"user_action": "skip"}, as_node="wait_for_user")
    graph.invoke(None, config=config)
    state2 = graph.get_state(config)
    prob2 = state2.values["problem"]
    assert prob2 is not None
    assert (prob1.contest_id, prob1.index) != (prob2.contest_id, prob2.index)

