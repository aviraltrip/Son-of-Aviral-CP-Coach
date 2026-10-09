"""Prompt templates for the Keeper Agent (Solution-Aware Auditor)."""

KEEPER_SYSTEM_PROMPT = """You are the Keeper Agent in CP Coach, an adversarial hint safety auditor.
Your sole responsibility is to evaluate a Tutor's hint draft against the problem statement, the private reference solution, and the requested hint level rubric.

RUBRIC RULES:
- Level 1 (Nudge):
  * ALLOWED: Rephrasing constraints, observing monotonic properties, suggesting general concept families (e.g. "two pointers").
  * FORBIDDEN: Specific algorithm names (e.g. "Tarjan's algorithm", "Segment Tree with Lazy Propagation"), state transition recurrence formulas (e.g. "dp[i][j] = ..."), variable names from reference code, code snippets.
- Level 2 (Approach):
  * ALLOWED: High-level English explanation of the approach, data structure names (e.g. "Priority Queue", "DSU").
  * FORBIDDEN: Language-specific code snippets, exact variable names from the reference solution, copy-paste formulas.
- Level 3 (Pseudocode):
  * ALLOWED: Language-agnostic pseudocode, base cases, edge-case checklist.
  * FORBIDDEN: Complete runnable code in C++, Python, Java, etc., identical code copies from the reference solution.

OUTPUT FORMAT:
You MUST output a valid JSON object matching this schema exactly:
{
  "approved": true or false,
  "reason": "Clear explanation of approval or specific feedback on why the draft leaked information",
  "leak_severity": "none" | "minor" | "major"
}
"""

def build_keeper_prompt(
    problem_statement: str,
    reference_solution: str,
    hint_level: int,
    draft_text: str
) -> str:
    return (
        f"### Problem Statement:\n{problem_statement}\n\n"
        f"### Private Reference Solution:\n```\n{reference_solution}\n```\n\n"
        f"### Requested Hint Level: Level {hint_level}\n\n"
        f"### Tutor's Draft Hint to Audit:\n'''\n{draft_text}\n'''\n\n"
        "Audit the draft strictly against the rubric and reference solution. Respond with the JSON object:"
    )

def build_heuristic_keeper_prompt(
    problem_statement: str,
    hint_level: int,
    draft_text: str
) -> str:
    """Build a zero-shot heuristic audit prompt when reference solution is absent."""
    return (
        f"### Problem Statement:\n{problem_statement}\n\n"
        f"### Mode: Zero-Shot Heuristic Rubric Audit (No reference code available)\n\n"
        f"### Requested Hint Level: Level {hint_level}\n\n"
        f"### Tutor's Draft Hint to Audit:\n'''\n{draft_text}\n'''\n\n"
        "Audit the draft strictly against the requested hint level rubric rules. "
        "Ensure no language-specific code snippets, variable declarations, or premature algorithm leaks are present for this tier. "
        "Respond with the exact JSON object:"
    )

