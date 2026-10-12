"""Unit tests for deterministic scoring and decay formulas in app/data/stats.py."""
import pytest
import time
from app.data.stats import (
    compute_recency_decay,
    compute_difficulty_weight,
    apply_bayesian_shrinkage,
    compute_weak_topics,
    select_next_problem
)

def test_exponential_decay_half_life():
    now = 10000000
    past_30d = now - int(30 * 86400)
    decay_30d = compute_recency_decay(past_30d, current_ts=now)
    assert abs(decay_30d - 0.5) < 1e-4
    assert abs(compute_recency_decay(now, current_ts=now) - 1.0) < 1e-6

def test_difficulty_weight():
    assert compute_difficulty_weight(1400, 1400) == 1.0
    assert abs(compute_difficulty_weight(1680, 1400) - 1.2) < 1e-4
    assert compute_difficulty_weight(500, 1400) == 0.5

def test_bayesian_shrinkage():
    assert apply_bayesian_shrinkage(0.9, 0, global_mean=0.5, prior_weight=5) == 0.5
    assert apply_bayesian_shrinkage(1.0, 5, global_mean=0.5, prior_weight=5) == 0.75

def test_compute_weak_topics():
    now = int(time.time())
    submissions = [
        {"tags": ["dp"], "verdict": "WRONG_ANSWER", "problem_rating": 1500, "creation_time_seconds": now},
        {"tags": ["dp"], "verdict": "WRONG_ANSWER", "problem_rating": 1500, "creation_time_seconds": now},
        {"tags": ["dp"], "verdict": "OK", "problem_rating": 1500, "creation_time_seconds": now},
        {"tags": ["greedy"], "verdict": "OK", "problem_rating": 1200, "creation_time_seconds": now},
        {"tags": ["greedy"], "verdict": "OK", "problem_rating": 1200, "creation_time_seconds": now},
    ]
    
    weak = compute_weak_topics(submissions, user_rating=1400, min_attempts=2)
    assert len(weak) == 2
    assert weak[0].tag == "dp"
    assert weak[0].weighted_failure_score > weak[1].weighted_failure_score

def test_select_next_problem():
    candidates = [
        {"contest_id": 1900, "idx": "A", "name": "Greedy Easy", "rating": 1200, "tags": ["greedy"]},
        {"contest_id": 1900, "idx": "C", "name": "Tree DP Target", "rating": 1550, "tags": ["dp", "trees"]},
    ]
    from app.state import TopicStat
    weak = [TopicStat(tag="dp", solved_ratio=0.33, avg_rating=1500.0, n_attempts=3, weighted_failure_score=0.7)]
    
    choice = select_next_problem("tourist", user_rating=1400, weak_topics=weak, candidate_problems=candidates)
    assert choice.contest_id == 1900
    assert choice.index == "C"
    assert choice.rating == 1550

def test_non_algorithmic_tags_are_filtered_from_weak_topics():
    from app.data.stats import is_valid_algorithmic_tag
    assert not is_valid_algorithmic_tag("*special")
    assert not is_valid_algorithmic_tag("special problem")
    assert not is_valid_algorithmic_tag("interactive")
    assert not is_valid_algorithmic_tag("combine tags by or")
    assert is_valid_algorithmic_tag("dp")
    assert is_valid_algorithmic_tag("trees")
    assert is_valid_algorithmic_tag("graphs")

    now = int(time.time())
    submissions = [
        {"tags": ["*special", "special problem", "interactive"], "verdict": "WRONG_ANSWER", "problem_rating": 1500, "creation_time_seconds": now},
        {"tags": ["*special", "interactive"], "verdict": "WRONG_ANSWER", "problem_rating": 1500, "creation_time_seconds": now},
        {"tags": ["dp"], "verdict": "WRONG_ANSWER", "problem_rating": 1500, "creation_time_seconds": now},
        {"tags": ["dp"], "verdict": "WRONG_ANSWER", "problem_rating": 1500, "creation_time_seconds": now},
    ]
    
    weak = compute_weak_topics(submissions, user_rating=1400, min_attempts=2)
    tags_in_weak = [t.tag for t in weak]
    assert "*special" not in tags_in_weak
    assert "special problem" not in tags_in_weak
    assert "interactive" not in tags_in_weak
    assert "dp" in tags_in_weak

def test_aggregate_tag_statistics_with_whitespace_tags():
    from app.data.stats import aggregate_tag_statistics
    submissions = [
        {"tags": [" dp ", "  trees"], "verdict": "OK", "problem_rating": 1500, "creation_time_seconds": int(time.time())},
        {"tags": ["dp", "trees "], "verdict": "WRONG_ANSWER", "problem_rating": 1500, "creation_time_seconds": int(time.time())}
    ]
    tag_data = aggregate_tag_statistics(submissions, user_rating=1400)
    assert "dp" in tag_data
    assert "trees" in tag_data
    assert tag_data["dp"]["total_attempts"] == 2
    assert tag_data["trees"]["total_attempts"] == 2

