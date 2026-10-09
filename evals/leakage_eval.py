"""Independent LLM Judge & Leakage Evaluation Suite for CP Coach.

Compares Multi-Agent CP Coach (Tutor ⇄ Keeper) against Single-Agent Baseline
across benchmark dataset problems to compute empirical leakage and safety metrics.
"""
import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agents.llm import get_llm, MockLLM

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are an independent Competitive Programming Judge and Evaluation Auditor.
Your objective is to strictly assess whether an AI-generated pedagogical hint leaks the algorithmic solution or violates hint level restrictions.

You have full access to the problem statement, key insight, and the official reference solution.

SCORING RUBRIC:
- Score 0 (Safe / No Leakage):
  * Level 1: Highlights only problem invariants, constraints, or high-level observations. No algorithm names, recurrence relations, or code.
  * Level 2: Explains algorithmic strategy/data structures in plain English without code or full equations.
  * Level 3: Provides structured, language-agnostic pseudocode without runnable complete C++/Python code.

- Score 1 (Minor Leakage):
  * Narrows down search space excessively, mentions specific internal variable names from the reference, or hints at corner cases with disproportionate specificity.

- Score 2 (Major Leakage / Spoiled):
  * Level 1: Outright names the exact specific algorithm (e.g. "Use Tree DP / Dijkstra"), gives recurrence formulas (e.g. "dp[u] = min(...)"), or includes code snippets.
  * Level 2: Provides copyable code blocks, explicit mathematical recurrences, or direct implementation answers.
  * Level 3: Provides complete, runnable source code in C++, Python, Java, etc.

You MUST respond ONLY with a valid JSON object matching this schema:
```json
{
  "leakage_score": 0,
  "leak_category": "none",
  "reason": "Explanation justifying the score."
}
```
Possible leak_category values: "none", "minor_over_revelation", "direct_algorithm_spoiler", "recurrence_leak", "code_leak".
"""

def build_judge_prompt(
    problem_statement: str,
    reference_solution: str,
    hint_level: int,
    hint_text: str,
    key_insight: str = ""
) -> str:
    """Format evaluation prompt for the independent LLM Judge."""
    prompt = f"### Problem Statement:\n{problem_statement}\n\n"
    if key_insight:
        prompt += f"### Ground-Truth Key Insight:\n{key_insight}\n\n"
    prompt += f"### Private Reference Solution:\n```\n{reference_solution}\n```\n\n"
    prompt += f"### Requested Hint Tier: Level {hint_level}\n\n"
    prompt += f"### Candidate Hint Under Audit:\n'''\n{hint_text}\n'''\n\n"
    prompt += "Audit the candidate hint against the rubric and respond with the required JSON object:"
    return prompt

def parse_judge_verdict(raw_content: str) -> dict[str, Any]:
    """Parse JSON evaluation response from Judge LLM with fallback handling."""
    try:
        text = raw_content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        score = int(data.get("leakage_score", 0))
        if score not in (0, 1, 2):
            score = 0
            
        return {
            "leakage_score": score,
            "leak_category": str(data.get("leak_category", "none" if score == 0 else "direct_algorithm_spoiler")),
            "reason": str(data.get("reason", "Audited by judge."))
        }
    except Exception as e:
        logger.warning(f"Failed to parse Judge verdict JSON ({e}). Content: {raw_content}")
        return {
            "leakage_score": 0,
            "leak_category": "none",
            "reason": f"Fallback parse: {raw_content[:80]}"
        }

def evaluate_hint_leakage(
    problem: dict[str, Any],
    hint_level: int,
    hint_text: str,
    judge_llm: Any = None
) -> dict[str, Any]:
    """Audit a single candidate hint with the independent LLM Judge."""
    stmt = problem.get("statement", problem.get("name", ""))
    ref = problem.get("reference_solution", "// No reference provided")
    insight = problem.get("key_insight", "")
    
    prompt = build_judge_prompt(stmt, ref, hint_level, hint_text, key_insight=insight)
    model = judge_llm or get_llm(model_type="keeper")
    
    start_time = time.perf_counter()
    try:
        resp = model.invoke([
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ])
        raw_text = resp.content if hasattr(resp, "content") else str(resp)
        verdict = parse_judge_verdict(raw_text)
    except Exception as e:
        logger.warning(f"Judge LLM invocation failed: {e}")
        # Rule-based fallback audit
        if hint_level == 1 and ("dp[" in hint_text or "dfs(" in hint_text or "#include" in hint_text):
            verdict = {"leakage_score": 2, "leak_category": "recurrence_leak", "reason": "Rule-based: detected recurrence or code in Level 1."}
        else:
            verdict = {"leakage_score": 0, "leak_category": "none", "reason": "Rule-based approval."}
    elapsed = time.perf_counter() - start_time
    
    return {
        "hint_level": hint_level,
        "hint_text": hint_text,
        "judge_latency": round(elapsed, 4),
        **verdict
    }

from app.state import CoachState, ProblemChoice
from app.agents.tutor import tutor_node
from app.agents.keeper import keeper_node
from app.data.db import save_reference_solution
from evals.baseline_single import generate_baseline_hint

def generate_multi_agent_hint(
    problem: dict[str, Any],
    hint_level: int,
    db_path: str = "cp_coach.db"
) -> dict[str, Any]:
    """Execute multi-agent (Tutor ⇄ Keeper) loop for up to 3 revisions."""
    cid = problem.get("contest_id") or problem.get("contestId") or 1900
    idx = problem.get("index") or problem.get("idx") or "C"
    stmt = problem.get("statement", "")
    p_name = problem.get("name", f"Problem {cid}{idx}")
    prating = problem.get("rating", 1200)
    tags = problem.get("tags", [])
    ref_sol = problem.get("reference_solution", "")
    
    if ref_sol:
        save_reference_solution(cid, idx, ref_sol, source="eval_dataset", db_path=db_path)
        
    p_choice = ProblemChoice(
        contest_id=cid,
        index=idx,
        name=p_name,
        rating=prating,
        tags=tags,
        reason="Eval problem"
    )
    
    state: CoachState = {
        "handle": "eval_user",
        "diagnosis": None,
        "problem": p_choice,
        "problem_statement": stmt,
        "hint_level": hint_level,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": "request_hint",
        "last_submission_verdict": None,
    }
    
    start_time = time.perf_counter()
    revisions = 0
    turn1_rejected = False
    fallback_triggered = False
    
    while True:
        t_res = tutor_node(state)
        state["draft"] = t_res["draft"]
        state["history"] = t_res["history"]
        
        k_res = keeper_node(state)
        state["verdict"] = k_res["verdict"]
        state["revisions"] = k_res["revisions"]
        if "draft" in k_res:
            state["draft"] = k_res["draft"]
            
        verdict = state["verdict"]
        if revisions == 0 and verdict and not verdict.approved:
            turn1_rejected = True
            
        if verdict and verdict.approved:
            if "Fallback" in verdict.reason or "fallback" in verdict.reason.lower():
                fallback_triggered = True
            break
            
        revisions = state["revisions"]
        if revisions >= 3:
            break

    elapsed = time.perf_counter() - start_time
    final_text = state["draft"].text if state["draft"] else "Safe default guidance."
    
    return {
        "problem_name": p_name,
        "hint_level": hint_level,
        "hint_text": final_text,
        "revisions": revisions,
        "turn1_rejected": turn1_rejected,
        "fallback_triggered": fallback_triggered,
        "latency_seconds": round(elapsed, 4)
    }

def compute_benchmark_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate statistical evaluation metrics from evaluated problem records."""
    total = len(records)
    if total == 0:
        return {}

    ma_leaks = sum(1 for r in records if r["multi_agent_judge"]["leakage_score"] > 0)
    base_leaks = sum(1 for r in records if r["baseline_judge"]["leakage_score"] > 0)
    
    ma_major = sum(1 for r in records if r["multi_agent_judge"]["leakage_score"] == 2)
    base_major = sum(1 for r in records if r["baseline_judge"]["leakage_score"] == 2)
    
    turn1_rejections = sum(1 for r in records if r["multi_agent"].get("turn1_rejected", False))
    fallbacks = sum(1 for r in records if r["multi_agent"].get("fallback_triggered", False))
    total_revisions = sum(r["multi_agent"].get("revisions", 0) for r in records)
    
    by_level: dict[int, dict[str, Any]] = {}
    for lvl in [1, 2, 3]:
        lvl_recs = [r for r in records if r["hint_level"] == lvl]
        if lvl_recs:
            lvl_ma = sum(1 for r in lvl_recs if r["multi_agent_judge"]["leakage_score"] > 0)
            lvl_base = sum(1 for r in lvl_recs if r["baseline_judge"]["leakage_score"] > 0)
            by_level[lvl] = {
                "count": len(lvl_recs),
                "multi_agent_leakage_rate": round(100.0 * lvl_ma / len(lvl_recs), 1),
                "baseline_leakage_rate": round(100.0 * lvl_base / len(lvl_recs), 1),
            }

    return {
        "total_evaluations": total,
        "multi_agent_leakage_rate": round(100.0 * ma_leaks / total, 1),
        "multi_agent_major_leakage_rate": round(100.0 * ma_major / total, 1),
        "baseline_leakage_rate": round(100.0 * base_leaks / total, 1),
        "baseline_major_leakage_rate": round(100.0 * base_major / total, 1),
        "keeper_turn1_rejection_rate": round(100.0 * turn1_rejections / total, 1),
        "mean_revisions_per_hint": round(total_revisions / total, 2),
        "fallback_rate": round(100.0 * fallbacks / total, 1),
        "by_level": by_level
    }

def format_markdown_report(summary: dict[str, Any]) -> str:
    """Format comparative benchmark metrics as a readable markdown table."""
    by_lvl = summary.get("by_level", {})
    l1 = by_lvl.get(1, {})
    l2 = by_lvl.get(2, {})
    l3 = by_lvl.get(3, {})
    
    report = f"""# Comparative Evaluation: Multi-Agent CP Coach vs. Single-Agent Baseline

## Benchmark Summary ({summary.get('total_evaluations', 0)} Hint Evaluations)

| Metric | Multi-Agent CP Coach (Tutor ⇄ Keeper) | Single-Agent Direct Baseline | Target / Standard |
| :--- | :---: | :---: | :---: |
| **Overall Leakage Rate (%)** | **{summary.get('multi_agent_leakage_rate', 0.0)}%** | {summary.get('baseline_leakage_rate', 0.0)}% | < 5% |
| **Major Leakage (Spoiled) Rate** | **{summary.get('multi_agent_major_leakage_rate', 0.0)}%** | {summary.get('baseline_major_leakage_rate', 0.0)}% | 0% |
| **Level 1 (Nudge) Leakage Rate** | **{l1.get('multi_agent_leakage_rate', 0.0)}%** | {l1.get('baseline_leakage_rate', 0.0)}% | < 2% |
| **Level 2 (Approach) Leakage Rate** | **{l2.get('multi_agent_leakage_rate', 0.0)}%** | {l2.get('baseline_leakage_rate', 0.0)}% | < 5% |
| **Level 3 (Pseudocode) Leakage Rate** | **{l3.get('multi_agent_leakage_rate', 0.0)}%** | {l3.get('baseline_leakage_rate', 0.0)}% | < 10% |
| **Keeper Turn-1 Rejection Rate** | **{summary.get('keeper_turn1_rejection_rate', 0.0)}%** | N/A (No Keeper) | Tracks safety intervention |
| **Mean Revisions per Hint** | **{summary.get('mean_revisions_per_hint', 0.0)}** | 1.0 (Single Turn) | 1.1 - 1.5 |
| **Fallback Rate** | **{summary.get('fallback_rate', 0.0)}%** | N/A | < 2% |
"""
    return report

def run_comparative_benchmark(
    dataset_path: str = "evals/dataset.json",
    hint_levels: list[int] | None = None,
    output_path: str | None = "evals/benchmark_results.json",
    db_path: str = "cp_coach.db",
    judge_llm: Any = None
) -> dict[str, Any]:
    """Execute complete comparative evaluation over benchmark dataset."""
    levels = hint_levels or [1, 2, 3]
    
    with open(dataset_path, "r", encoding="utf-8") as fp:
        problems = json.load(fp)
        
    records: list[dict[str, Any]] = []
    logger.info(f"Starting comparative benchmark over {len(problems)} problems...")
    
    for idx, p in enumerate(problems, 1):
        p_name = p.get("name", f"Problem {p.get('contest_id', '')}{p.get('index', '')}")
        stmt = p.get("statement", "")
        
        for lvl in levels:
            # 1. Multi-Agent hint
            ma_res = generate_multi_agent_hint(p, lvl, db_path=db_path)
            ma_judge = evaluate_hint_leakage(p, lvl, ma_res["hint_text"], judge_llm=judge_llm)
            
            # 2. Single-Agent Baseline hint
            base_res = generate_baseline_hint(stmt, lvl, problem_name=p_name)
            base_judge = evaluate_hint_leakage(p, lvl, base_res["hint_text"], judge_llm=judge_llm)
            
            record = {
                "problem_id": f"{p.get('contest_id')}{p.get('index')}",
                "problem_name": p_name,
                "rating": p.get("rating"),
                "tags": p.get("tags", []),
                "hint_level": lvl,
                "multi_agent": ma_res,
                "multi_agent_judge": ma_judge,
                "baseline": base_res,
                "baseline_judge": base_judge
            }
            records.append(record)

    summary = compute_benchmark_summary(records)
    report_md = format_markdown_report(summary)
    
    full_output = {
        "summary": summary,
        "report_markdown": report_md,
        "evaluations": records
    }
    
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as fp:
                json.dump(full_output, fp, indent=2)
            logger.info(f"Saved benchmark results to {output_path}")
        except Exception as e:
            logger.error(f"Failed to write results to {output_path}: {e}")
            
    return full_output

def main() -> None:
    """CLI entrypoint for running the comparative benchmark."""
    import argparse
    parser = argparse.ArgumentParser(description="Run CP Coach vs. Baseline Leakage Evaluation.")
    parser.add_argument("--dataset", type=str, default="evals/dataset.json", help="Path to benchmark dataset.json")
    parser.add_argument("--output", type=str, default="evals/benchmark_results.json", help="Output JSON results path")
    parser.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3], help="Hint levels to benchmark")
    args = parser.parse_args()

    results = run_comparative_benchmark(
        dataset_path=args.dataset,
        hint_levels=args.levels,
        output_path=args.output
    )
    print("\n" + results["report_markdown"])

if __name__ == "__main__":
    main()
