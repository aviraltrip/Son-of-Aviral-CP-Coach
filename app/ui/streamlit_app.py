"""Streamlit Web Application for CP Coach.

Multi-Agent Competitive Programming Coach with live Codeforces history sync,
deterministic algorithmic diagnostics, tailored recommendations, and verified 3-tier hints.
Clean UI without icons or emojis.
"""
import os
import sys
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

from app.logging_config import setup_logging
setup_logging()

from app.graph import create_coach_graph
from app.state import CodeSubmission
from app.ui.components import (
    inject_custom_css,
    get_rank_badge,
    render_tag_chips,
    render_weak_topics_summary,
    render_problem_card,
    render_hint_box,
    render_agent_trace,
    render_judge_verdict_banner,
    render_fuzz_result_banner,
    STARTER_TEMPLATES
)
from app.judge.fuzzer import stress_test_problem_submission
from app.judge.runner import get_active_judge_backend
from app.data.db import get_user, get_user_topic_stats
from app.data.cf_client import sync_user_data
from app.data.rate_limiter import rate_limiter

MAX_SOURCE_BYTES: int = 64 * 1024  # 64 KB (standard competitive programming limit)

def init_session_state() -> None:
    """Initialize LangGraph state machine and UI session values with persistent checkpointing."""
    query_thread = st.query_params.get("thread_id")
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = query_thread if query_thread else str(uuid.uuid4())
        st.query_params["thread_id"] = st.session_state.thread_id
        
    if "graph" not in st.session_state:
        st.session_state.graph = create_coach_graph(persisted=True)
        
    if "config" not in st.session_state:
        st.session_state.config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
    if "handle" not in st.session_state:
        st.session_state.handle = "tourist"
        
    if "user_info" not in st.session_state:
        st.session_state.user_info = None
        
    if "initialized" not in st.session_state:
        st.session_state.initialized = False

    if "code_lang" not in st.session_state:
        st.session_state.code_lang = "cpp"

    if "user_code" not in st.session_state:
        st.session_state.user_code = STARTER_TEMPLATES["cpp"]

    if "fuzz_result" not in st.session_state:
        st.session_state.fuzz_result = None

def render_sidebar() -> str:
    """Render sidebar with user handle settings, sync actions, and profile stats."""
    with st.sidebar:
        st.markdown("### User Profile")
        handle_input = st.text_input("Codeforces Handle", value=st.session_state.handle, help="Enter your Codeforces username.")
        
        col_sync, col_reset = st.columns(2)
        sync_clicked = col_sync.button("Sync CF", use_container_width=True)
        reset_clicked = col_reset.button("Reset", use_container_width=True)
        
        if reset_clicked:
            new_thread = str(uuid.uuid4())
            st.session_state.thread_id = new_thread
            st.query_params["thread_id"] = new_thread
            st.session_state.config = {"configurable": {"thread_id": new_thread}}
            st.session_state.initialized = False
            st.session_state.graph = create_coach_graph(persisted=True)
            st.rerun()

        if sync_clicked:
            st.session_state.handle = handle_input.strip()
            with st.spinner(f"Syncing profile & submissions for '{st.session_state.handle}'..."):
                try:
                    uinfo, count = sync_user_data(st.session_state.handle, max_submissions=300, ttl_seconds=0)
                    st.session_state.user_info = uinfo
                    st.toast(f"Synced {count} submissions from Codeforces!")
                except Exception as e:
                    st.warning(f"Could not reach CF API ({e}). Using local database cache.")
                    st.session_state.user_info = get_user(st.session_state.handle) or {"handle": st.session_state.handle, "current_rating": 1400}

            st.session_state.graph.invoke({
                "handle": st.session_state.handle,
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
            }, config=st.session_state.config)
            st.session_state.initialized = True
            st.rerun()

        elif not st.session_state.initialized:
            st.session_state.handle = handle_input.strip()
            cached_user = get_user(st.session_state.handle)
            st.session_state.user_info = cached_user or {"handle": st.session_state.handle, "current_rating": 1400}
            with st.spinner(f"Initializing coach profile for '{st.session_state.handle}'..."):
                st.session_state.graph.invoke({
                    "handle": st.session_state.handle,
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
                }, config=st.session_state.config)
            st.session_state.initialized = True
            st.rerun()

        user = st.session_state.user_info or get_user(st.session_state.handle) or {}
        rating = user.get("rating") or user.get("current_rating") or 1400
        max_rating = user.get("maxRating") or user.get("max_rating") or rating
        rank_title, rank_color = get_rank_badge(rating)

        st.markdown(
            f"""
            <div class="card" style="padding: 1rem; margin-top: 1rem;">
                <div style="font-weight: 600; font-size: 1.1rem; color: #f8fafc;">{st.session_state.handle}</div>
                <div style="font-size: 0.85rem; font-weight: 500; color: {rank_color}; margin-bottom: 0.5rem;">{rank_title}</div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #94a3b8;">
                    <span>Rating: <strong style="color: #f8fafc;">{rating}</strong></span>
                    <span>Max: <strong style="color: #f8fafc;">{max_rating}</strong></span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        return st.session_state.handle

def main() -> None:
    st.set_page_config(
        page_title="Son of Aviral | Multi-Agent CP Mentorship",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inject_custom_css()
    init_session_state()
    handle = render_sidebar()

    st.markdown('<div class="main-header">Son of Aviral</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Multi-Agent Competitive Programming Coach &bull; Solution-Blind Hints &bull; Data-Driven Diagnostics</div>',
        unsafe_allow_html=True
    )

    state = st.session_state.graph.get_state(st.session_state.config)
    values = state.values

    tab_coach, tab_diag = st.tabs(["Active Coaching", "Weak Topics & Diagnostics"])

    with tab_diag:
        st.markdown("### Algorithmic Weakness Analysis")
        diag = values.get("diagnosis")
        if diag:
            st.markdown(f"**Diagnostic Summary**: {diag.summary}")
            render_weak_topics_summary(diag.weak_topics)
        else:
            saved_stats = get_user_topic_stats(handle)
            render_weak_topics_summary(saved_stats)

    with tab_coach:
        problem = values.get("problem")
        stmt = values.get("problem_statement", "")
        
        render_problem_card(problem, stmt)

        st.markdown("### Progressive Hint Requests")
        st.markdown(
            "Request graded hints without fear of spoilers. The solution-blind **Tutor Agent** drafts hints, and the **Keeper Agent** verifies safety."
        )

        col_h1, col_h2, col_h3 = st.columns(3)
        h1_clicked = col_h1.button("Level 1 (Nudge)", use_container_width=True, help="High-level invariant or monotonic observation.")
        h2_clicked = col_h2.button("Level 2 (Approach)", use_container_width=True, help="Algorithmic strategy & data structures in plain English.")
        h3_clicked = col_h3.button("Level 3 (Pseudocode)", use_container_width=True, help="Structured recurrence & pseudocode transitions.")

        if h1_clicked or h2_clicked or h3_clicked:
            lvl = 1 if h1_clicked else (2 if h2_clicked else 3)
            client_id = st.session_state.get("thread_id", "session_default")
            allowed, wait_sec = rate_limiter.consume("hint", client_id)
            if not allowed:
                st.warning(f"Hint rate limit reached. Please wait {int(wait_sec)}s before requesting another hint.")
            else:
                with st.spinner(f"Tutor & Keeper agents collaborating on Level {lvl} hint..."):
                    st.session_state.graph.update_state(st.session_state.config, {
                        "user_action": "request_hint",
                        "hint_level": lvl,
                        "last_submission_verdict": None
                    }, as_node="wait_for_user")
                    st.session_state.graph.invoke(None, config=st.session_state.config)
                st.rerun()

        draft = values.get("draft")
        verdict = values.get("verdict")
        if draft and verdict and verdict.approved:
            render_hint_box(draft, verdict)

        st.markdown("---")
        backend_name = get_active_judge_backend()
        backend_labels = {
            "isolated_subprocess": "Isolated Subprocess (Hardened)",
            "judge0": "Remote Judge0 Sandbox",
            "disabled": "Disabled (Remote CF Polling Only)"
        }
        badge_label = backend_labels.get(backend_name, backend_name.capitalize())
        badge_color = "#38bdf8" if backend_name != "disabled" else "#f59e0b"
        st.markdown(
            f"### Solution Code Editor & Sandbox Judge "
            f"<span style='font-size: 0.78rem; font-weight: 500; padding: 2px 8px; border-radius: 4px; "
            f"background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(148, 163, 184, 0.2); color: {badge_color}; margin-left: 8px;'>"
            f"Backend: {badge_label}</span>",
            unsafe_allow_html=True
        )
        st.markdown("Write and test your solution with CPU timeouts, memory constraints, and differential fuzzing.")

        col_lang, col_space = st.columns([1, 3])
        with col_lang:
            selected_lang = st.selectbox(
                "Language",
                options=["cpp", "python3", "java"],
                format_func=lambda x: {"cpp": "C++17 (g++)", "python3": "Python 3.10", "java": "Java 17"}.get(x, x),
                index=0 if st.session_state.code_lang == "cpp" else (1 if st.session_state.code_lang == "python3" else 2),
                key="select_code_lang"
            )
            if selected_lang != st.session_state.code_lang:
                st.session_state.code_lang = selected_lang
                st.session_state.user_code = STARTER_TEMPLATES.get(selected_lang, "")

        code_input = st.text_area(
            "Source Code",
            value=st.session_state.user_code,
            height=260,
            key="text_user_code"
        )
        st.session_state.user_code = code_input

        col_run_judge, col_fuzz, col_skip = st.columns([1.5, 1.5, 1])
        judge_submit_clicked = col_run_judge.button("Submit to Sandbox Judge", use_container_width=True, type="primary")
        fuzz_clicked = col_fuzz.button("Run Differential Fuzzer", use_container_width=True, help="Stress test against reference solution to find counterexamples.")
        skip_clicked = col_skip.button("Skip Problem", use_container_width=True)

        if judge_submit_clicked:
            cid = getattr(problem, "contest_id", None) if problem else None
            idx = getattr(problem, "index", None) if problem else None
            if not problem or not cid or not idx:
                st.warning("No active problem selected.")
            elif len(code_input.encode("utf-8")) > MAX_SOURCE_BYTES:
                st.error("Source code exceeds maximum allowed size (64 KB).")
            else:
                client_id = st.session_state.get("thread_id", "session_default")
                allowed, wait_sec = rate_limiter.consume("judge", client_id)
                if not allowed:
                    st.warning(f"Submission rate limit reached. Please wait {int(wait_sec)}s before submitting code again.")
                else:
                    submission_obj = CodeSubmission(
                        language=st.session_state.code_lang,
                        source_code=code_input
                    )
                    with st.spinner("Compiling and executing test cases in sandbox..."):
                        st.session_state.graph.update_state(st.session_state.config, {
                            "user_action": "submit_code",
                            "submission_code": submission_obj,
                            "last_submission_verdict": None
                        }, as_node="wait_for_user")
                        st.session_state.graph.invoke(None, config=st.session_state.config)
                    st.rerun()

        if fuzz_clicked:
            cid = getattr(problem, "contest_id", None) if problem else None
            idx = getattr(problem, "index", None) if problem else None
            if not problem or not cid or not idx:
                st.warning("No active problem selected.")
            elif len(code_input.encode("utf-8")) > MAX_SOURCE_BYTES:
                st.error("Source code exceeds maximum allowed size (64 KB).")
            else:
                client_id = st.session_state.get("thread_id", "session_default")
                allowed, wait_sec = rate_limiter.consume("fuzzer", client_id)
                if not allowed:
                    st.warning(f"Differential fuzzer rate limit reached. Please wait {int(wait_sec)}s before running fuzzer again.")
                else:
                    with st.spinner("Differential fuzzer generating randomized test inputs against reference solution..."):
                        st.session_state.fuzz_result = stress_test_problem_submission(
                            contest_id=cid,
                            idx=idx,
                            user_code=code_input,
                            user_lang=st.session_state.code_lang,
                            max_trials=30
                        )
                    st.rerun()

        if st.session_state.fuzz_result:
            render_fuzz_result_banner(st.session_state.fuzz_result)

        judge_verdict = values.get("judge_verdict")
        if judge_verdict:
            render_judge_verdict_banner(judge_verdict)

        st.markdown("---")
        st.markdown("### Remote Codeforces Synchronization")
        st.markdown("Poll live Codeforces submission verdict or manually simulate outcomes.")

        col_poll, col_ac, col_wa, col_tle = st.columns(4)
        poll_clicked = col_poll.button("Poll Codeforces", use_container_width=True, help="Poll live Codeforces API for latest submission.")
        ac_clicked = col_ac.button("Force Accepted", use_container_width=True, help="Simulate Accepted solution.")
        wa_clicked = col_wa.button("Force Wrong Answer", use_container_width=True, help="Simulate Wrong Answer.")
        tle_clicked = col_tle.button("Force Time Limit", use_container_width=True, help="Simulate Time Limit Exceeded.")

        if poll_clicked:
            with st.spinner("Polling live submission on Codeforces API..."):
                st.session_state.graph.update_state(st.session_state.config, {
                    "user_action": "submitted",
                    "last_submission_verdict": None
                }, as_node="wait_for_user")
                st.session_state.graph.invoke(None, config=st.session_state.config)
            st.rerun()

        if ac_clicked:
            with st.spinner("Processing Accepted verdict & updating topic proficiencies..."):
                st.session_state.graph.update_state(st.session_state.config, {
                    "user_action": "submitted",
                    "last_submission_verdict": "OK"
                }, as_node="wait_for_user")
                st.session_state.graph.invoke(None, config=st.session_state.config)
            st.balloons()
            st.success("Problem solved! Loading next tailored practice problem...")
            st.rerun()

        if wa_clicked or tle_clicked:
            v_type = "WRONG_ANSWER" if wa_clicked else "TIME_LIMIT_EXCEEDED"
            with st.spinner(f"Analyzing {v_type} failure & drafting targeted diagnostic guidance..."):
                st.session_state.graph.update_state(st.session_state.config, {
                    "user_action": "submitted",
                    "last_submission_verdict": v_type
                }, as_node="wait_for_user")
                st.session_state.graph.invoke(None, config=st.session_state.config)
            st.rerun()

        if skip_clicked:
            with st.spinner("Skipping problem and selecting alternative recommendation..."):
                st.session_state.graph.update_state(st.session_state.config, {
                    "user_action": "skip",
                    "last_submission_verdict": None
                }, as_node="wait_for_user")
                st.session_state.graph.invoke(None, config=st.session_state.config)
            st.rerun()

        with st.expander("Multi-Agent Reasoning Trace (Tutor / Keeper Dialogue)", expanded=False):
            render_agent_trace(values.get("history", []))

if __name__ == "__main__":
    main()
