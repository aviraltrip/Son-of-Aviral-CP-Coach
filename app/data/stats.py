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

def apply_bayesian_shrinkage(raw_score: float, n_attempts: int, global_mean: float = 0.5, prior_weight: float = 5.0) -> float:
    """Smooth raw failure score toward global mean when attempt sample size is small."""
    if n_attempts <= 0:
        return global_mean
    return (n_attempts * raw_score + prior_weight * global_mean) / (n_attempts + prior_weight)

def aggregate_tag_statistics(submissions: list[dict[str, Any]], user_rating: int | None, current_ts: int | None = None) -> dict[str, dict[str, Any]]:
    """Aggregate per-tag attempt metrics, weighted failures, and solve counts."""
    tag_data: dict[str, dict[str, Any]] = {}
    
    for s in submissions:
        tags = s.get("tags", [])
        verdict = s.get("verdict", "")
        p_rating = s.get("problem_rating") or s.get("rating")
        ts = s.get("creation_time_seconds") or s.get("creationTimeSeconds", int(time.time()))
        
        is_ac = (verdict == "OK")
        recency = compute_recency_decay(ts, current_ts)
        difficulty = compute_difficulty_weight(p_rating, user_rating)
        weight = recency * difficulty
        
        for t in tags:
            if t not in tag_data:
                tag_data[t] = {
                    "total_attempts": 0,
                    "total_accepted": 0,
                    "weighted_attempts": 0.0,
                    "weighted_failures": 0.0,
                    "solved_ratings": []
                }
            tag_data[t]["total_attempts"] += 1
            tag_data[t]["weighted_attempts"] += weight
            if is_ac:
                tag_data[t]["total_accepted"] += 1
                if p_rating:
                    tag_data[t]["solved_ratings"].append(p_rating)
            else:
                tag_data[t]["weighted_failures"] += weight
                
    return tag_data
