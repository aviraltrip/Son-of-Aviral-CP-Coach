"""Streamlit Web Application for CP Coach.

Multi-Agent Competitive Programming Coach with live Codeforces history sync,
deterministic algorithmic diagnostics, tailored recommendations, and verified 3-tier hints.
"""
import os
import sys
import uuid
from pathlib import Path

# Ensure project root is in sys.path when launched directly via `streamlit run`
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

from app.graph import create_coach_graph
from app.ui.components import (
    inject_custom_css,
    get_rank_badge,
    render_tag_chips,
    render_weak_topics_summary
)
from app.data.db import get_user, get_user_topic_stats
from app.data.cf_client import sync_user_data

def init_session_state() -> None:
    """Initialize LangGraph state machine and UI session values."""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
        
    if "graph" not in st.session_state:
        st.session_state.graph = create_coach_graph()
        
    if "config" not in st.session_state:
        st.session_state.config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
    if "handle" not in st.session_state:
        st.session_state.handle = "tourist"
        
    if "user_info" not in st.session_state:
        st.session_state.user_info = None
        
    if "initialized" not in st.session_state:
        st.session_state.initialized = False

def render_sidebar() -> str:
    """Render sidebar with user handle settings, sync actions, and profile stats."""
    with st.sidebar:
        st.markdown("### 👤 User Profile")
        handle_input = st.text_input("Codeforces Handle", value=st.session_state.handle, help="Enter your Codeforces username.")
        
        col_sync, col_reset = st.columns(2)
        sync_clicked = col_sync.button("🔄 Sync CF", use_container_width=True)
        reset_clicked = col_reset.button("⚡ Reset", use_container_width=True)
        
        if reset_clicked:
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.config = {"configurable": {"thread_id": st.session_state.thread_id}}
            st.session_state.initialized = False
            st.session_state.graph = create_coach_graph()
            st.rerun()

        if sync_clicked or not st.session_state.initialized:
            st.session_state.handle = handle_input.strip()
            with st.spinner(f"Syncing profile & submissions for '{st.session_state.handle}'..."):
                try:
                    uinfo, count = sync_user_data(st.session_state.handle, max_submissions=300, ttl_seconds=0)
                    st.session_state.user_info = uinfo
                    st.toast(f"Synced {count} submissions from Codeforces!", icon="✅")
                except Exception as e:
                    st.warning(f"Could not reach CF API ({e}). Using local database cache.")
                    st.session_state.user_info = get_user(st.session_state.handle) or {"handle": st.session_state.handle, "current_rating": 1400}

            # Initialize LangGraph
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
        
        st.markdown("---")
        st.markdown(f"**Session Thread**: `{st.session_state.thread_id[:8]}`")
        return st.session_state.handle

def main() -> None:
    st.set_page_config(
        page_title="CP Coach | Multi-Agent CP Mentorship",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inject_custom_css()
    init_session_state()
    handle = render_sidebar()

    st.markdown('<div class="main-header">CP Coach</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Multi-Agent Competitive Programming Coach &bull; Solution-Blind Hints &bull; Data-Driven Diagnostics</div>',
        unsafe_allow_html=True
    )

    state = st.session_state.graph.get_state(st.session_state.config)
    values = state.values

    tab_coach, tab_diag = st.tabs(["🎯 Active Coaching", "📊 Weak Topics & Diagnostics"])

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
        
        # 1. Problem Viewer Card
        from app.ui.components import render_problem_card, render_hint_box, render_agent_trace
        render_problem_card(problem, stmt)

        st.markdown("### 💡 Progressive Hint Requests")
        st.markdown(
            "Request graded hints without fear of spoilers. The solution-blind **Tutor Agent** drafts hints, and the **Keeper Agent** verifies safety."
        )

        col_h1, col_h2, col_h3 = st.columns(3)
        h1_clicked = col_h1.button("💡 Level 1 (Nudge)", use_container_width=True, help="High-level invariant or monotonic observation.")
        h2_clicked = col_h2.button("🧭 Level 2 (Approach)", use_container_width=True, help="Algorithmic strategy & data structures in plain English.")
        h3_clicked = col_h3.button("📝 Level 3 (Pseudocode)", use_container_width=True, help="Structured recurrence & pseudocode transitions.")

        if h1_clicked or h2_clicked or h3_clicked:
            lvl = 1 if h1_clicked else (2 if h2_clicked else 3)
            with st.spinner(f"Tutor & Keeper agents collaborating on Level {lvl} hint..."):
                st.session_state.graph.update_state(st.session_state.config, {
                    "user_action": "request_hint",
                    "hint_level": lvl,
                    "last_submission_verdict": None
                }, as_node="wait_for_user")
                st.session_state.graph.invoke(None, config=st.session_state.config)
            st.rerun()

        # 2. Render Approved Hint Display
        draft = values.get("draft")
        verdict = values.get("verdict")
        if draft and verdict and verdict.approved:
            render_hint_box(draft, verdict)

        st.markdown("---")
        st.markdown("### 🚀 Submission & Verification")
        st.markdown("Check your Codeforces submission to update your proficiency stats or receive targeted failure diagnostics.")

        col_poll, col_ac, col_wa, col_tle, col_skip = st.columns([1.2, 1, 1, 1, 1])
        poll_clicked = col_poll.button("🔄 Poll Codeforces", use_container_width=True, help="Poll live Codeforces API for latest submission.")
        ac_clicked = col_ac.button("✅ Submit (AC)", use_container_width=True, help="Simulate Accepted solution.")
        wa_clicked = col_wa.button("❌ Submit (WA)", use_container_width=True, help="Simulate Wrong Answer.")
        tle_clicked = col_tle.button("⏱️ Submit (TLE)", use_container_width=True, help="Simulate Time Limit Exceeded.")
        skip_clicked = col_skip.button("⏭️ Skip", use_container_width=True, help="Skip problem and pick another.")

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
            st.success("🎉 Problem solved! Loading next tailored practice problem...")
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

        # 3. Agent Inspection Trace
        with st.expander("🔍 Multi-Agent Reasoning Trace (Tutor ⇄ Keeper Dialogue)", expanded=False):
            render_agent_trace(values.get("history", []))

if __name__ == "__main__":
    main()
