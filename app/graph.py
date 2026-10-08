"""Parent LangGraph StateGraph, conditional edges, routing, and interrupt."""
import sys
from typing import Literal, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import CoachState
from app.agents.analyst import analyst_node
from app.agents.tutor import tutor_node
from app.agents.keeper import keeper_node

def get_checkpointer(persisted: bool = False) -> Any:
    """Return memory or persistent checkpointer instance."""
    return MemorySaver()

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
    """Evaluate recent submission verdict and update history."""
    verdict = state.get("last_submission_verdict", "OK")
    history = list(state.get("history", []))
    history.append({
        "role": "system",
        "type": "submission_check",
        "verdict": verdict,
        "content": f"Submission check completed with verdict: {verdict}"
    })
    
    updates: dict[str, Any] = {"history": history}
    if verdict == "OK":
        updates["draft"] = None
        updates["verdict"] = None
        updates["revisions"] = 0
    return updates

def route_submission(state: CoachState) -> Literal["analyst", "tutor"]:
    """Route after checking submission: loop to analyst on AC, route to tutor on WA/TLE."""
    verdict = state.get("last_submission_verdict", "OK")
    if verdict == "OK":
        return "analyst"
    return "tutor"

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

def create_coach_graph(checkpointer: Any = None) -> Any:
    """Build and compile the CP Coach LangGraph state machine."""
    workflow = StateGraph(CoachState)
    
    # Add Nodes
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("wait_for_user", wait_for_user_node)
    workflow.add_node("tutor", tutor_node)
    workflow.add_node("keeper", keeper_node)
    workflow.add_node("check_submission", check_submission_node)
    
    # Flow Edges
    workflow.add_edge(START, "analyst")
    workflow.add_edge("analyst", "wait_for_user")
    
    # User interaction routing
    workflow.add_conditional_edges(
        "wait_for_user",
        route_user_action,
        {
            "tutor": "tutor",
            "check_submission": "check_submission",
            "analyst": "analyst",
            "__end__": END,
        }
    )
    
    # Tutor ⇄ Keeper verification loop
    workflow.add_edge("tutor", "keeper")
    workflow.add_conditional_edges(
        "keeper",
        route_keeper_verdict,
        {
            "tutor": "tutor",
            "wait_for_user": "wait_for_user"
        }
    )
    
    # Submission routing: AC -> analyst | WA/TLE -> tutor (targeted hint)
    workflow.add_conditional_edges(
        "check_submission",
        route_submission,
        {
            "analyst": "analyst",
            "tutor": "tutor"
        }
    )
    
    if checkpointer is None:
        checkpointer = get_checkpointer()
        
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["wait_for_user"]
    )
