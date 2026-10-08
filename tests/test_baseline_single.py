"""Unit tests for single-agent baseline hint generation and batch evaluation."""
import json
import pytest
from unittest.mock import MagicMock

from evals.baseline_single import (
    BASELINE_SYSTEM_PROMPT,
    build_baseline_prompt,
    generate_baseline_hint,
    run_baseline_batch,
)
from app.agents.llm import MockLLM

def test_build_baseline_prompt_levels():
    """Verify baseline prompt incorporates problem statement and requested hint tiers."""
    stmt = "Given a binary tree, find the minimum operations."
    
    p1 = build_baseline_prompt(stmt, 1)
    assert "Level 1" in p1
    assert stmt in p1

    p2 = build_baseline_prompt(stmt, 2)
    assert "Level 2" in p2

    p3 = build_baseline_prompt(stmt, 3)
    assert "Level 3" in p3

def test_build_baseline_prompt_with_history():
    """Verify baseline prompt formats recent conversation history."""
    history = [
        {"role": "user", "content": "I tried DFS but failed."},
        {"role": "assistant", "content": "Consider tree transitions."}
    ]
    p = build_baseline_prompt("Problem statement", 1, history=history)
    assert "Recent Conversation History:" in p
    assert "DFS" in p

def test_generate_baseline_hint_with_mock_llm():
    """Verify generate_baseline_hint returns structured metadata with MockLLM."""
    mock_llm = MockLLM(model_name="mock-test-model")
    res = generate_baseline_hint(
        problem_statement="Find max subarray sum.",
        hint_level=1,
        llm=mock_llm,
        problem_name="1900C"
    )

    assert res["problem_name"] == "1900C"
    assert res["hint_level"] == 1
    assert isinstance(res["hint_text"], str)
    assert len(res["hint_text"]) > 0
    assert res["model_name"] == "mock-test-model"
    assert res["latency_seconds"] >= 0.0
    assert res["timestamp"] > 0

def test_generate_baseline_hint_exception_fallback():
    """Verify generate_baseline_hint provides safe fallback when LLM fails."""
    faulty_llm = MagicMock()
    faulty_llm.invoke.side_effect = RuntimeError("API Rate Limit Exceeded")
    
    res = generate_baseline_hint(
        problem_statement="Solve problem X.",
        hint_level=2,
        llm=faulty_llm,
        problem_name="TestProblem"
    )

    assert res["hint_level"] == 2
    assert "Observe problem constraints" in res["hint_text"]

def test_run_baseline_batch(tmp_path):
    """Verify run_baseline_batch runs all hint tiers across problem list and writes JSON."""
    problems = [
        {
            "contest_id": 1900,
            "index": "C",
            "name": "Anji's Binary Tree",
            "rating": 1500,
            "tags": ["dp", "trees"],
            "statement": "You are given a binary tree with n vertices."
        },
        {
            "contest_id": 1800,
            "index": "B",
            "name": "Count the Number of Pairs",
            "rating": 1000,
            "tags": ["greedy", "strings"],
            "statement": "You are given a string s of length n."
        }
    ]

    out_file = str(tmp_path / "baseline_results.json")
    mock_llm = MockLLM()
    results = run_baseline_batch(
        problems,
        hint_levels=[1, 2, 3],
        output_file=out_file,
        llm=mock_llm
    )

    # 2 problems * 3 hint levels = 6 hint records
    assert len(results) == 6
    assert results[0]["contest_id"] == 1900
    assert results[0]["index"] == "C"
    assert results[0]["hint_level"] == 1
    assert results[1]["hint_level"] == 2
    assert results[2]["hint_level"] == 3

    # Check written file
    with open(out_file, "r", encoding="utf-8") as fp:
        saved_data = json.load(fp)
    assert len(saved_data) == 6
