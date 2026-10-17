"""Unit tests for independent LLM Judge and leakage benchmark evaluation suite."""
import json
import pytest
from unittest.mock import MagicMock

from evals.leakage_eval import (
    JUDGE_SYSTEM_PROMPT,
    build_judge_prompt,
    parse_judge_verdict,
    evaluate_hint_leakage,
    generate_multi_agent_hint,
    compute_benchmark_summary,
    format_markdown_report,
    run_comparative_benchmark,
)
from app.agents.llm import MockLLM
from app.data.db import init_db

@pytest.fixture
def clean_eval_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_leakage_eval.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    init_db(db_file)
    return db_file

def test_build_judge_prompt_structure():
    """Verify build_judge_prompt includes statement, reference code, insight, and candidate draft."""
    prompt = build_judge_prompt(
        problem_statement="Given a tree, compute min operations.",
        reference_solution="int dfs(int u) { return 0; }",
        hint_level=1,
        hint_text="Look at the subtree transitions.",
        key_insight="Tree dynamic programming"
    )

    assert "### Problem Statement:" in prompt
    assert "### Ground-Truth Key Insight:" in prompt
    assert "Tree dynamic programming" in prompt
    assert "### Private Reference Solution:" in prompt
    assert "### Requested Hint Tier: Level 1" in prompt
    assert "Look at the subtree transitions." in prompt

def test_parse_judge_verdict_valid_json():
    """Verify parse_judge_verdict handles raw JSON strings."""
    raw = '{"leakage_score": 0, "leak_category": "none", "reason": "Safe nudge."}'
    verdict = parse_judge_verdict(raw)
    assert verdict["leakage_score"] == 0
    assert verdict["leak_category"] == "none"
    assert "Safe nudge." in verdict["reason"]

def test_parse_judge_verdict_markdown_fences():
    """Verify parse_judge_verdict parses JSON wrapped inside markdown code fences."""
    raw = """```json
{
  "leakage_score": 2,
  "leak_category": "recurrence_leak",
  "reason": "Directly revealed dp[u] transition at Level 1."
}
```"""
    verdict = parse_judge_verdict(raw)
    assert verdict["leakage_score"] == 2
    assert verdict["leak_category"] == "recurrence_leak"

def test_parse_judge_verdict_malformed_fallback():
    """Verify parse_judge_verdict falls back gracefully on unparseable responses."""
    raw = "Invalid non-JSON response from model"
    verdict = parse_judge_verdict(raw)
    assert verdict["leakage_score"] == 0
    assert "Fallback parse" in verdict["reason"]

def test_evaluate_hint_leakage_clean():
    """Verify evaluate_hint_leakage runs audit and returns metadata with MockLLM."""
    problem = {
        "statement": "Find max element.",
        "reference_solution": "int main() {}",
        "key_insight": "Linear scan"
    }
    mock_llm = MockLLM()
    res = evaluate_hint_leakage(problem, 1, "Consider how to track the largest value seen so far.", judge_llm=mock_llm)
    
    assert res["hint_level"] == 1
    assert res["leakage_score"] in (0, 1, 2)
    assert res["judge_latency"] >= 0.0

def test_generate_multi_agent_hint(clean_eval_db, monkeypatch):
    """Verify generate_multi_agent_hint runs the Tutor ⇄ Keeper verification loop."""
    monkeypatch.setattr("app.agents.tutor.get_llm", lambda *a, **k: MockLLM())
    monkeypatch.setattr("app.agents.keeper.get_llm", lambda *a, **k: MockLLM())
    problem = {
        "contest_id": 1900,
        "index": "C",
        "name": "Anji's Binary Tree",
        "statement": "Binary tree problem statement.",
        "rating": 1500,
        "tags": ["dp", "trees"],
        "reference_solution": "int dfs(int u) { return 0; }"
    }

    res = generate_multi_agent_hint(problem, 1, db_path=clean_eval_db)
    assert res["problem_name"] == "Anji's Binary Tree"
    assert res["hint_level"] == 1
    assert isinstance(res["hint_text"], str)
    assert len(res["hint_text"]) > 0
    assert res["revisions"] <= 3

def test_compute_benchmark_summary_calculations():
    """Verify statistical metrics computation across evaluation records."""
    mock_records = [
        {
            "hint_level": 1,
            "multi_agent": {"revisions": 0, "turn1_rejected": False, "fallback_triggered": False},
            "multi_agent_judge": {"leakage_score": 0},
            "baseline_judge": {"leakage_score": 2}
        },
        {
            "hint_level": 1,
            "multi_agent": {"revisions": 1, "turn1_rejected": True, "fallback_triggered": False},
            "multi_agent_judge": {"leakage_score": 0},
            "baseline_judge": {"leakage_score": 0}
        },
        {
            "hint_level": 2,
            "multi_agent": {"revisions": 0, "turn1_rejected": False, "fallback_triggered": False},
            "multi_agent_judge": {"leakage_score": 0},
            "baseline_judge": {"leakage_score": 1}
        },
        {
            "hint_level": 3,
            "multi_agent": {"revisions": 3, "turn1_rejected": True, "fallback_triggered": True},
            "multi_agent_judge": {"leakage_score": 0},
            "baseline_judge": {"leakage_score": 0}
        }
    ]

    summary = compute_benchmark_summary(mock_records)
    assert summary["total_evaluations"] == 4
    assert summary["multi_agent_leakage_rate"] == 0.0
    assert summary["baseline_leakage_rate"] == 50.0
    assert summary["baseline_major_leakage_rate"] == 25.0
    assert summary["keeper_turn1_rejection_rate"] == 50.0
    assert summary["fallback_rate"] == 25.0
    assert summary["mean_revisions_per_hint"] == 1.0

def test_format_markdown_report():
    """Verify format_markdown_report creates a valid markdown table."""
    summary = {
        "total_evaluations": 10,
        "multi_agent_leakage_rate": 0.0,
        "multi_agent_major_leakage_rate": 0.0,
        "baseline_leakage_rate": 30.0,
        "baseline_major_leakage_rate": 10.0,
        "keeper_turn1_rejection_rate": 20.0,
        "mean_revisions_per_hint": 1.2,
        "fallback_rate": 0.0,
        "by_level": {
            1: {"multi_agent_leakage_rate": 0.0, "baseline_leakage_rate": 40.0},
            2: {"multi_agent_leakage_rate": 0.0, "baseline_leakage_rate": 20.0},
            3: {"multi_agent_leakage_rate": 0.0, "baseline_leakage_rate": 0.0},
        }
    }
    report = format_markdown_report(summary)
    assert "# Comparative Evaluation" in report
    assert "Overall Leakage Rate (%)" in report
    assert "**0.0%**" in report
    assert "30.0%" in report

def test_run_comparative_benchmark_mocked(tmp_path, clean_eval_db, monkeypatch):
    """Verify run_comparative_benchmark executes end-to-end and writes results JSON."""
    mini_dataset = [
        {
            "contest_id": 1900,
            "index": "C",
            "name": "Anji's Binary Tree",
            "rating": 1500,
            "tags": ["dp", "trees"],
            "statement": "Binary tree statement.",
            "reference_solution": "int dfs() {}",
            "key_insight": "Tree DP"
        }
    ]
    dataset_file = str(tmp_path / "mini_dataset.json")
    with open(dataset_file, "w", encoding="utf-8") as fp:
        json.dump(mini_dataset, fp)

    out_file = str(tmp_path / "bench_out.json")
    mock_llm = MockLLM()
    monkeypatch.setattr("app.agents.tutor.get_llm", lambda *a, **k: mock_llm)
    monkeypatch.setattr("app.agents.keeper.get_llm", lambda *a, **k: mock_llm)
    monkeypatch.setattr("evals.baseline_single.get_llm", lambda *a, **k: mock_llm)
    monkeypatch.setattr("evals.leakage_eval.get_llm", lambda *a, **k: mock_llm)
    
    results = run_comparative_benchmark(
        dataset_path=dataset_file,
        hint_levels=[1, 2],
        output_path=out_file,
        db_path=clean_eval_db,
        judge_llm=mock_llm
    )

    assert results["summary"]["total_evaluations"] == 2
    assert "report_markdown" in results
    assert len(results["evaluations"]) == 2

    with open(out_file, "r", encoding="utf-8") as fp:
        saved = json.load(fp)
    assert "summary" in saved
    assert len(saved["evaluations"]) == 2
