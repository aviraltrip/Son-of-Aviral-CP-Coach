"""Deterministic scoring, exponential decay, shrinkage, and problem recommendation engine."""
import math
import time
from typing import Any
from app.state import TopicStat, ProblemChoice

HALF_LIFE_DAYS = 30.0
HALF_LIFE_SECONDS = HALF_LIFE_DAYS * 86400.0
LN_2 = math.log(2)

def compute_recency_decay(submission_ts: int, current_ts: int | None = None) -> float:
    """Compute exponential decay weight with a 30-day half-life: r_i = exp(-delta_t * ln(2) / T_half)."""
    if current_ts is None:
        current_ts = int(time.time())
    delta_t = max(0, current_ts - submission_ts)
    return math.exp(- (delta_t * LN_2) / HALF_LIFE_SECONDS)

def compute_difficulty_weight(problem_rating: int | None, user_rating: int | None) -> float:
    """Compute difficulty weight: d_i = max(0.5, problem_rating / user_rating)."""
    if not problem_rating or not user_rating or user_rating <= 0:
        return 1.0
    return max(0.5, float(problem_rating) / float(user_rating))
