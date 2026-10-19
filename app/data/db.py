"""SQLite database layer for CP Coach. Encapsulates all SQL access."""
import os
import sqlite3
import json
import time
from typing import Any, Generator
from contextlib import contextmanager

import logging
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", settings.database_path)

_INITIALIZED_DBS: set[str] = set()

def reset_db_initialization_cache() -> None:
    """Clear in-memory cache of initialized databases (used for testing)."""
    _INITIALIZED_DBS.clear()

def _create_raw_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
    except sqlite3.Error as e:
        logger.warning(f"Could not apply PRAGMA settings for {db_path}: {e}")
    return conn

def init_db(db_path: str = DEFAULT_DB_PATH, force: bool = False) -> None:
    """Initialize SQLite tables idempotently with one-time execution caching."""
    abs_path = os.path.abspath(db_path)
    if not force and abs_path in _INITIALIZED_DBS:
        return
    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    """Initialize SQLite tables idempotently."""
    conn = _create_raw_connection(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                handle TEXT PRIMARY KEY,
                current_rating INTEGER,
                max_rating INTEGER,
                last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS problems (
                contest_id INTEGER NOT NULL,
                idx TEXT NOT NULL,
                name TEXT NOT NULL,
                rating INTEGER,
                tags_json TEXT NOT NULL,
                PRIMARY KEY (contest_id, idx)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY,
                user_handle TEXT NOT NULL,
                contest_id INTEGER NOT NULL,
                idx TEXT NOT NULL,
                verdict TEXT NOT NULL,
                programming_language TEXT NOT NULL,
                pass_count INTEGER DEFAULT 0,
                time_consumed_ms INTEGER DEFAULT 0,
                memory_consumed_bytes INTEGER DEFAULT 0,
                creation_time_seconds INTEGER NOT NULL,
                FOREIGN KEY (user_handle) REFERENCES users(handle) ON DELETE CASCADE,
                FOREIGN KEY (contest_id, idx) REFERENCES problems(contest_id, idx) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topic_stats (
                user_handle TEXT NOT NULL,
                tag TEXT NOT NULL,
                total_attempts INTEGER DEFAULT 0,
                total_accepted INTEGER DEFAULT 0,
                weighted_failure_score REAL DEFAULT 0.0,
                avg_rating_solved REAL,
                last_attempt_ts INTEGER,
                PRIMARY KEY (user_handle, tag),
                FOREIGN KEY (user_handle) REFERENCES users(handle) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_handle TEXT NOT NULL,
                contest_id INTEGER NOT NULL,
                idx TEXT NOT NULL,
                hints_requested INTEGER DEFAULT 0,
                keeper_rejections INTEGER DEFAULT 0,
                final_outcome TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                FOREIGN KEY (user_handle) REFERENCES users(handle) ON DELETE CASCADE,
                FOREIGN KEY (contest_id, idx) REFERENCES problems(contest_id, idx) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS "references" (
                contest_id INTEGER NOT NULL,
                idx TEXT NOT NULL,
                solution_code TEXT,
                solution_editorial TEXT,
                source TEXT DEFAULT 'manual',
                PRIMARY KEY (contest_id, idx),
                FOREIGN KEY (contest_id, idx) REFERENCES problems(contest_id, idx) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_cases (
                contest_id INTEGER NOT NULL,
                idx TEXT NOT NULL,
                test_index INTEGER NOT NULL,
                input_data TEXT NOT NULL,
                expected_output TEXT NOT NULL,
                is_sample BOOLEAN DEFAULT 0,
                PRIMARY KEY (contest_id, idx, test_index),
                FOREIGN KEY (contest_id, idx) REFERENCES problems(contest_id, idx) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_hints (
                contest_id INTEGER NOT NULL,
                idx TEXT NOT NULL,
                hint_level INTEGER NOT NULL,
                hint_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (contest_id, idx, hint_level),
                FOREIGN KEY (contest_id, idx) REFERENCES problems(contest_id, idx) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_auth (
                handle TEXT PRIMARY KEY,
                salt TEXT NOT NULL,
                hashed_passkey TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_user_handle ON submissions(user_handle);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_problem ON submissions(contest_id, idx);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_user_created ON submissions(user_handle, creation_time_seconds DESC);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_problems_rating ON problems(rating);")
        conn.execute("DELETE FROM cached_hints WHERE hint_text LIKE '%what each state represents%' OR hint_text LIKE '%small test cases on paper%' OR hint_text LIKE '%Safe Guidance:%';")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    _INITIALIZED_DBS.add(abs_path)

@contextmanager
def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database connection with row factory, WAL, and transaction management."""
    abs_path = os.path.abspath(db_path)
    if abs_path not in _INITIALIZED_DBS:
        init_db(db_path)
    conn = _create_raw_connection(db_path)
    try:
        yield conn
        conn.commit()
    except sqlite3.OperationalError as e:
        conn.rollback()
        logger.error(f"SQLite operational error on {db_path}: {e}")
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction failed on {db_path}: {e}")
        raise
    finally:
        conn.close()

def upsert_user(handle: str, current_rating: int | None, max_rating: int | None, db_path: str = DEFAULT_DB_PATH) -> None:
    """Insert or update a Codeforces user record."""
    with get_db_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO users (handle, current_rating, max_rating, last_synced_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(handle) DO UPDATE SET
                current_rating = excluded.current_rating,
                max_rating = excluded.max_rating,
                last_synced_at = CURRENT_TIMESTAMP;
        """, (handle.lower(), current_rating, max_rating))

def get_user(handle: str, db_path: str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    """Retrieve user record by handle."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM users WHERE handle = ?;", (handle.lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def upsert_problems(problems_data: list[dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> int:
    """Batch insert or update problems in the catalog."""
    inserted = 0
    with get_db_connection(db_path) as conn:
        for p in problems_data:
            contest_id = p.get("contestId") or p.get("contest_id")
            idx = p.get("index") or p.get("idx")
            name = p.get("name")
            rating = p.get("rating")
            tags = p.get("tags", [])
            if contest_id and idx and name:
                tags_json = json.dumps(tags)
                conn.execute("""
                    INSERT INTO problems (contest_id, idx, name, rating, tags_json)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(contest_id, idx) DO UPDATE SET
                        name = excluded.name,
                        rating = excluded.rating,
                        tags_json = excluded.tags_json;
                """, (contest_id, idx, name, rating, tags_json))
                inserted += 1
    return inserted

def get_problem(contest_id: int, idx: str, db_path: str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    """Retrieve a single problem by contest ID and index."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM problems WHERE contest_id = ? AND idx = ?;", (contest_id, idx))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = json.loads(d["tags_json"])
        return d

def get_candidate_problems(min_rating: int, max_rating: int, tags: list[str] | None = None, limit: int = 100, db_path: str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    """Retrieve candidate practice problems within rating boundaries."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("""
            SELECT * FROM problems
            WHERE rating >= ? AND rating <= ?
            ORDER BY contest_id DESC
            LIMIT ?;
        """, (min_rating, max_rating, limit))
        results = []
        for row in cursor.fetchall():
            d = dict(row)
            d["tags"] = json.loads(d["tags_json"])
            if tags:
                if any(t in d["tags"] for t in tags):
                    results.append(d)
            else:
                results.append(d)
        return results

def upsert_submissions(user_handle: str, submissions_data: list[dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> int:
    """Batch upsert user submissions."""
    inserted = 0
    handle = user_handle.lower()
    with get_db_connection(db_path) as conn:
        for s in submissions_data:
            sub_id = s.get("id")
            problem = s.get("problem", {})
            contest_id = problem.get("contestId") or s.get("contest_id")
            idx = problem.get("index") or s.get("idx")
            verdict = s.get("verdict", "TESTING")
            lang = s.get("programmingLanguage", s.get("programming_language", "Unknown"))
            pass_count = s.get("passedTestCount", s.get("pass_count", 0))
            time_ms = s.get("timeConsumedMillis", s.get("time_consumed_ms", 0))
            mem_bytes = s.get("memoryConsumedBytes", s.get("memory_consumed_bytes", 0))
            ts = s.get("creationTimeSeconds", s.get("creation_time_seconds", int(time.time())))

            if sub_id and contest_id and idx:
                p_name = problem.get("name", f"Problem {contest_id}{idx}")
                p_rating = problem.get("rating")
                p_tags = json.dumps(problem.get("tags", []))
                conn.execute("""
                    INSERT INTO problems (contest_id, idx, name, rating, tags_json)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(contest_id, idx) DO NOTHING;
                """, (contest_id, idx, p_name, p_rating, p_tags))

                conn.execute("""
                    INSERT INTO submissions (id, user_handle, contest_id, idx, verdict, programming_language, pass_count, time_consumed_ms, memory_consumed_bytes, creation_time_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        verdict = excluded.verdict,
                        pass_count = excluded.pass_count,
                        time_consumed_ms = excluded.time_consumed_ms,
                        memory_consumed_bytes = excluded.memory_consumed_bytes;
                """, (sub_id, handle, contest_id, idx, verdict, lang, pass_count, time_ms, mem_bytes, ts))
                inserted += 1
    return inserted

def get_user_submissions(handle: str, limit: int = 1000, db_path: str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    """Retrieve submissions for a user ordered by creation time descending."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("""
            SELECT s.*, p.name as problem_name, p.rating as problem_rating, p.tags_json
            FROM submissions s
            JOIN problems p ON s.contest_id = p.contest_id AND s.idx = p.idx
            WHERE s.user_handle = ?
            ORDER BY s.creation_time_seconds DESC
            LIMIT ?;
        """, (handle.lower(), limit))
        results = []
        for row in cursor.fetchall():
            d = dict(row)
            d["tags"] = json.loads(d["tags_json"])
            results.append(d)
        return results

def get_attempted_problem_keys(handle: str, db_path: str = DEFAULT_DB_PATH) -> set[tuple[int, str]]:
    """Get all (contest_id, idx) pairs attempted by the user."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("""
            SELECT DISTINCT contest_id, idx FROM submissions
            WHERE user_handle = ?;
        """, (handle.lower(),))
        return {(row["contest_id"], row["idx"]) for row in cursor.fetchall()}

def save_topic_stats(handle: str, topic_stats_list: list[dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> None:
    """Save computed topic statistics for a user."""
    handle_clean = handle.lower()
    with get_db_connection(db_path) as conn:
        for stat in topic_stats_list:
            conn.execute("""
                INSERT INTO topic_stats (user_handle, tag, total_attempts, total_accepted, weighted_failure_score, avg_rating_solved, last_attempt_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_handle, tag) DO UPDATE SET
                    total_attempts = excluded.total_attempts,
                    total_accepted = excluded.total_accepted,
                    weighted_failure_score = excluded.weighted_failure_score,
                    avg_rating_solved = excluded.avg_rating_solved,
                    last_attempt_ts = excluded.last_attempt_ts;
            """, (
                handle_clean,
                stat.get("tag"),
                stat.get("total_attempts", stat.get("n_attempts", 0)),
                stat.get("total_accepted", 0),
                stat.get("weighted_failure_score", 0.0),
                stat.get("avg_rating_solved", stat.get("avg_rating")),
                stat.get("last_attempt_ts")
            ))

def get_user_topic_stats(handle: str, db_path: str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    """Retrieve saved topic statistics for a user ordered by failure score descending."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("""
            SELECT * FROM topic_stats
            WHERE user_handle = ?
            ORDER BY weighted_failure_score DESC;
        """, (handle.lower(),))
        return [dict(row) for row in cursor.fetchall()]

def save_reference_solution(contest_id: int, idx: str, solution_code: str, solution_editorial: str = "", source: str = "manual", db_path: str = DEFAULT_DB_PATH) -> None:
    """Save private reference solution for the Keeper agent."""
    with get_db_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO problems (contest_id, idx, name, rating, tags_json)
            VALUES (?, ?, ?, NULL, '[]')
            ON CONFLICT(contest_id, idx) DO NOTHING;
        """, (contest_id, idx, f"Problem {contest_id}{idx}"))
        conn.execute("""
            INSERT INTO "references" (contest_id, idx, solution_code, solution_editorial, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(contest_id, idx) DO UPDATE SET
                solution_code = excluded.solution_code,
                solution_editorial = excluded.solution_editorial,
                source = excluded.source;
        """, (contest_id, idx, solution_code, solution_editorial, source))

def get_reference_solution(contest_id: int, idx: str, db_path: str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    """Retrieve private reference solution. Strictly for Keeper Agent use only."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute('SELECT * FROM "references" WHERE contest_id = ? AND idx = ?;', (contest_id, idx))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_session(session_id: str, handle: str, contest_id: int, idx: str, db_path: str = DEFAULT_DB_PATH) -> None:
    """Create a new coaching session record."""
    with get_db_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO sessions (session_id, user_handle, contest_id, idx, hints_requested, keeper_rejections, started_at)
            VALUES (?, ?, ?, ?, 0, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO NOTHING;
        """, (session_id, handle.lower(), contest_id, idx))

def update_session_outcome(session_id: str, final_outcome: str, hints_requested: int = 0, keeper_rejections: int = 0, db_path: str = DEFAULT_DB_PATH) -> None:
    """Update coaching session outcome ('SOLVED', 'SKIPPED', 'ABANDONED')."""
    with get_db_connection(db_path) as conn:
        conn.execute("""
            UPDATE sessions
            SET final_outcome = ?,
                hints_requested = ?,
                keeper_rejections = ?,
                ended_at = CURRENT_TIMESTAMP
            WHERE session_id = ?;
        """, (final_outcome, hints_requested, keeper_rejections, session_id))

def get_session(session_id: str, db_path: str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    """Retrieve session record by session_id."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM sessions WHERE session_id = ?;", (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def record_problem_submission(
    handle: str,
    contest_id: int,
    idx: str,
    verdict: str,
    programming_language: str = "C++17",
    sub_id: int | None = None,
    pass_count: int = 0,
    time_consumed_ms: int = 0,
    memory_consumed_bytes: int = 0,
    problem_name: str | None = None,
    problem_rating: int | None = None,
    tags: list[str] | None = None,
    creation_time_seconds: int | None = None,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """Insert or update a single submission and ensure problem metadata is recorded."""
    clean_handle = handle.lower()
    ts = creation_time_seconds or int(time.time())
    actual_sub_id = sub_id or int(time.time() * 1000) % 2147483647
    
    with get_db_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO users (handle)
            VALUES (?)
            ON CONFLICT(handle) DO NOTHING;
        """, (clean_handle,))

        tags_json = json.dumps(tags or [])
        name = problem_name or f"Problem {contest_id}{idx}"
        conn.execute("""
            INSERT INTO problems (contest_id, idx, name, rating, tags_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(contest_id, idx) DO UPDATE SET
                rating = COALESCE(excluded.rating, problems.rating),
                tags_json = CASE WHEN excluded.tags_json != '[]' THEN excluded.tags_json ELSE problems.tags_json END;
        """, (contest_id, idx, name, problem_rating, tags_json))

        conn.execute("""
            INSERT INTO submissions (
                id, user_handle, contest_id, idx, verdict,
                programming_language, pass_count, time_consumed_ms,
                memory_consumed_bytes, creation_time_seconds
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                verdict = excluded.verdict,
                pass_count = excluded.pass_count,
                time_consumed_ms = excluded.time_consumed_ms,
                memory_consumed_bytes = excluded.memory_consumed_bytes;
        """, (
            actual_sub_id, clean_handle, contest_id, idx, verdict,
            programming_language, pass_count, time_consumed_ms,
            memory_consumed_bytes, ts
        ))
    return actual_sub_id

def upsert_test_case(
    contest_id: int,
    idx: str,
    test_index: int,
    input_data: str,
    expected_output: str,
    is_sample: bool = False,
    db_path: str = DEFAULT_DB_PATH
) -> None:
    """Insert or update a test case for a problem."""
    clean_idx = idx.upper()
    with get_db_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO problems (contest_id, idx, name, rating, tags_json)
            VALUES (?, ?, ?, NULL, '[]')
            ON CONFLICT(contest_id, idx) DO NOTHING;
        """, (contest_id, clean_idx, f"Problem {contest_id}{clean_idx}"))
        conn.execute("""
            INSERT INTO test_cases (contest_id, idx, test_index, input_data, expected_output, is_sample)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(contest_id, idx, test_index) DO UPDATE SET
                input_data = excluded.input_data,
                expected_output = excluded.expected_output,
                is_sample = excluded.is_sample;
        """, (contest_id, clean_idx, test_index, input_data, expected_output, int(is_sample)))

def upsert_test_cases_batch(
    test_cases: list[dict[str, Any]],
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """Batch insert or update test cases. Returns count of processed items."""
    count = 0
    with get_db_connection(db_path) as conn:
        for tc in test_cases:
            contest_id = tc.get("contest_id") or tc.get("contestId")
            idx = tc.get("idx") or tc.get("index")
            test_index = tc.get("test_index", 1)
            input_data = tc.get("input_data", "")
            expected_output = tc.get("expected_output", "")
            is_sample = bool(tc.get("is_sample", False))
            if contest_id and idx:
                clean_idx = str(idx).upper()
                conn.execute("""
                    INSERT INTO problems (contest_id, idx, name, rating, tags_json)
                    VALUES (?, ?, ?, NULL, '[]')
                    ON CONFLICT(contest_id, idx) DO NOTHING;
                """, (contest_id, clean_idx, f"Problem {contest_id}{clean_idx}"))
                conn.execute("""
                    INSERT INTO test_cases (contest_id, idx, test_index, input_data, expected_output, is_sample)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(contest_id, idx, test_index) DO UPDATE SET
                        input_data = excluded.input_data,
                        expected_output = excluded.expected_output,
                        is_sample = excluded.is_sample;
                """, (contest_id, clean_idx, test_index, input_data, expected_output, int(is_sample)))
                count += 1
    return count

def get_problem_test_cases(
    contest_id: int,
    idx: str,
    samples_only: bool = False,
    db_path: str = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    """Retrieve test cases for a specific problem ordered by test_index."""
    with get_db_connection(db_path) as conn:
        if samples_only:
            cursor = conn.execute("""
                SELECT * FROM test_cases
                WHERE contest_id = ? AND idx = ? AND is_sample = 1
                ORDER BY test_index ASC;
            """, (contest_id, idx.upper()))
        else:
            cursor = conn.execute("""
                SELECT * FROM test_cases
                WHERE contest_id = ? AND idx = ?
                ORDER BY test_index ASC;
            """, (contest_id, idx.upper()))
        return [dict(row) for row in cursor.fetchall()]

def seed_dataset_test_cases(
    dataset_path: str | None = None,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """Seed test cases from the curated dataset.json into SQLite."""
    if not dataset_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dataset_path = os.path.join(base_dir, "evals", "dataset.json")

    if not os.path.exists(dataset_path):
        return 0

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_case_list = []
    for item in data:
        cid = item.get("contest_id")
        idx = item.get("index")
        sample_in = item.get("sample_input")
        sample_out = item.get("sample_output")
        if cid and idx and sample_in and sample_out:
            test_case_list.append({
                "contest_id": cid,
                "idx": idx,
                "test_index": 1,
                "input_data": sample_in,
                "expected_output": sample_out,
                "is_sample": True
            })

    return upsert_test_cases_batch(test_case_list, db_path=db_path)
    

def get_cached_hint(contest_id: int, idx: str, hint_level: int, db_path: str = DEFAULT_DB_PATH) -> str | None:
    """Retrieve an approved cached hint for a problem and level."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT hint_text FROM cached_hints WHERE contest_id = ? AND idx = ? AND hint_level = ?;",
            (contest_id, idx.upper(), hint_level)
        )
        row = cursor.fetchone()
        return row["hint_text"] if row else None

def save_cached_hint(contest_id: int, idx: str, hint_level: int, hint_text: str, db_path: str = DEFAULT_DB_PATH) -> None:
    """Save an approved hint into the cache for instant zero-latency retrieval."""
    if not hint_text or not hint_text.strip():
        return
    with get_db_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO cached_hints (contest_id, idx, hint_level, hint_text)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(contest_id, idx, hint_level) DO UPDATE SET
                hint_text = excluded.hint_text,
                created_at = CURRENT_TIMESTAMP;
        """, (contest_id, idx.upper(), hint_level, hint_text.strip()))

def get_user_auth(handle: str, db_path: str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    """Retrieve user authentication credentials by handle."""
    clean_handle = handle.lower().strip()
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT salt, hashed_passkey FROM user_auth WHERE handle = ?;", (clean_handle,))
        row = cursor.fetchone()
        return dict(row) if row else None

def save_user_auth(handle: str, salt: str, hashed_passkey: str, db_path: str = DEFAULT_DB_PATH) -> None:
    """Register authentication credentials for a handle."""
    clean_handle = handle.lower().strip()
    with get_db_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO user_auth (handle, salt, hashed_passkey) VALUES (?, ?, ?);",
            (clean_handle, salt, hashed_passkey)
        )

def ensure_db_initialized(db_path: str = DEFAULT_DB_PATH) -> None:
    """Explicitly verify that database schema is initialized."""
    abs_path = os.path.abspath(db_path)
    if abs_path not in _INITIALIZED_DBS:
        init_db(db_path)

def check_db_health(db_path: str = DEFAULT_DB_PATH) -> dict[str, Any]:
    """Verify database connection, WAL journal mode, and schema integrity."""
    try:
        ensure_db_initialized(db_path)
        with get_db_connection(db_path) as conn:
            cursor = conn.execute("PRAGMA integrity_check;")
            integrity_row = cursor.fetchone()
            integrity_status = integrity_row[0] if integrity_row else "unknown"

            cursor = conn.execute("PRAGMA journal_mode;")
            journal_row = cursor.fetchone()
            journal_mode = journal_row[0] if journal_row else "unknown"

            cursor = conn.execute("SELECT COUNT(*) as problem_count FROM problems;")
            problem_count = cursor.fetchone()["problem_count"]

            return {
                "healthy": integrity_status.lower() == "ok",
                "integrity": integrity_status,
                "journal_mode": journal_mode,
                "problem_count": problem_count,
                "path": os.path.abspath(db_path)
            }
    except Exception as e:
        logger.error(f"DB health check failed for {db_path}: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "path": os.path.abspath(db_path)
        }