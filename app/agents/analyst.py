"""Analyst agent stub: responsible for weak topic analysis and problem selection."""
from typing import Any
from app.state import CoachState, Diagnosis, TopicStat, ProblemChoice

def analyst_node(state: CoachState) -> dict[str, Any]:
    """Analyze handle history (stubbed for Phase 1) and recommend a problem."""
    handle = state.get("handle", "user")
    
    weak_topics = [
        TopicStat(tag="dp", solved_ratio=0.35, avg_rating=1450.0, n_attempts=20, weighted_failure_score=0.65),
        TopicStat(tag="graphs", solved_ratio=0.45, avg_rating=1500.0, n_attempts=15, weighted_failure_score=0.55),
        TopicStat(tag="binary search", solved_ratio=0.50, avg_rating=1400.0, n_attempts=10, weighted_failure_score=0.50),
    ]
    
    diagnosis = Diagnosis(
        weak_topics=weak_topics,
        summary=f"Analysis for {handle}: Highest failure rates in Dynamic Programming (35% solve rate) and Graphs (45% solve rate). Target practice around 1500-1600 rating.",
        user_rating=1420
    )
    
    problem = ProblemChoice(
        contest_id=1900,
        index="C",
        name="Anji's Binary Tree",
        rating=1500,
        tags=["dp", "trees", "dfs and similar"],
        reason="Targeted 1500-rated Dynamic Programming on Trees problem matching your primary weak area."
    )
    
    problem_statement = (
        "Problem 1900C: Anji's Binary Tree (Rating: 1500)\n"
        "You are given a binary tree with n vertices labeled from 1 to n. Vertex 1 is the root.\n"
        "Each vertex has a letter 'L', 'R', or 'U' written on it.\n"
        "Find the minimum number of letters you need to change so that there is a path from the root to some leaf."
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
    }
