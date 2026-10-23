"""Streamlit Web Application for CP Coach.

Multi-Agent Competitive Programming Coach with live Codeforces history sync,
deterministic algorithmic diagnostics, tailored recommendations, and verified 3-tier hints.
Clean UI without icons or emojis.
"""
import os
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(override=True)

import streamlit as st

try:
    if hasattr(st, "secrets"):
        for _key, _val in st.secrets.items():
            if isinstance(_val, (str, int, float, bool)):
                _val_str = str(_val).strip()
                if _val_str:
                    os.environ[str(_key).upper()] = _val_str
                    os.environ[str(_key)] = _val_str
except Exception:
    pass

from app.logging_config import setup_logging
setup_logging()

from app.graph import create_coach_graph
from app.state import CodeSubmission
from app.ui.components import (
    inject_custom_css,
    get_rank_badge,
    render_weak_topics_summary,
    render_problem_card,
    render_hint_box,
    render_agent_trace,
    render_judge_verdict_banner,
    render_fuzz_result_banner,
    STARTER_TEMPLATES
)
from app.judge.fuzzer import stress_test_problem_submission
from app.data.db import get_user, get_user_topic_stats
from app.data.cf_client import sync_user_data
from app.data.rate_limiter import rate_limiter
from app.observability import get_langsmith_config, is_langsmith_enabled, record_langsmith_feedback

MAX_SOURCE_BYTES: int = 64 * 1024 

def init_session_state() -> None:
    """Initialize LangGraph state machine and UI session values with persistent checkpointing."""
    query_thread = st.query_params.get("thread_id")
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = query_thread if query_thread else str(uuid.uuid4())
        st.query_params["thread_id"] = st.session_state.thread_id
        
    if "graph" not in st.session_state:
        st.session_state.graph = create_coach_graph(persisted=True)
        
    query_handle = st.query_params.get("handle")
    if "handle" not in st.session_state:
        st.session_state.handle = query_handle.strip() if query_handle else ""
    elif st.session_state.handle and not query_handle:
        st.query_params["handle"] = st.session_state.handle

    if "config" not in st.session_state:
        st.session_state.config = get_langsmith_config(
            thread_id=st.session_state.thread_id,
            handle=st.session_state.handle or "anonymous",
            tags=["streamlit", "ui"]
        )
        
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

def start_mentorship_for_handle(clean_handle: str, full_sync: bool = False) -> None:
    """Initialize or update session state and LangGraph for a selected handle."""
    clean_handle = clean_handle.strip()
    if not clean_handle:
        return
    st.session_state.handle = clean_handle
    st.query_params["handle"] = clean_handle
    st.session_state.config = get_langsmith_config(
        thread_id=st.session_state.thread_id,
        handle=clean_handle,
        tags=["streamlit", "ui"]
    )
    if full_sync:
        with st.spinner(f"Syncing profile & submissions for '{clean_handle}'..."):
            try:
                uinfo, count = sync_user_data(clean_handle, max_submissions=300, ttl_seconds=0)
                st.session_state.user_info = uinfo
                st.toast(f"Synced {count} submissions from Codeforces!")
            except Exception as e:
                st.warning(f"Could not reach CF API ({e}). Using local database cache.")
                st.session_state.user_info = get_user(clean_handle) or {"handle": clean_handle, "current_rating": 1400}
    else:
        cached_user = get_user(clean_handle)
        st.session_state.user_info = cached_user or {"handle": clean_handle, "current_rating": 1400}

    with st.spinner(f"Initializing coach profile for '{clean_handle}'..."):
        st.session_state.graph.invoke({
            "handle": clean_handle,
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

def render_welcome_screen() -> None:
    """Render an engaging hero onboarding view when no handle is currently selected."""
    st.markdown(
        """
        <div class="card" style="padding: 1.75rem 2rem; margin-top: 1rem; border: 1px solid rgba(59, 130, 246, 0.3); background: rgba(15, 23, 42, 0.65);">
            <div style="font-size: 1.45rem; font-weight: 700; color: #f8fafc; margin-bottom: 0.5rem;">
                Start Guided Mentorship
            </div>
            <div style="font-size: 0.95rem; color: #94a3b8; line-height: 1.5; margin-bottom: 1rem;">
                Enter your Codeforces handle below to sync your submission history, or select an instant profile to explore the diagnostic dashboard and solution-blind hints.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col_in, col_btn = st.columns([3, 1.2])
    with col_in:
        onboarding_handle = st.text_input(
            "Codeforces Handle",
            placeholder="e.g. aviraltrip, tourist",
            label_visibility="collapsed",
            key="main_onboarding_handle"
        )
    with col_btn:
        start_clicked = st.button("Start Mentorship", type="primary", use_container_width=True)

    if start_clicked and onboarding_handle.strip():
        start_mentorship_for_handle(onboarding_handle.strip(), full_sync=True)
        st.rerun()

    st.markdown('<div style="font-size: 0.88rem; font-weight: 500; color: #cbd5e1; margin-top: 1rem; margin-bottom: 0.5rem;">Or select an instant demo profile:</div>', unsafe_allow_html=True)
    quick_cols = st.columns(3)
    sample_profiles = [
        ("aviraltrip", "963 (Newbie)"),
        ("tourist", "3382 (LGM)"),
        ("shivanandh", "1293 (Pupil)")
    ]
    for i, (qhandle, qdesc) in enumerate(sample_profiles):
        with quick_cols[i]:
            if st.button(f"Load '{qhandle}' ({qdesc})", key=f"quick_{qhandle}", use_container_width=True):
                start_mentorship_for_handle(qhandle, full_sync=False)
                st.rerun()

    st.markdown(
        """
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; margin-top: 1.75rem;">
            <div class="card" style="margin-bottom: 0;">
                <div style="font-weight: 600; font-size: 1rem; color: #60a5fa; margin-bottom: 0.4rem;">
                    Solution-Blind Graded Hints
                </div>
                <div style="font-size: 0.85rem; color: #94a3b8; line-height: 1.45;">
                    Three-tier pedagogical assistance (Nudge, Approach, Pseudocode). Every hint is verified by an independent Keeper agent to prevent code leaks.
                </div>
            </div>
            <div class="card" style="margin-bottom: 0;">
                <div style="font-weight: 600; font-size: 1rem; color: #34d399; margin-bottom: 0.4rem;">
                    Algorithmic Weakness Analysis
                </div>
                <div style="font-size: 0.85rem; color: #94a3b8; line-height: 1.45;">
                    Automatic Bayesian diagnosis across 36 algorithmic tag hierarchies (DP, Greedy, Trees, Graphs, Math) based on your real Codeforces submission history.
                </div>
            </div>
            <div class="card" style="margin-bottom: 0;">
                <div style="font-weight: 600; font-size: 1rem; color: #f59e0b; margin-bottom: 0.4rem;">
                    Sandbox Judge & Fuzzer
                </div>
                <div style="font-size: 0.85rem; color: #94a3b8; line-height: 1.45;">
                    Built-in C++, Python, and Java execution sandbox with CPU time limits, memory tracking, and differential fuzzing against randomized stress tests.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_sidebar() -> str:
    """Render sidebar with user handle settings, sync actions, and profile stats."""
    with st.sidebar:
        has_llm_key = bool(
            os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or (hasattr(st, "secrets") and any(k in st.secrets for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "google_api_key", "gemini_api_key", "OPENROUTER_API_KEY")))
        )
        if not has_llm_key:
            st.warning("No Gemini API key detected. Add GOOGLE_API_KEY in Streamlit Cloud Settings → Secrets to generate live tailored hints.")
        st.markdown("### User Profile")
        handle_input = st.text_input(
            "Codeforces Handle",
            value=st.session_state.handle,
            placeholder="e.g. your_handle",
            help="Enter your Codeforces username."
        )
        
        col_sync, col_reset = st.columns(2)
        sync_clicked = col_sync.button("Sync CF", use_container_width=True)
        reset_clicked = col_reset.button("Reset", use_container_width=True)
        
        if reset_clicked:
            new_thread = str(uuid.uuid4())
            st.session_state.thread_id = new_thread
            st.session_state.handle = ""
            st.query_params["thread_id"] = new_thread
            st.query_params.pop("handle", None)
            st.session_state.config = get_langsmith_config(
                thread_id=new_thread,
                handle="anonymous",
                tags=["streamlit", "ui"]
            )
            st.session_state.initialized = False
            st.session_state.graph = create_coach_graph(persisted=True)
            st.rerun()

        if sync_clicked:
            clean_handle = handle_input.strip()
            if not clean_handle:
                st.warning("Please enter a Codeforces handle.")
            else:
                start_mentorship_for_handle(clean_handle, full_sync=True)
                st.rerun()

        elif not st.session_state.initialized and st.session_state.handle:
            start_mentorship_for_handle(st.session_state.handle, full_sync=False)
            st.rerun()

        if st.session_state.handle:
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
        initial_sidebar_state="auto"
    )
    
    inject_custom_css()
    init_session_state()
    handle = render_sidebar()

    st.markdown('<div class="main-header">Son of Aviral</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Multi-Agent Competitive Programming Coach &bull; Solution-Blind Hints &bull; Data-Driven Diagnostics</div>',
        unsafe_allow_html=True
    )

    if not handle:
        render_welcome_screen()
        return

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
            if is_langsmith_enabled():
                col_fb_help, col_fb_spoil = st.columns(2)
                hint_rev = values.get("revisions", 0)
                btn_key_pos = f"btn_fb_help_lvl{draft.level}_rev{hint_rev}"
                btn_key_neg = f"btn_fb_spoil_lvl{draft.level}_rev{hint_rev}"
                
                with col_fb_help:
                    if st.button("Helpful Hint", key=btn_key_pos, use_container_width=True):
                        record_langsmith_feedback(
                            run_id=st.session_state.thread_id,
                            key="pedagogical_utility",
                            score=1.0,
                            comment=f"Level {draft.level} hint approved and rated helpful"
                        )
                        st.toast("Feedback recorded to LangSmith trace!")
                with col_fb_spoil:
                    if st.button("Flag Spoiler", key=btn_key_neg, use_container_width=True):
                        record_langsmith_feedback(
                            run_id=st.session_state.thread_id,
                            key="spoiler_leakage",
                            score=0.0,
                            comment=f"User reported Level {draft.level} hint leaked algorithmic solution"
                        )
                        st.toast("Spoiler flagged to LangSmith trace!")

        st.markdown("---")
        st.markdown("### Solution Code Editor & Sandbox Judge")
        st.markdown("Write and test your solution with CPU timeouts, memory constraints, and differential fuzzing.")

        col_lang, col_space = st.columns([1.5, 2.5])
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
            st.session_state.fuzz_result = None
            st.session_state.user_code = STARTER_TEMPLATES.get(st.session_state.code_lang, "")
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
            cid = getattr(problem, "contest_id", None) if problem else None
            idx = getattr(problem, "index", None) if problem else None
            with st.spinner("Skipping problem and selecting alternative recommendation..."):
                updates: dict[str, Any] = {
                    "user_action": "skip",
                    "last_submission_verdict": None
                }
                if cid and idx:
                    updates["history"] = [{
                        "role": "user",
                        "type": "problem_skipped",
                        "contest_id": cid,
                        "index": idx,
                        "content": f"User skipped problem {cid}{idx}"
                    }]
                st.session_state.fuzz_result = None
                st.session_state.user_code = STARTER_TEMPLATES.get(st.session_state.code_lang, "")
                st.session_state.graph.update_state(st.session_state.config, updates, as_node="wait_for_user")
                st.session_state.graph.invoke(None, config=st.session_state.config)
            st.rerun()

        with st.expander("Multi-Agent Reasoning Trace (Tutor / Keeper Dialogue)", expanded=False):
            render_agent_trace(values.get("history", []))

if __name__ == "__main__":
    main()
