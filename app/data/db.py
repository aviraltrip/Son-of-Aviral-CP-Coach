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
