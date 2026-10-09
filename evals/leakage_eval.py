"""Independent LLM Judge & Leakage Evaluation Suite for CP Coach.

Compares Multi-Agent CP Coach (Tutor ⇄ Keeper) against Single-Agent Baseline
across benchmark dataset problems to compute empirical leakage and safety metrics.
"""
import os
import json
import time
import logging
from typing import Any

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
