import os
import sys
import logging
from typing import Literal, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.state import CoachState
from app.agents.analyst import analyst_node
from app.agents.tutor import tutor_node
from app.agents.keeper import keeper_node
from app.agents.judge import judge_node
from app.data.cf_client import get_latest_problem_submission
from app.data.db import record_problem_submission
from app.data.stats import recalculate_user_topic_stats

logger = logging.getLogger(__name__)

ALLOWED_MSGPACK_MODULES = [
    ("app.state", "Diagnosis"),
    ("app.state", "ProblemChoice"),
    ("app.state", "HintDraft"),
    ("app.state", "HintVerdict"),
    ("app.state", "CodeSubmission"),
    ("app.state", "JudgeVerdict"),
    ("app.state", "TestCaseResult"),
    ("app.state", "TopicStat"),
    ("app.state", "TestCase"),
    ("app.state", "UserMessage")
]

def get_checkpointer(persisted: bool = False) -> Any:
    """Return memory or persistent checkpointer instance with registered Pydantic types."""
    serde = JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_MSGPACK_MODULES)
    return MemorySaver(serde=serde)

def route_user_action(state: CoachState) -> Literal["tutor", "check_submission", "judge", "analyst", "__end__"]:
    """Route based on user action taken at the wait_for_user interrupt."""
    action = state.get("user_action")
    if action in ("submit_code", "judge"):
        return "judge"
    elif action == "request_hint":
        return "tutor"
    elif action in ("submitted", "check_submission"):
        return "check_submission"
    elif action in ("skip", "skip_problem"):
        return "analyst"
    elif action == "done":
        return "__end__"
    return "tutor"

def route_judge_verdict(state: CoachState) -> Literal["analyst", "tutor", "wait_for_user"]:
    """Route based on Sandbox Judge execution outcome."""
    jv = state.get("judge_verdict")
    status = jv.status if jv else state.get("last_submission_verdict", "UNKNOWN")
    handle = state.get("handle")
    db_path = os.getenv("DATABASE_PATH", "cp_coach.db")
    
    if status == "AC":
        if handle:
            try:
                recalculate_user_topic_stats(handle, db_path=db_path)
            except Exception as e:
                logger.warning(f"Could not recalculate topic stats on judge AC: {e}")
        return "analyst"
    elif status in ("WA", "TLE", "MLE", "RE", "CE"):
        return "tutor"
    return "wait_for_user"

def check_submission_node(state: CoachState) -> dict[str, Any]:
    """Evaluate recent submission verdict, update DB records and topic stats, and append to history."""
    handle = state.get("handle")
    problem = state.get("problem")
    explicit_verdict = state.get("last_submission_verdict")
    db_path = os.getenv("DATABASE_PATH", "cp_coach.db")
    
    verdict = explicit_verdict
    
    if not verdict and handle and problem:
        try:
            sub = get_latest_problem_submission(handle, problem.contest_id, problem.index, ttl_seconds=0)
            if sub:
                verdict = sub.get("verdict", "TESTING")
            else:
                verdict = "NO_SUBMISSION_FOUND"
        except Exception as e:
            logger.warning(f"Failed to poll live Codeforces submission for {handle}: {e}")
            verdict = "NO_SUBMISSION_FOUND"
            
    if not verdict:
        verdict = "OK"

    if handle and problem:
        try:
            record_problem_submission(
                handle=handle,
                contest_id=problem.contest_id,
                idx=problem.index,
                verdict=verdict,
                problem_name=problem.name,
                problem_rating=problem.rating,
                tags=problem.tags,
                db_path=db_path
            )
        except Exception as e:
            logger.warning(f"Could not record submission in SQLite: {e}")

    history = list(state.get("history", []))
    history.append({
        "role": "system",
        "type": "submission_check",
        "verdict": verdict,
        "content": f"Submission check completed with verdict: {verdict}"
    })
    
    updates: dict[str, Any] = {
        "history": history,
        "last_submission_verdict": verdict
    }
    
    if verdict == "OK":
        if handle:
            try:
                recalculate_user_topic_stats(handle, db_path=db_path)
            except Exception as e:
                logger.warning(f"Could not recalculate topic stats: {e}")
        updates["draft"] = None
        updates["verdict"] = None
        updates["revisions"] = 0
        updates["problem"] = None
        updates["problem_statement"] = ""
    elif verdict in ("WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "MEMORY_LIMIT_EXCEEDED", "RUNTIME_ERROR", "COMPILATION_ERROR", "CHALLENGED"):
        updates["draft"] = None
        updates["verdict"] = None
        updates["revisions"] = 0
        
    return updates

def route_submission(state: CoachState) -> Literal["analyst", "tutor", "wait_for_user"]:
    """Route after checking submission: loop to analyst on AC, route to tutor on WA/TLE, or wait if pending."""
    verdict = state.get("last_submission_verdict", "OK")
    if verdict == "OK":
        return "analyst"
    elif verdict in ("NO_SUBMISSION_FOUND", "TESTING", "PENDING"):
        return "wait_for_user"
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
    
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("wait_for_user", wait_for_user_node)
    workflow.add_node("tutor", tutor_node)
    workflow.add_node("keeper", keeper_node)
    workflow.add_node("check_submission", check_submission_node)
    workflow.add_node("judge", judge_node)
    
    workflow.add_edge(START, "analyst")
    workflow.add_edge("analyst", "wait_for_user")
    
    workflow.add_conditional_edges(
        "wait_for_user",
        route_user_action,
        {
            "tutor": "tutor",
            "check_submission": "check_submission",
            "judge": "judge",
            "analyst": "analyst",
            "__end__": END,
        }
    )
    
    workflow.add_edge("tutor", "keeper")
    workflow.add_conditional_edges(
        "keeper",
        route_keeper_verdict,
        {
            "tutor": "tutor",
            "wait_for_user": "wait_for_user"
        }
    )
    
    workflow.add_conditional_edges(
        "judge",
        route_judge_verdict,
        {
            "analyst": "analyst",
            "tutor": "tutor",
            "wait_for_user": "wait_for_user"
        }
    )
    
    workflow.add_conditional_edges(
        "check_submission",
        route_submission,
        {
            "analyst": "analyst",
            "tutor": "tutor",
            "wait_for_user": "wait_for_user"
        }
    )
    
    if checkpointer is None:
        checkpointer = get_checkpointer()
        
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["wait_for_user"]
    )

def run_cli_session(handle: str = "tourist") -> None:
    """Run an interactive CLI coaching session."""
    import uuid
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    graph = create_coach_graph()
    
    print(f"\n{'='*60}")
    print(f"         🏆 CP COACH: MULTI-AGENT CP TUTORING")
    print(f"         Session Thread: {thread_id[:8]}... | User: {handle}")
    print(f"{'='*60}")
    print(f"Analyzing Codeforces profile history for '{handle}'...")
    print("⚡ Live sync & deterministic stats engine active (Rate limit: 1req/2s)...")
    
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
        "last_submission_verdict": None,
    }, config=config)
    
    while True:
        state = graph.get_state(config)
        values = state.values
        
        if not state.next:
            print("\n[Session Complete] Excellent practice! Keep up the consistency.")
            break
            
        print(f"\n{'-'*60}")
        if values.get("diagnosis"):
            d = values["diagnosis"]
            print(f"📊 Diagnosis: {d.summary}")
            
        if values.get("problem"):
            p = values["problem"]
            print(f"\n🎯 Active Problem: {p.contest_id}{p.index} - {p.name} (Rating: {p.rating})")
            print(f"🏷️  Tags: {', '.join(p.tags)}")
            print(f"💡 Why Selected: {p.reason}")
            print(f"\n📜 Statement:\n{values.get('problem_statement')}")
            
        if values.get("draft") and values.get("verdict") and values["verdict"].approved:
            draft = values["draft"]
            v = values["verdict"]
            print(f"\n💬 [Coach Hint - Level {draft.level}]:")
            print(f"   {draft.text}")
            print(f"   (Audit: {v.reason})")
            
        print(f"\n{'-'*60}")
        print("Available Actions:")
        print("  1. Request Hint Level 1 (Nudge)")
        print("  2. Request Hint Level 2 (Approach)")
        print("  3. Request Hint Level 3 (Pseudocode)")
        print("  4. 🔄 Poll live Codeforces submission (CF API)")
        print("  5. Simulate Submission -> Accepted (AC)")
        print("  6. Simulate Submission -> Wrong Answer (WA)")
        print("  7. Simulate Submission -> Time Limit Exceeded (TLE)")
        print("  8. Skip Problem")
        print("  9. Exit Session")
        
        choice = input("\nEnter choice (1-9): ").strip()
        if choice in ["1", "2", "3"]:
            lvl = int(choice)
            graph.update_state(config, {
                "user_action": "request_hint",
                "hint_level": lvl,
                "last_submission_verdict": None
            }, as_node="wait_for_user")
            graph.invoke(None, config=config)
        elif choice == "4":
            print("\n📡 Polling latest submission on Codeforces...")
            graph.update_state(config, {
                "user_action": "submitted",
                "last_submission_verdict": None
            }, as_node="wait_for_user")
            graph.invoke(None, config=config)
        elif choice == "5":
            graph.update_state(config, {
                "user_action": "submitted",
                "last_submission_verdict": "OK"
            }, as_node="wait_for_user")
            graph.invoke(None, config=config)
            print("\n✅ Submission Accepted! Loading next targeted problem...")
        elif choice == "6":
            graph.update_state(config, {
                "user_action": "submitted",
                "last_submission_verdict": "WRONG_ANSWER"
            }, as_node="wait_for_user")
            graph.invoke(None, config=config)
            print("\n❌ Verdict: Wrong Answer. Coach is preparing a targeted diagnostic hint...")
        elif choice == "7":
            graph.update_state(config, {
                "user_action": "submitted",
                "last_submission_verdict": "TIME_LIMIT_EXCEEDED"
            }, as_node="wait_for_user")
            graph.invoke(None, config=config)
            print("\n⏱️ Verdict: Time Limit Exceeded. Coach is analyzing asymptotic complexity...")
        elif choice == "8":
            graph.update_state(config, {
                "user_action": "skip",
                "last_submission_verdict": None
            }, as_node="wait_for_user")
            graph.invoke(None, config=config)
            print("\n⏭️ Problem skipped. Selecting alternative problem...")
        elif choice == "9":
            graph.update_state(config, {"user_action": "done"}, as_node="wait_for_user")
            graph.invoke(None, config=config)
            break
        else:
            print("Invalid option. Please choose 1-9.")

if __name__ == "__main__":
    h = sys.argv[1] if len(sys.argv) > 1 else "tourist"
    run_cli_session(h)
