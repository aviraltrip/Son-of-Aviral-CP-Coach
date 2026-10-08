"""Single-Agent Baseline for competitive programming hints (Experimental Control).

Directly prompts a single LLM to generate hints at requested levels (1-3)
without a solution-aware Keeper agent auditing for leakage.
"""
import time
import logging
from typing import Any

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
