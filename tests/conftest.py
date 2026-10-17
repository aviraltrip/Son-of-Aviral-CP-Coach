"""Shared pytest fixtures for CP Coach test suite."""
import pytest
from app.data.db import init_db

@pytest.fixture
def temp_db(tmp_path):
    """Create an isolated temporary SQLite database for testing."""
    db_file = str(tmp_path / "test_cp_coach.db")
    init_db(db_file)
    return db_file
