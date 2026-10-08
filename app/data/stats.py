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

def compute_weak_topics(submissions: list[dict[str, Any]], user_rating: int | None, min_attempts: int = 2) -> list[TopicStat]:
    """Compute ranked list of weak algorithm topics based on weighted failure rate & shrinkage."""
    if not submissions:
        return []
        
    tag_data = aggregate_tag_statistics(submissions, user_rating)
    if not tag_data:
        return []
        
    total_w_attempts = sum(d["weighted_attempts"] for d in tag_data.values())
    total_w_failures = sum(d["weighted_failures"] for d in tag_data.values())
    global_failure_rate = (total_w_failures / total_w_attempts) if total_w_attempts > 0 else 0.5
    
    topic_stats: list[TopicStat] = []
    for tag, d in tag_data.items():
        n = d["total_attempts"]
        if n < min_attempts:
            continue
            
        raw_wfr = (d["weighted_failures"] / d["weighted_attempts"]) if d["weighted_attempts"] > 0 else 0.5
        adj_score = apply_bayesian_shrinkage(raw_wfr, n, global_mean=global_failure_rate, prior_weight=5.0)
        solved_ratio = (d["total_accepted"] / n) if n > 0 else 0.0
        avg_rating = (sum(d["solved_ratings"]) / len(d["solved_ratings"])) if d["solved_ratings"] else None
        
        topic_stats.append(TopicStat(
            tag=tag,
            solved_ratio=round(solved_ratio, 3),
            avg_rating=round(avg_rating, 1) if avg_rating else None,
            n_attempts=n,
            weighted_failure_score=round(adj_score, 4)
        ))
        
    topic_stats.sort(key=lambda t: t.weighted_failure_score, reverse=True)
    return topic_stats

def select_next_problem(
    user_handle: str,
    user_rating: int | None,
    weak_topics: list[TopicStat],
    candidate_problems: list[dict[str, Any]],
    attempted_keys: set[tuple[int, str]] | None = None
) -> ProblemChoice:
    """Select next optimal practice problem matching top weak topics in user target rating window."""
    attempted = attempted_keys or set()
    rating = user_rating or 1400
    target_min = rating + 100
    target_max = rating + 200
    
    top_tags = [t.tag for t in weak_topics[:3]] if weak_topics else ["dp", "greedy", "graphs"]
    
    for p in candidate_problems:
        cid = p.get("contest_id") or p.get("contestId")
        idx = p.get("idx") or p.get("index")
        prating = p.get("rating")
        tags = p.get("tags", [])
        
        if (cid, idx) in attempted:
            continue
            
        if prating and target_min <= prating <= target_max:
            matching = [t for t in top_tags if t in tags]
            if matching:
                return ProblemChoice(
                    contest_id=cid,
                    index=idx,
                    name=p.get("name", f"Problem {cid}{idx}"),
                    rating=prating,
                    tags=tags,
                    reason=f"Targeted {prating}-rated problem matching weak topic '{matching[0]}' (Rating target: {target_min}-{target_max})."
                )

    for p in candidate_problems:
        cid = p.get("contest_id") or p.get("contestId")
        idx = p.get("idx") or p.get("index")
        prating = p.get("rating")
        tags = p.get("tags", [])
        
        if (cid, idx) in attempted:
            continue
            
        matching = [t for t in top_tags if t in tags]
        if matching:
            return ProblemChoice(
                contest_id=cid,
                index=idx,
                name=p.get("name", f"Problem {cid}{idx}"),
                rating=prating,
                tags=tags,
                reason=f"Practice problem for weak topic '{matching[0]}'."
            )

    return ProblemChoice(
        contest_id=1900,
        index="C",
        name="Anji's Binary Tree",
        rating=1500,
        tags=["dp", "trees"],
        reason="Default recommended tree dynamic programming problem."
    )
