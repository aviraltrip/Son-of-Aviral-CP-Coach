"""Single-Agent Baseline for competitive programming hints (Experimental Control).

Directly prompts a single LLM to generate hints at requested levels (1-3)
without a solution-aware Keeper agent auditing for leakage.
"""
import sys
import time
import logging
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logger = logging.getLogger(__name__)

BASELINE_SYSTEM_PROMPT = """You are a competitive programming coach.
Your job is to provide progressive hints to help a student solve a Codeforces problem on their own.

You must follow the requested Hint Level strictly:
- Level 1 (Nudge): High-level observation or leading question. Focus on invariant or constraint without naming algorithms or formulas.
- Level 2 (Approach): Explain the algorithmic paradigm, strategy, or relevant data structure in plain English. No code snippets.
- Level 3 (Pseudocode): Provide structured pseudocode and transitions. Do not provide runnable complete code in C++ or Python.

Do NOT reveal the full solution or write complete source code.
"""

def build_baseline_prompt(
    problem_statement: str,
    hint_level: int,
    history: list[dict[str, Any]] | None = None
) -> str:
    """Format single-chain user prompt with problem statement and requested hint tier."""
    level_descriptions = {
        1: "Level 1 (Nudge): Give a high-level conceptual observation or leading question.",
        2: "Level 2 (Approach): Explain the algorithmic strategy and data structures in English.",
        3: "Level 3 (Pseudocode): Provide structured pseudocode, recurrence, and edge cases."
    }
    tier_desc = level_descriptions.get(hint_level, level_descriptions[1])
    
    prompt = f"### Problem Statement:\n{problem_statement}\n\n"
    prompt += f"### Requested Hint Tier:\n{tier_desc}\n\n"
    
    if history:
        prompt += "### Recent Conversation History:\n"
        for turn in history[-4:]:
            role = turn.get("role", "user")
            content = turn.get("content") or turn.get("text", "")
            prompt += f"- {role.capitalize()}: {content}\n"
        prompt += "\n"
        
    prompt += "Provide the hint now:"
    return prompt

from app.agents.llm import get_llm

def generate_baseline_hint(
    problem_statement: str,
    hint_level: int,
    history: list[dict[str, Any]] | None = None,
    llm: Any | None = None,
    problem_name: str = ""
) -> dict[str, Any]:
    """Generate a hint using a single direct LLM call without Keeper audit."""
    prompt = build_baseline_prompt(problem_statement, hint_level, history)
    model = llm or get_llm(model_type="tutor")
    model_name = getattr(model, "model_name", getattr(model, "model", "default-llm"))
    
    start_time = time.perf_counter()
    try:
        resp = model.invoke([
            {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ])
        text = resp.content.strip() if hasattr(resp, "content") else str(resp).strip()
    except Exception as e:
        logger.warning(f"Baseline LLM invocation failed: {e}")
        text = f"Observe problem constraints and draw out small examples on paper."
    elapsed = time.perf_counter() - start_time

    return {
        "problem_name": problem_name,
        "hint_level": hint_level,
        "hint_text": text,
        "model_name": str(model_name),
        "latency_seconds": round(elapsed, 4),
        "timestamp": int(time.time())
    }

import json

def run_baseline_batch(
    problems: list[dict[str, Any]],
    hint_levels: list[int] | None = None,
    output_file: str | None = None,
    llm: Any | None = None
) -> list[dict[str, Any]]:
    """Run single-agent baseline across a batch of problems for all requested hint tiers."""
    levels = hint_levels or [1, 2, 3]
    results: list[dict[str, Any]] = []

    for idx, p in enumerate(problems, 1):
        p_name = p.get("name", f"Problem {p.get('contest_id', '')}{p.get('index', '')}")
        stmt = p.get("statement") or p.get("problem_statement") or p_name
        
        logger.info(f"[{idx}/{len(problems)}] Generating baseline hints for {p_name}...")
        for lvl in levels:
            hint_res = generate_baseline_hint(
                problem_statement=stmt,
                hint_level=lvl,
                llm=llm,
                problem_name=p_name
            )
            record = {
                "contest_id": p.get("contest_id") or p.get("contestId"),
                "index": p.get("index") or p.get("idx"),
                "name": p_name,
                "rating": p.get("rating"),
                "tags": p.get("tags", []),
                **hint_res
            }
            results.append(record)

    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as fp:
                json.dump(results, fp, indent=2)
            logger.info(f"Saved {len(results)} baseline hint records to {output_file}")
        except Exception as e:
            logger.error(f"Failed to write output to {output_file}: {e}")

    return results

def generate_baseline_conversation(
    problem_statement: str,
    problem_name: str = "",
    llm: Any | None = None
) -> list[dict[str, Any]]:
    """Simulate a progressive multi-turn hint conversation (Levels 1 -> 2 -> 3) using a single direct LLM."""
    history: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []
    
    for level in [1, 2, 3]:
        hint_res = generate_baseline_hint(
            problem_statement=problem_statement,
            hint_level=level,
            history=history,
            llm=llm,
            problem_name=problem_name
        )
        turns.append(hint_res)
        
        # Update history for next turn
        history.append({"role": "user", "content": f"Can you give me a Level {level} hint?"})
        history.append({"role": "assistant", "content": hint_res["hint_text"]})
        
    return turns

def load_problems_from_db(limit: int = 10, db_path: str = "cp_coach.db") -> list[dict[str, Any]]:
    """Load problems from local SQLite database for baseline evaluation."""
    from app.data.db import get_candidate_problems
    return get_candidate_problems(min_rating=800, max_rating=2000, limit=limit, db_path=db_path)

def main() -> None:
    """CLI entrypoint for running single-agent baseline hints."""
    import argparse
    parser = argparse.ArgumentParser(description="Run single-agent baseline hint generation.")
    parser.add_argument("--contest", type=int, default=1900, help="Contest ID")
    parser.add_argument("--index", type=str, default="C", help="Problem Index")
    parser.add_argument("--level", type=int, default=1, choices=[1, 2, 3], help="Hint Level (1-3)")
    parser.add_argument("--statement", type=str, default=None, help="Inline statement text")
    parser.add_argument("--all-levels", action="store_true", help="Generate all 3 hint levels")
    parser.add_argument("--from-db", action="store_true", help="Load problems from SQLite database")
    parser.add_argument("--limit", type=int, default=5, help="Number of problems to load from DB")
    parser.add_argument("--output", type=str, default=None, help="Path to save output JSON")
    args = parser.parse_args()

    if args.from_db:
        problems = load_problems_from_db(limit=args.limit)
        print(f"\n⚡ Loaded {len(problems)} problems from SQLite database. Running baseline batch...")
        results = run_baseline_batch(problems, output_file=args.output)
        print(f"✅ Generated {len(results)} baseline hint evaluations.")
        return

    if args.all_levels:
        stmt = args.statement or f"Problem {args.contest}{args.index} on Codeforces."
        turns = generate_baseline_conversation(stmt, problem_name=f"{args.contest}{args.index}")
        print(f"\n{'='*60}")
        print(f" Single-Agent Baseline Multi-Turn Progression ({args.contest}{args.index})")
        print(f"{'='*60}")
        for t in turns:
            print(f"\n[Level {t['hint_level']}] (Latency: {t['latency_seconds']}s):")
            print(f"  {t['hint_text']}")
        print(f"\n{'='*60}\n")
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fp:
                json.dump(turns, fp, indent=2)
        return

    stmt = args.statement or f"Problem {args.contest}{args.index} on Codeforces."
    res = generate_baseline_hint(stmt, args.level, problem_name=f"{args.contest}{args.index}")
    
    print(f"\n{'='*60}")
    print(f" Single-Agent Baseline Hint (Level {args.level})")
    print(f" Model: {res['model_name']} | Latency: {res['latency_seconds']}s")
    print(f"{'='*60}")
    print(res["hint_text"])
    print(f"{'='*60}\n")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fp:
            json.dump(res, fp, indent=2)

if __name__ == "__main__":
    main()
