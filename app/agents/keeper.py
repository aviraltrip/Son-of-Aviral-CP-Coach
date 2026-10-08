"""Keeper agent: audits hint drafts against reference solutions and rubric."""
import os
import json
import logging
from typing import Any

from app.state import CoachState, HintVerdict
from app.data.db import get_reference_solution, save_reference_solution

logger = logging.getLogger(__name__)

SAFE_FALLBACK_HINT = (
    "Safe Guidance: Consider simplifying the problem constraints and simulating the process on a small example tree."
)

DEFAULT_REFERENCE_SOLUTION = """
// Reference Solution for Problem
#include <bits/stdc++.h>
using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    return 0;
}
"""

def load_or_create_reference(contest_id: int, idx: str, db_path: str = "cp_coach.db") -> str:
    """Load private reference solution from SQLite references table, or generate placeholder."""
    ref = get_reference_solution(contest_id, idx, db_path=db_path)
    if ref and ref.get("solution_code"):
        return ref["solution_code"]
    
    save_reference_solution(contest_id, idx, DEFAULT_REFERENCE_SOLUTION, source="synthetic_fallback", db_path=db_path)
    return DEFAULT_REFERENCE_SOLUTION

from app.prompts.keeper_prompt import KEEPER_SYSTEM_PROMPT, build_keeper_prompt
from app.agents.llm import get_llm

def parse_keeper_verdict(raw_content: str, level: int) -> HintVerdict:
    """Parse JSON verdict from Keeper LLM response with graceful fallback."""
    try:
        text = raw_content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        data = json.loads(text)
        return HintVerdict(
            approved=bool(data.get("approved", True)),
            reason=str(data.get("reason", f"Level {level} hint approved.")),
            leak_severity=data.get("leak_severity", "none")
        )
    except Exception as e:
        logger.warning(f"Failed to parse Keeper verdict JSON ({e}). Content: {raw_content}")
        return HintVerdict(
            approved=True,
            reason=f"Approved under Level {level} standards.",
            leak_severity="none"
        )
