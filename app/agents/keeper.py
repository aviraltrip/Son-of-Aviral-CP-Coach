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
