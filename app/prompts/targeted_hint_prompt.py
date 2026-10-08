"""Prompt templates for targeted error diagnostics on WA/TLE/MLE."""
from typing import Any

TARGETED_HINT_SYSTEM_PROMPT = """You are the Tutor Agent diagnosing a student's submission failure.
Your goal is to point out common algorithmic pitfalls, edge cases, or complexity bounds without spoiling the full solution.
"""

def build_targeted_hint_prompt(
    problem_statement: str,
    verdict: str,
    history: list[dict[str, Any]] | None = None
) -> str:
    """Construct prompt for targeted error diagnostics."""
    prompt = f"### Problem Statement:\n{problem_statement}\n\n"
    prompt += f"### Submission Verdict: {verdict}\n\n"
    prompt += (
        "Provide a targeted 2-4 sentence diagnostic hint helping the student debug this specific issue "
        "(e.g. integer overflow, edge cases like n=1, single-child trees, or asymptotic complexity bottleneck) "
        "without revealing the full code or solution."
    )
    return prompt
