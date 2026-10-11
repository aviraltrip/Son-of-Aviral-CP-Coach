"""Integration tests for LangGraph state machine recovery with persistent SqliteSaver."""
import os
import pytest
from app.graph import create_coach_graph, get_checkpointer

def test_graph_session_state_survives_restart(tmp_path):
    """Verify that graph execution state persists to SQLite and survives engine re-instantiation."""
    checkpoints_db = str(tmp_path / "test_checkpoints.db")
    thread_id = "persistent_user_session_42"
    config = {"configurable": {"thread_id": thread_id}}

    checkpointer_1 = get_checkpointer(persisted=True, db_path=checkpoints_db)
    graph_1 = create_coach_graph(checkpointer=checkpointer_1)

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

    events = list(graph_1.stream(initial_state, config=config))
    state_1 = graph_1.get_state(config)

    assert state_1.next == ("wait_for_user",)
    assert state_1.values["diagnosis"] is not None
    saved_problem = state_1.values["problem"]
    assert saved_problem is not None

    assert os.path.exists(checkpoints_db)

    checkpointer_2 = get_checkpointer(persisted=True, db_path=checkpoints_db)
    graph_2 = create_coach_graph(checkpointer=checkpointer_2)

    state_2 = graph_2.get_state(config)
    assert state_2.next == ("wait_for_user",)
    assert state_2.values["diagnosis"].summary == state_1.values["diagnosis"].summary
    assert state_2.values["problem"].contest_id == saved_problem.contest_id
    assert state_2.values["problem"].index == saved_problem.index

    graph_2.update_state(config, {
        "user_action": "request_hint",
        "hint_level": 1
    }, as_node="wait_for_user")
    graph_2.invoke(None, config=config)

    resumed_state = graph_2.get_state(config)
    assert resumed_state.values["draft"] is not None
    assert resumed_state.values["verdict"] is not None
