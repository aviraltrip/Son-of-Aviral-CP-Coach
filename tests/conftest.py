"""Shared pytest fixtures for CP Coach test suite."""
import os
import pytest
from app.data.db import init_db
from app.agents.llm import MockLLM

@pytest.fixture(autouse=True)
def mock_llm_in_tests(monkeypatch):
    """Ensure all unit and integration tests use deterministic MockLLM without external network calls or rate limits."""
    monkeypatch.setattr("app.agents.llm.get_llm", lambda model_type="tutor": MockLLM(model_name=f"mock-{model_type}"))
    monkeypatch.setattr("app.agents.tutor.get_llm", lambda model_type="tutor": MockLLM(model_name=f"mock-{model_type}"))
    monkeypatch.setattr("app.agents.keeper.get_llm", lambda model_type="keeper": MockLLM(model_name=f"mock-{model_type}"))
    monkeypatch.setattr("app.agents.analyst.get_llm", lambda model_type="analyst": MockLLM(model_name=f"mock-{model_type}"))

@pytest.fixture
def temp_db(tmp_path):
    """Create an isolated temporary SQLite database for testing."""
    db_file = str(tmp_path / "test_cp_coach.db")
    init_db(db_file)
    return db_file
