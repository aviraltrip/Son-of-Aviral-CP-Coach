"""Unit tests for LangSmith observability and distributed tracing integration."""
import os
import pytest
from unittest.mock import patch, MagicMock

from app.config import AppConfig, sync_langsmith_env
from app.observability import (
    configure_langsmith,
    is_langsmith_enabled,
    get_langsmith_config,
    record_langsmith_feedback
)

def test_configure_langsmith_enabled_via_config(monkeypatch):
    """Verify that configure_langsmith populates os.environ when config has tracing enabled."""
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    monkeypatch.delenv("LANGCHAIN_ENDPOINT", raising=False)

    cfg = AppConfig(
        langchain_tracing_v2=True,
        langchain_api_key="lsv2_pt_testkey",
        langchain_project="test-project",
        langchain_endpoint="https://api.smith.test.com"
    )

    result = configure_langsmith(cfg)
    assert result is True
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
    assert os.environ.get("LANGCHAIN_API_KEY") == "lsv2_pt_testkey"
    assert os.environ.get("LANGCHAIN_PROJECT") == "test-project"
    assert os.environ.get("LANGCHAIN_ENDPOINT") == "https://api.smith.test.com"

def test_configure_langsmith_disabled_when_empty(monkeypatch):
    """Verify configure_langsmith returns False when tracing is not configured."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    cfg = AppConfig(
        langchain_tracing_v2=False,
        langchain_api_key="",
        langchain_project="cp-coach"
    )

    result = configure_langsmith(cfg)
    assert result is False
    assert not is_langsmith_enabled()

def test_configure_langsmith_explicit_false_overrides_key(monkeypatch):
    """Verify that explicit LANGCHAIN_TRACING_V2=false disables tracing even if key is present."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    cfg = AppConfig(
        langchain_tracing_v2=False,
        langchain_api_key="some_key"
    )

    result = configure_langsmith(cfg)
    assert result is False
    assert not is_langsmith_enabled()

def test_is_langsmith_enabled(monkeypatch):
    """Verify boolean status reflecting LANGCHAIN_TRACING_V2 env var."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    assert is_langsmith_enabled() is True

    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    assert is_langsmith_enabled() is False

def test_get_langsmith_config():
    """Verify that config dictionary contains configurable, tags, metadata, and run_name."""
    config = get_langsmith_config(
        thread_id="test-thread-1234",
        handle="tourist",
        environment="testing",
        tags=["ui", "fast"],
        metadata={"hint_level": 2}
    )

    assert config["configurable"]["thread_id"] == "test-thread-1234"
    assert "cp-coach" in config["tags"]
    assert "env:testing" in config["tags"]
    assert "ui" in config["tags"]
    assert config["metadata"]["handle"] == "tourist"
    assert config["metadata"]["environment"] == "testing"
    assert config["metadata"]["hint_level"] == 2
    assert "tourist" in config["run_name"]

def test_record_langsmith_feedback_disabled(monkeypatch):
    """Verify feedback returns False when tracing is disabled."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    success = record_langsmith_feedback("run-123", "utility", 1.0)
    assert success is False

def test_record_langsmith_feedback_no_run_id(monkeypatch):
    """Verify feedback returns False when run_id is missing."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "test-key")
    success = record_langsmith_feedback(None, "utility", 1.0)
    assert success is False

def test_record_langsmith_feedback_success(monkeypatch):
    """Verify feedback calls Client.create_feedback when enabled."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_pt_key")

    mock_client = MagicMock()
    with patch("langsmith.Client", return_value=mock_client):
        success = record_langsmith_feedback("run-123", "pedagogical_utility", 1.0, comment="Great hint")
        assert success is True
        mock_client.create_feedback.assert_called_once_with(
            run_id="run-123",
            key="pedagogical_utility",
            score=1.0,
            comment="Great hint"
        )

def test_record_langsmith_feedback_error_handled(monkeypatch):
    """Verify feedback catches client exceptions gracefully without crashing."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_pt_key")

    mock_client = MagicMock()
    mock_client.create_feedback.side_effect = RuntimeError("API unreachable")
    with patch("langsmith.Client", return_value=mock_client):
        success = record_langsmith_feedback("run-123", "spoiler_leakage", 0.0)
        assert success is False
