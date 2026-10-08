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
