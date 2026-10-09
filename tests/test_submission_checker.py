"""Unit tests for Codeforces submission polling, check_submission node, and database logging."""
import pytest
from unittest.mock import patch

from app.state import CoachState, ProblemChoice
from app.data.cf_client import get_latest_problem_submission
from app.data.db import init_db, get_user_submissions, get_user_topic_stats, upsert_user
from app.graph import check_submission_node, route_submission

@pytest.fixture
def clean_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_submission.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    init_db(db_file)
    upsert_user("tourist", 3800, 4000, db_path=db_file)
    return db_file

def test_get_latest_problem_submission_found():
    """Verify that get_latest_problem_submission filters for matching contestId and index."""
    mock_submissions = [
        {"id": 101, "problem": {"contestId": 1900, "index": "A"}, "verdict": "WRONG_ANSWER"},
        {"id": 102, "problem": {"contestId": 1900, "index": "C"}, "verdict": "OK"},
        {"id": 100, "problem": {"contestId": 1800, "index": "B"}, "verdict": "OK"},
    ]
    with patch("app.data.cf_client.get_user_status", return_value=mock_submissions):
        sub = get_latest_problem_submission("tourist", 1900, "C", ttl_seconds=0)
        assert sub is not None
        assert sub["id"] == 102
        assert sub["verdict"] == "OK"

def test_get_latest_problem_submission_not_found():
    """Verify that get_latest_problem_submission returns None if no submission matches."""
    mock_submissions = [
        {"id": 101, "problem": {"contestId": 1900, "index": "A"}, "verdict": "OK"}
    ]
    with patch("app.data.cf_client.get_user_status", return_value=mock_submissions):
        sub = get_latest_problem_submission("tourist", 1900, "C", ttl_seconds=0)
        assert sub is None

def test_check_submission_node_accepted_flow(clean_db):
    """Verify that an OK verdict records submission, recomputes topic stats, and cleans active state."""
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": ProblemChoice(
            contest_id=1900,
            index="C",
            name="Anji's Binary Tree",
            rating=1500,
            tags=["dp", "trees"],
            reason="Practice"
        ),
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "submitted",
        "last_submission_verdict": "OK",
    }

    res = check_submission_node(state)
    assert res["last_submission_verdict"] == "OK"
    assert res["problem"] is None
    assert res["problem_statement"] == ""
    assert res["draft"] is None
    assert res["revisions"] == 0

    subs = get_user_submissions("tourist", db_path=clean_db)
    assert len(subs) >= 1
    assert subs[0]["contest_id"] == 1900
    assert subs[0]["idx"] == "C"
    assert subs[0]["verdict"] == "OK"

def test_check_submission_node_wrong_answer_flow(clean_db):
    """Verify that a WRONG_ANSWER verdict logs attempt and prepares state for targeted hint."""
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": ProblemChoice(
            contest_id=1900,
            index="C",
            name="Anji's Binary Tree",
            rating=1500,
            tags=["dp", "trees"],
            reason="Practice"
        ),
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 1,
        "history": [],
        "user_action": "submitted",
        "last_submission_verdict": "WRONG_ANSWER",
    }

    res = check_submission_node(state)
    assert res["last_submission_verdict"] == "WRONG_ANSWER"
    assert res["draft"] is None
    assert res["revisions"] == 0

    subs = get_user_submissions("tourist", db_path=clean_db)
    assert len(subs) >= 1
    assert subs[0]["verdict"] == "WRONG_ANSWER"

def test_check_submission_node_live_cf_polling(clean_db):
    """Verify check_submission_node queries Codeforces API when verdict is not explicitly supplied."""
    state: CoachState = {
        "handle": "tourist",
        "diagnosis": None,
        "problem": ProblemChoice(
            contest_id=1900,
            index="C",
            name="Anji's Binary Tree",
            rating=1500,
            tags=["dp", "trees"],
            reason="Practice"
        ),
        "problem_statement": "Sample problem statement",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "submitted",
        "last_submission_verdict": None,
    }

    mock_sub = {
        "id": 99999,
        "problem": {"contestId": 1900, "index": "C"},
        "verdict": "TIME_LIMIT_EXCEEDED",
        "programmingLanguage": "GNU C++20",
        "creationTimeSeconds": 1700000000
    }
    with patch("app.graph.get_latest_problem_submission", return_value=mock_sub):
        res = check_submission_node(state)
        assert res["last_submission_verdict"] == "TIME_LIMIT_EXCEEDED"

def test_route_submission_branches():
    """Verify route_submission correctly directs AC to analyst, errors to tutor, and pending to wait_for_user."""
    assert route_submission({"last_submission_verdict": "OK"}) == "analyst"
    assert route_submission({"last_submission_verdict": "WRONG_ANSWER"}) == "tutor"
    assert route_submission({"last_submission_verdict": "TIME_LIMIT_EXCEEDED"}) == "tutor"
    assert route_submission({"last_submission_verdict": "MEMORY_LIMIT_EXCEEDED"}) == "tutor"
    assert route_submission({"last_submission_verdict": "NO_SUBMISSION_FOUND"}) == "wait_for_user"
    assert route_submission({"last_submission_verdict": "TESTING"}) == "wait_for_user"
