"""Parent LangGraph StateGraph, conditional edges, routing, and interrupt."""
from typing import Literal, Any

from app.state import CoachState
from app.agents.analyst import analyst_node
from app.agents.tutor import tutor_node
from app.agents.keeper import keeper_node

def route_user_action(state: CoachState) -> Literal["tutor", "check_submission", "analyst", "__end__"]:
    """Route based on user action taken at the wait_for_user interrupt."""
    action = state.get("user_action")
    if action == "request_hint":
        return "tutor"
    elif action == "submitted":
        return "check_submission"
    elif action == "skip":
        return "analyst"
    elif action == "done":
        return "__end__"
    return "tutor"

def check_submission_node(state: CoachState) -> dict[str, Any]:
    """Stubbed submission checker node."""
    action_data = state.get("user_action", "")
    return {
        "history": list(state.get("history", [])) + [{
            "role": "system",
            "content": f"Submission evaluated: {action_data}"
        }]
    }

def route_submission(state: CoachState) -> Literal["analyst", "tutor"]:
    """Route after checking submission."""
    return "analyst"

def route_keeper_verdict(state: CoachState) -> Literal["tutor", "wait_for_user"]:
    """Route based on Keeper verdict and revision count."""
    verdict = state.get("verdict")
    revisions = state.get("revisions", 0)
    
    if verdict and verdict.approved:
        return "wait_for_user"
    
    if revisions < 3:
        return "tutor"
        
    return "wait_for_user"

def wait_for_user_node(state: CoachState) -> dict[str, Any]:
    """Interrupt/checkpoint node waiting for human user input."""
    return {}
