"""Analyst agent node: syncs Codeforces data, runs stats engine, and picks next problem."""
import os
import logging
from typing import Any

from app.state import CoachState, Diagnosis, TopicStat, ProblemChoice
from app.data.db import (
    get_user,
    get_user_submissions,
    get_candidate_problems,
    get_attempted_problem_keys,
    save_topic_stats
)
from app.data.cf_client import sync_user_data, CFAPIError
from app.data.stats import compute_weak_topics, select_next_problem

logger = logging.getLogger(__name__)

SAMPLE_PROBLEMS_FALLBACK = [
    {"contest_id": 1900, "idx": "C", "name": "Anji's Binary Tree", "rating": 1500, "tags": ["dp", "trees", "dfs and similar"]},
    {"contest_id": 1850, "idx": "E", "name": "Cardboard for Pictures", "rating": 1100, "tags": ["binary search", "math"]},
    {"contest_id": 1840, "idx": "D", "name": "Wooden Toy Festival", "rating": 1400, "tags": ["binary search", "greedy", "sortings"]},
    {"contest_id": 1833, "idx": "E", "name": "Round Dance", "rating": 1600, "tags": ["graphs", "dsu", "dfs and similar"]},
    {"contest_id": 1800, "idx": "E2", "name": "Unforgivable Curse", "rating": 1400, "tags": ["dsu", "strings", "greedy"]},
]
