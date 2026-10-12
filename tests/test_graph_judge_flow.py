"""End-to-End Integration tests for Sandbox Judge LangGraph flow (Phase 8.3)."""
import pytest
from app.graph import create_coach_graph, get_checkpointer
from app.state import CoachState, ProblemChoice, CodeSubmission
from app.data.db import init_db, upsert_user, upsert_problems, upsert_test_case
from app.agents.judge import judge_node

@pytest.fixture
def judge_graph_setup(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_judge_graph.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    init_db(db_file)
    upsert_user("tourist", 1500, 1600, db_path=db_file)
    upsert_problems([{"contestId": 9999, "index": "C", "name": "Problem C", "rating": 1200, "tags": ["dp"]}], db_path=db_file)
    upsert_test_case(9999, "C", 1, "5\n", "10\n", is_sample=True, db_path=db_file)

    checkpointer = get_checkpointer()
    graph = create_coach_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "test_judge_flow_thread"}}
    return graph, config, db_file

def test_judge_node_accepted_python(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_judge_ac.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    init_db(db_file)
    upsert_problems([{"contestId": 9999, "index": "A", "name": "Sum Two", "rating": 800, "tags": ["math"]}], db_path=db_file)
    upsert_test_case(9999, "A", 1, "4 5\n", "9\n", is_sample=True, db_path=db_file)
    upsert_test_case(9999, "A", 2, "10 20\n", "30\n", is_sample=False, db_path=db_file)

    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": ProblemChoice(contest_id=9999, index="A", name="Sum Two", rating=800, tags=["math"], reason="Practice"),
        "problem_statement": "Given two integers a and b, print a + b.",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "submit_code",
        "last_submission_verdict": None,
        "submission_code": CodeSubmission(
            language="python3",
            source_code="import sys\ndata = sys.stdin.read().split()\nif data:\n    print(int(data[0]) + int(data[1]))\n"
        ),
        "judge_verdict": None
    }

    res = judge_node(state)

    assert res["judge_verdict"].status == "AC"
    assert res["judge_verdict"].passed_count == 2
    assert res["last_submission_verdict"] == "AC"

    from app.data.db import get_user_submissions
    subs = get_user_submissions("tourist", db_path=db_file)
    assert len(subs) == 1
    assert subs[0]["verdict"] == "OK"

def test_judge_node_wrong_answer_python(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_judge_wa.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    init_db(db_file)
    upsert_problems([{"contestId": 9999, "index": "B", "name": "Mul Two", "rating": 800, "tags": ["math"]}], db_path=db_file)
    upsert_test_case(9999, "B", 1, "4 5\n", "20\n", is_sample=True, db_path=db_file)

    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": ProblemChoice(contest_id=9999, index="B", name="Mul Two", rating=800, tags=["math"], reason="Practice"),
        "problem_statement": "Given two integers a and b, print a * b.",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "submit_code",
        "last_submission_verdict": None,
        "submission_code": CodeSubmission(
            language="python3",
            source_code="print(999)\n"
        ),
        "judge_verdict": None
    }

    res = judge_node(state)

    assert res["judge_verdict"].status == "WA"
    assert res["judge_verdict"].failing_test_index == 1
    assert res["last_submission_verdict"] == "WA"

def test_graph_flow_judge_wrong_answer_to_tutor(judge_graph_setup):
    """Verify that submitting WA code via graph routes to Judge -> Tutor targeted hint -> Keeper."""
    graph, config, db_file = judge_graph_setup

    graph.invoke({"handle": "tourist", "history": []}, config=config)

    state = graph.get_state(config)
    assert state.values.get("problem") is not None

    bad_code = CodeSubmission(language="python3", source_code="print(999999999)\n")
    graph.update_state(
        config,
        {
            "user_action": "submit_code",
            "submission_code": bad_code
        },
        as_node="wait_for_user"
    )

    graph.invoke(None, config=config)
    after_sub = graph.get_state(config)

    assert after_sub.values.get("judge_verdict") is not None
    assert after_sub.values["judge_verdict"].status == "WA"
    assert after_sub.values.get("draft") is not None
    assert after_sub.values.get("verdict") is not None
    assert after_sub.values["verdict"].approved is True
