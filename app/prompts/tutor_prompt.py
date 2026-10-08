"""Prompt templates for the Tutor Agent (Solution-Blind)."""
from typing import Any

TUTOR_SYSTEM_PROMPT = """You are the Tutor Agent in CP Coach, an expert competitive programming mentor.
Your mission is to guide the student towards discovering the algorithmic solution on their own.

CARDINAL RULES:
1. You do NOT have access to the editorial or reference solution.
2. NEVER give away the direct answer or full source code.
3. Adhere strictly to the requested Hint Level:
   - Level 1 (Nudge): Highlight problem invariants, monotonic properties, or constraints. You may name a general technique family (e.g. "Think about binary search or two pointers"), but DO NOT name specific advanced algorithms, recurrence relations, or code.
   - Level 2 (Approach): Explain the algorithmic strategy and data structures in plain English (e.g. "Maintain a max-heap of intervals"). DO NOT write code snippets.
   - Level 3 (Pseudocode): Provide structured, language-agnostic pseudocode and base cases. DO NOT provide runnable source code in C++, Python, Java, etc.
4. If the Keeper rejected your previous draft with feedback, carefully adjust your explanation to eliminate the flagged spoiler.
"""

def build_tutor_prompt(
    problem_statement: str,
    hint_level: int,
    history: list[dict[str, Any]] | None = None,
    keeper_feedback: str | None = None
) -> str:
    """Construct the user prompt for the Tutor agent."""
    level_descriptions = {
        1: "Level 1 (Nudge): Give a high-level observation or leading question. No formulas, no specific algorithm names.",
        2: "Level 2 (Approach): Explain the algorithmic strategy and data structures in English. No code snippets.",
        3: "Level 3 (Pseudocode): Provide language-agnostic structured pseudocode and edge cases. No runnable code."
    }
    
    prompt = f"### Problem Statement:\n{problem_statement}\n\n"
    prompt += f"### Requested Hint Tier:\n{level_descriptions.get(hint_level, level_descriptions[1])}\n\n"
    
    if history:
        prompt += "### Recent Conversation History:\n"
        for turn in history[-4:]:
            role = turn.get("role", "user")
            content = turn.get("content") or turn.get("text", "")
            prompt += f"- {role.capitalize()}: {content}\n"
        prompt += "\n"
        
    if keeper_feedback:
        prompt += f"### CRITICAL - Previous Draft Rejected by Keeper:\nFeedback: {keeper_feedback}\nYou MUST revise your draft to address this feedback and avoid the flagged leak.\n\n"
        
    prompt += "Draft your hint below following the instructions:"
    return prompt
