"""Unit tests for SQLite database operations in app/data/db.py."""
import pytest
from app.data.db import (
    init_db,
    upsert_user,
    get_user,
    upsert_problems,
    get_problem,
    get_candidate_problems,
    upsert_submissions,
    get_user_submissions,
    get_attempted_problem_keys,
    save_topic_stats,
    get_user_topic_stats,
    save_reference_solution,
    get_reference_solution,
    create_session,
    update_session_outcome
)

@pytest.fixture
def temp_db(tmp_path):
    """Create an isolated temporary SQLite database for testing."""
    db_file = str(tmp_path / "test_cp_coach.db")
    init_db(db_file)
    return db_file

def test_user_crud(temp_db):
    upsert_user("Tourist", 3800, 3900, db_path=temp_db)
    user = get_user("tourist", db_path=temp_db)
    assert user is not None
    assert user["handle"] == "tourist"
    assert user["current_rating"] == 3800
    assert user["max_rating"] == 3900

def test_problem_crud(temp_db):
    problems = [
        {"contestId": 1900, "index": "A", "name": "Cover in Water", "rating": 800, "tags": ["greedy", "implementation"]},
        {"contestId": 1900, "index": "C", "name": "Anji's Binary Tree", "rating": 1500, "tags": ["dp", "trees"]},
    ]
    inserted = upsert_problems(problems, db_path=temp_db)
    assert inserted == 2
    
    p = get_problem(1900, "C", db_path=temp_db)
    assert p is not None
    assert p["name"] == "Anji's Binary Tree"
    assert "dp" in p["tags"]

    candidates = get_candidate_problems(1400, 1600, tags=["trees"], db_path=temp_db)
    assert len(candidates) == 1
    assert candidates[0]["idx"] == "C"

def test_submission_and_attempted_keys(temp_db):
    upsert_user("tourist", 3800, 3900, db_path=temp_db)
    subs = [
        {
            "id": 1001,
            "problem": {"contestId": 1900, "index": "A", "name": "Cover in Water", "rating": 800, "tags": ["greedy"]},
            "verdict": "OK",
            "programmingLanguage": "GNU C++20",
            "creationTimeSeconds": 1700000000
        },
        {
            "id": 1002,
            "problem": {"contestId": 1900, "index": "C", "name": "Anji's Binary Tree", "rating": 1500, "tags": ["dp", "trees"]},
            "verdict": "WRONG_ANSWER",
            "programmingLanguage": "GNU C++20",
            "creationTimeSeconds": 1700000100
        }
    ]
    upsert_submissions("tourist", subs, db_path=temp_db)
    user_subs = get_user_submissions("tourist", db_path=temp_db)
    assert len(user_subs) == 2
    
    attempted = get_attempted_problem_keys("tourist", db_path=temp_db)
    assert (1900, "A") in attempted
    assert (1900, "C") in attempted
    assert (1900, "B") not in attempted

def test_topic_stats_and_references(temp_db):
    upsert_user("tourist", 3800, 3900, db_path=temp_db)
    stats = [
        {"tag": "dp", "total_attempts": 10, "total_accepted": 3, "weighted_failure_score": 0.70, "avg_rating_solved": 1550.0},
        {"tag": "greedy", "total_attempts": 20, "total_accepted": 18, "weighted_failure_score": 0.10, "avg_rating_solved": 1200.0},
    ]
    save_topic_stats("tourist", stats, db_path=temp_db)
    saved = get_user_topic_stats("tourist", db_path=temp_db)
    assert len(saved) == 2
    assert saved[0]["tag"] == "dp"
    assert saved[0]["weighted_failure_score"] == 0.70

    save_reference_solution(1900, "C", "int main() { return 0; }", "Editorial explanation", db_path=temp_db)
    ref = get_reference_solution(1900, "C", db_path=temp_db)
    assert ref is not None
    assert "return 0;" in ref["solution_code"]

def test_session_lifecycle(temp_db):
    upsert_user("tourist", 3800, 3900, db_path=temp_db)
    upsert_problems([{"contestId": 1900, "index": "C", "name": "Tree", "rating": 1500, "tags": []}], db_path=temp_db)
    create_session("sess_123", "tourist", 1900, "C", db_path=temp_db)
    update_session_outcome("sess_123", "SOLVED", hints_requested=2, keeper_rejections=0, db_path=temp_db)

def test_test_cases_crud(temp_db):
    from app.data.db import upsert_test_case, upsert_test_cases_batch, get_problem_test_cases
    upsert_problems([{"contestId": 1900, "index": "A", "name": "Problem A", "rating": 1000, "tags": []}], db_path=temp_db)
    
    upsert_test_case(1900, "A", 1, "5\n1 2 3 4 5\n", "15\n", is_sample=True, db_path=temp_db)
    upsert_test_case(1900, "A", 2, "2\n10 20\n", "30\n", is_sample=False, db_path=temp_db)
    
    all_tests = get_problem_test_cases(1900, "A", samples_only=False, db_path=temp_db)
    assert len(all_tests) == 2
    assert all_tests[0]["test_index"] == 1
    assert all_tests[0]["is_sample"] == 1
    assert all_tests[0]["expected_output"] == "15\n"
    
    samples = get_problem_test_cases(1900, "A", samples_only=True, db_path=temp_db)
    assert len(samples) == 1
    assert samples[0]["test_index"] == 1

def test_cached_hints_crud(temp_db):
    from app.data.db import get_cached_hint, save_cached_hint
    upsert_problems([{"contestId": 1900, "index": "C", "name": "Tree DP", "rating": 1500, "tags": []}], db_path=temp_db)
    
    hint = get_cached_hint(1900, "C", 1, db_path=temp_db)
    assert hint is None
    
    save_cached_hint(1900, "C", 1, "Consider binary tree traversal invariants.", db_path=temp_db)
    hint = get_cached_hint(1900, "C", 1, db_path=temp_db)
    assert hint == "Consider binary tree traversal invariants."
    
    save_cached_hint(1900, "C", 1, "Updated Level 1 hint text.", db_path=temp_db)
    hint_updated = get_cached_hint(1900, "C", 1, db_path=temp_db)
    assert hint_updated == "Updated Level 1 hint text."

def test_database_indexes_created(temp_db):
    import sqlite3
    conn = sqlite3.connect(temp_db)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type = 'index';")
    indexes = {row[0] for row in cursor.fetchall()}
    conn.close()
    assert "idx_submissions_user_handle" in indexes
    assert "idx_submissions_problem" in indexes
    assert "idx_submissions_user_created" in indexes
    assert "idx_problems_rating" in indexes

