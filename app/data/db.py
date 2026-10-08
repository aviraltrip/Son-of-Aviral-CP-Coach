"""SQLite database layer for CP Coach. Encapsulates all SQL access."""
import os
import sqlite3
import json
import time
from typing import Any, Generator
from contextlib import contextmanager

DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "cp_coach.db")

@contextmanager
def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize SQLite tables idempotently."""
    with get_db_connection(db_path) as conn:
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

def upsert_user(handle: str, current_rating: int | None, max_rating: int | None, db_path: str = DEFAULT_DB_PATH) -> None:
    """Insert or update a Codeforces user record."""
    init_db(db_path)
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
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM users WHERE handle = ?;", (handle.lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def upsert_problems(problems_data: list[dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> int:
    """Batch insert or update problems in the catalog."""
    init_db(db_path)
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
    init_db(db_path)
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
    init_db(db_path)
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
    init_db(db_path)
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
    init_db(db_path)
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
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("""
            SELECT DISTINCT contest_id, idx FROM submissions
            WHERE user_handle = ?;
        """, (handle.lower(),))
        return {(row["contest_id"], row["idx"]) for row in cursor.fetchall()}

def save_topic_stats(handle: str, topic_stats_list: list[dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> None:
    """Save computed topic statistics for a user."""
    init_db(db_path)
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
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("""
            SELECT * FROM topic_stats
            WHERE user_handle = ?
            ORDER BY weighted_failure_score DESC;
        """, (handle.lower(),))
        return [dict(row) for row in cursor.fetchall()]

def save_reference_solution(contest_id: int, idx: str, solution_code: str, solution_editorial: str = "", source: str = "manual", db_path: str = DEFAULT_DB_PATH) -> None:
    """Save private reference solution for the Keeper agent."""
    init_db(db_path)
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
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.execute('SELECT * FROM "references" WHERE contest_id = ? AND idx = ?;', (contest_id, idx))
        row = cursor.fetchone()
        return dict(row) if row else None
