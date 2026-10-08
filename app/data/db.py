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
