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

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

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
    
    # Submission routing
    workflow.add_conditional_edges(
        "check_submission",
        route_submission,
        {
            "analyst": "analyst",
            "tutor": "tutor"
        }
    )
    
    if checkpointer is None:
        checkpointer = MemorySaver()
        
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["wait_for_user"]
    )

import sys

def run_cli_session(handle: str = "tourist") -> None:
    """Run an interactive CLI coaching session."""
    import uuid
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    graph = create_coach_graph()
    
    print(f"\n================ CP COACH CLI ================")
    print(f"Initializing coaching session for handle: {handle}...")
    
    # Initial state
    graph.invoke({
        "handle": handle,
        "diagnosis": None,
        "problem": None,
        "problem_statement": "",
        "hint_level": 1,
        "draft": None,
        "verdict": None,
        "revisions": 0,
        "history": [],
        "user_action": None,
    }, config=config)
    
    while True:
        state = graph.get_state(config)
        values = state.values
        
        if not state.next:
            print("\nSession ended. Great practice!")
            break
            
        print("\n" + "="*50)
        if values.get("problem"):
            p = values["problem"]
            print(f"Problem: {p.contest_id}{p.index} - {p.name} (Rating: {p.rating})")
            print(f"Tags: {', '.join(p.tags)}")
            print(f"Reason: {p.reason}")
            print(f"\nStatement:\n{values.get('problem_statement')}")
            
        if values.get("draft") and values.get("verdict") and values["verdict"].approved:
            print(f"\n[Hint Level {values['draft'].level}]:\n{values['draft'].text}")
            
        print("\nOptions:")
        print("1. Request Hint Level 1 (Nudge)")
        print("2. Request Hint Level 2 (Approach)")
        print("3. Request Hint Level 3 (Pseudocode)")
        print("4. Submit solution (check verdict)")
        print("5. Skip problem")
        print("6. Exit")
        
        choice = input("\nEnter choice (1-6): ").strip()
        if choice in ["1", "2", "3"]:
            lvl = int(choice)
            graph.update_state(config, {"user_action": "request_hint", "hint_level": lvl}, as_node="wait_for_user")
            graph.invoke(None, config=config)
        elif choice == "4":
            graph.update_state(config, {"user_action": "submitted"}, as_node="wait_for_user")
            graph.invoke(None, config=config)
            print("\nChecked submission -> Solved! Loading next problem...")
        elif choice == "5":
            graph.update_state(config, {"user_action": "skip"}, as_node="wait_for_user")
            graph.invoke(None, config=config)
        elif choice == "6":
            graph.update_state(config, {"user_action": "done"}, as_node="wait_for_user")
            graph.invoke(None, config=config)
            break
        else:
            print("Invalid option. Please choose 1-6.")

if __name__ == "__main__":
    h = sys.argv[1] if len(sys.argv) > 1 else "tourist"
    run_cli_session(h)
