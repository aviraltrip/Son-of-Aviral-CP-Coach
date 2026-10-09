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
from app.data.stats import compute_weak_topics, select_next_problem, is_valid_algorithmic_tag

logger = logging.getLogger(__name__)

SAMPLE_PROBLEMS_FALLBACK = [
    {"contest_id": 1900, "idx": "C", "name": "Anji's Binary Tree", "rating": 1500, "tags": ["dp", "trees", "dfs and similar"]},
    {"contest_id": 1850, "idx": "E", "name": "Cardboard for Pictures", "rating": 1100, "tags": ["binary search", "math"]},
    {"contest_id": 1840, "idx": "D", "name": "Wooden Toy Festival", "rating": 1400, "tags": ["binary search", "greedy", "sortings"]},
    {"contest_id": 1833, "idx": "E", "name": "Round Dance", "rating": 1600, "tags": ["graphs", "dsu", "dfs and similar"]},
    {"contest_id": 1800, "idx": "E2", "name": "Unforgivable Curse", "rating": 1400, "tags": ["dsu", "strings", "greedy"]},
]

def format_diagnostic_summary(handle: str, user_rating: int | None, weak_topics: list[TopicStat]) -> str:
    """Format a clear diagnostic summary based on computed stats, focusing strictly on algorithmic tags."""
    rating_str = f"rated {user_rating}" if user_rating else "unrated"
    valid_weak = [t for t in weak_topics if is_valid_algorithmic_tag(t.tag)]
    if not valid_weak:
        return f"Diagnostics for {handle} ({rating_str}): Profile synced. Recommended a baseline practice problem to assess initial performance."
        
    top_two = [f"{t.tag} ({int(t.solved_ratio*100)}% solve rate, {t.n_attempts} attempts)" for t in valid_weak[:2]]
    return f"Diagnostics for {handle} ({rating_str}): Primary weak areas identified in {', '.join(top_two)}. Recommended problem targets your weak areas in your optimal rating range."

def analyst_node(state: CoachState) -> dict[str, Any]:
    """Execute live data analysis, update SQLite cache, compute weak topics, and select next problem."""
    handle = state.get("handle", "tourist").strip()
    db_path = os.getenv("DATABASE_PATH", "cp_coach.db")
    
    try:
        user_info, _ = sync_user_data(handle, max_submissions=300, db_path=db_path)
        user_rating = user_info.get("rating")
    except Exception as e:
        logger.warning(f"Could not sync live CF data for {handle}: {e}. Utilizing cached data.")
        cached_user = get_user(handle, db_path=db_path)
        user_rating = cached_user["current_rating"] if cached_user else 1400

    submissions = get_user_submissions(handle, limit=300, db_path=db_path)
    weak_topics = compute_weak_topics(submissions, user_rating=user_rating, min_attempts=2)
    
    if weak_topics:
        save_topic_stats(handle, [t.model_dump() for t in weak_topics], db_path=db_path)
        
    rating = user_rating or 1400
    candidates = get_candidate_problems(rating, rating + 300, db_path=db_path)
    if not candidates:
        candidates = SAMPLE_PROBLEMS_FALLBACK
        
    attempted = get_attempted_problem_keys(handle, db_path=db_path)
    problem = select_next_problem(handle, user_rating, weak_topics, candidates, attempted_keys=attempted)
    
    summary = format_diagnostic_summary(handle, user_rating, weak_topics)
    diagnosis = Diagnosis(
        weak_topics=weak_topics,
        summary=summary,
        user_rating=user_rating
    )
    
    problem_statement = (
        f"Problem {problem.contest_id}{problem.index}: {problem.name} (Rating: {problem.rating or 'Unrated'})\n"
        f"Tags: {', '.join(problem.tags)}\n\n"
        f"You are tasked with finding an optimal algorithm matching time and memory constraints.\n"
        f"Target Topic: {problem.tags[0] if problem.tags else 'general algorithmic reasoning'}"
    )
    
    return {
        "diagnosis": diagnosis,
        "problem": problem,
        "problem_statement": problem_statement,
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "user_action": None,
        "last_submission_verdict": None
    }
