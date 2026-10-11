"""Stress testing database concurrency under multi-threaded loads with SQLite WAL mode."""
import time
import pytest
import concurrent.futures
from app.data.db import (
    init_db,
    upsert_user,
    get_user,
    record_problem_submission,
    get_user_submissions,
    check_db_health
)

@pytest.fixture
def concurrency_db(tmp_path):
    """Create isolated SQLite database for concurrent load testing."""
    db_file = str(tmp_path / "concurrent_coach.db")
    init_db(db_file)
    return db_file

def test_concurrent_user_and_submission_writes(concurrency_db):
    """Test that multiple worker threads can concurrently write without database locks."""
    num_threads = 10
    submissions_per_thread = 15

    def worker(thread_idx: int):
        handle = f"user_{thread_idx}"
        upsert_user(handle, 1200 + thread_idx * 10, 1400, db_path=concurrency_db)
        
        for sub_idx in range(submissions_per_thread):
            sub_id = thread_idx * 1000 + sub_idx + 1
            record_problem_submission(
                handle=handle,
                contest_id=1900,
                idx="A",
                verdict="OK" if sub_idx % 2 == 0 else "WRONG_ANSWER",
                sub_id=sub_id,
                creation_time_seconds=int(time.time()),
                db_path=concurrency_db
            )
        return handle

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        handles = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(handles) == num_threads

    for h in handles:
        u = get_user(h, db_path=concurrency_db)
        assert u is not None
        subs = get_user_submissions(h, limit=50, db_path=concurrency_db)
        assert len(subs) == submissions_per_thread

    health = check_db_health(concurrency_db)
    assert health["healthy"] is True
    assert health["journal_mode"].lower() == "wal"
