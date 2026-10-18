"""Integration tests for Analyst agent node with SQLite data layer."""
import pytest
from unittest.mock import patch
from app.state import CoachState
from app.agents.analyst import analyst_node
from app.data.db import init_db, upsert_user, upsert_submissions, upsert_problems

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "analyst_test.db")
    init_db(db_file)
    monkeypatch.setenv("DATABASE_PATH", db_file)
    return db_file

@patch("app.agents.analyst.sync_user_data")
def test_analyst_node_execution(mock_sync, isolated_db):
    mock_sync.return_value = ({"rating": 1500, "maxRating": 1600}, 2)
    
    upsert_user("tourist", 1500, 1600, db_path=isolated_db)
    upsert_problems([
        {"contestId": 1800, "index": "C", "name": "Tree Problem", "rating": 1650, "tags": ["trees", "dp"]},
    ], db_path=isolated_db)
    upsert_submissions("tourist", [
        {
            "id": 9991,
            "problem": {"contestId": 1700, "index": "A", "name": "DP Fail", "rating": 1500, "tags": ["dp"]},
            "verdict": "WRONG_ANSWER",
            "creationTimeSeconds": 1700000000
        },
        {
            "id": 9992,
            "problem": {"contestId": 1700, "index": "B", "name": "DP Fail 2", "rating": 1500, "tags": ["dp"]},
            "verdict": "WRONG_ANSWER",
            "creationTimeSeconds": 1700000100
        }
    ], db_path=isolated_db)
    
    state: CoachState = {
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
        "last_submission_verdict": None
    }
    
    result = analyst_node(state)
    assert result["diagnosis"] is not None
    assert len(result["diagnosis"].weak_topics) > 0
    assert result["diagnosis"].weak_topics[0].tag == "dp"
    assert result["problem"] is not None
