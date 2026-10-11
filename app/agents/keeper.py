"""Keeper agent: audits hint drafts against reference solutions and rubric."""
import os
import json
import logging
from typing import Any

from app.state import CoachState, HintVerdict
from app.data.db import get_reference_solution, save_reference_solution, save_cached_hint
from app.prompts.keeper_prompt import KEEPER_SYSTEM_PROMPT, build_keeper_prompt, build_heuristic_keeper_prompt
from app.agents.llm import get_llm

logger = logging.getLogger(__name__)

SAFE_FALLBACK_HINT = (
    "Safe Guidance: Consider simplifying the problem constraints and simulating the process on a small example tree."
)

DEFAULT_REFERENCE_SOLUTION = """
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

def keeper_node(state: CoachState) -> dict[str, Any]:
    """Audit the tutor's hint draft against private reference solution or zero-shot heuristic rubric."""
    draft = state.get("draft")
    revisions = state.get("revisions", 0)
    level = state.get("hint_level", 1)
    problem = state.get("problem")
    problem_stmt = state.get("problem_statement", "")
    db_path = os.getenv("DATABASE_PATH", "cp_coach.db")
    
    if not draft:
        return {
            "verdict": HintVerdict(approved=False, reason="No draft provided", leak_severity="minor"),
            "revisions": revisions + 1
        }
        
    cid = problem.contest_id if problem else 1900
    idx = problem.index if problem else "C"
    
    ref = get_reference_solution(cid, idx, db_path=db_path)
    has_ref = bool(ref and ref.get("solution_code") and ref["solution_code"].strip() != DEFAULT_REFERENCE_SOLUTION.strip())
    
    if has_ref and ref is not None:
        reference_code = ref["solution_code"]
        prompt = build_keeper_prompt(problem_stmt, reference_code, level, draft.text)
        logger.info(f"[Keeper] Auditing Problem {cid}{idx} with Solution-Aware Mode.")
    else:
        prompt = build_heuristic_keeper_prompt(problem_stmt, level, draft.text)
        logger.info(f"[Keeper] Auditing Problem {cid}{idx} with Zero-Shot Heuristic Rubric Mode.")
    
    llm = get_llm(model_type="keeper")
    
    try:
        resp = llm.invoke([
            {"role": "system", "content": KEEPER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ])
        raw_text = resp.content if hasattr(resp, "content") else str(resp)
        verdict = parse_keeper_verdict(raw_text, level)
    except Exception as e:
        logger.warning(f"Keeper audit LLM call failed: {e}. Applying rule-based check.")
        if level == 1 and "dp[" in draft.text:
            verdict = HintVerdict(approved=False, reason="Leaked DP recurrence at Level 1.", leak_severity="major")
        else:
            verdict = HintVerdict(approved=True, reason="Rule-based approval.", leak_severity="none")

    new_revisions = revisions if verdict.approved else revisions + 1
    updates: dict[str, Any] = {
        "verdict": verdict,
        "revisions": new_revisions
    }
    
    if not verdict.approved and new_revisions >= 3:
        draft.text = SAFE_FALLBACK_HINT
        verdict.approved = True
        verdict.reason = "Approved via Safe Generic Fallback (Max 3 revisions reached)."
        updates["draft"] = draft
        updates["verdict"] = verdict

    if verdict.approved and draft and draft.text:
        try:
            save_cached_hint(cid, idx, level, draft.text, db_path=db_path)
        except Exception as e:
            logger.debug(f"Could not cache approved hint: {e}")
        
    return updates
