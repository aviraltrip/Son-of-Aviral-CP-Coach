import streamlit as st
import pandas as pd
from typing import Any
from app.data.stats import is_valid_algorithmic_tag

CUSTOM_CSS = """
<style>
/* Modern typography & base layout */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body {
    overflow-x: hidden !important;
    max-width: 100% !important;
    width: 100% !important;
    position: relative;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

[data-testid="stAppViewContainer"] {
    overflow-x: hidden !important;
    max-width: 100% !important;
}

.main {
    overflow-x: hidden !important;
    max-width: 100% !important;
}

/* Streamlit Header Glassmorphism & Fixed Bar Clearance */
header[data-testid="stHeader"] {
    background: rgba(15, 23, 42, 0.85) !important;
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
    border-bottom: 1px solid rgba(148, 163, 184, 0.08) !important;
    z-index: 99999 !important;
}

/* Sidebar Toggle Button styling on Mobile & Desktop */
div[data-testid="stSidebarCollapsedControl"] {
    top: 0.5rem !important;
    left: 0.5rem !important;
}

div[data-testid="stSidebarCollapsedControl"] button {
    background: rgba(30, 41, 59, 0.7) !important;
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    border-radius: 8px !important;
    color: #f8fafc !important;
}

code, pre {
    font-family: 'JetBrains Mono', monospace !important;
}

/* Base Block Container Spacing */
.block-container,
div[data-testid="stMainBlockContainer"],
.stMainBlockContainer,
div[data-testid="block-container"] {
    padding-top: 5.75rem !important;
    padding-bottom: 3rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
}

/* Header & Card Containers */
.main-header {
    font-size: 2.1rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.25;
    margin-top: 0.25rem;
    margin-bottom: 0.25rem;
    color: #f8fafc;
    word-break: break-word;
}

.sub-header {
    color: #94a3b8;
    font-size: 0.95rem;
    line-height: 1.45;
    margin-bottom: 1.5rem;
    word-break: break-word;
}

.card {
    background: rgba(30, 41, 59, 0.4);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
    backdrop-filter: blur(8px);
    box-sizing: border-box;
}

.card-title {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
    color: #f8fafc;
}

/* Badges & Chips */
.badge-rating {
    background: #3b82f6;
    color: #ffffff;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 9999px;
    display: inline-block;
    white-space: nowrap;
}

.badge-tag {
    background: rgba(148, 163, 184, 0.12);
    color: #cbd5e1;
    font-size: 0.75rem;
    font-weight: 500;
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    margin-right: 0.4rem;
    margin-bottom: 0.35rem;
    display: inline-block;
    line-height: 1.3;
}

.hint-box {
    background: rgba(15, 23, 42, 0.6);
    border-left: 4px solid #3b82f6;
    border-radius: 0 8px 8px 0;
    padding: 1rem 1.25rem;
    margin-top: 1rem;
    margin-bottom: 1rem;
    word-break: break-word;
    box-sizing: border-box;
}

.audit-box {
    background: rgba(15, 23, 42, 0.4);
    border: 1px dashed rgba(148, 163, 184, 0.2);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: #94a3b8;
    margin-top: 0.5rem;
    word-break: break-word;
    box-sizing: border-box;
}

.agent-bubble-tutor {
    background: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    word-break: break-word;
    box-sizing: border-box;
}

.agent-bubble-keeper {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    word-break: break-word;
    box-sizing: border-box;
}

.agent-bubble-keeper-rejected {
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    word-break: break-word;
    box-sizing: border-box;
}

/* Streamlit Tabs Navigation */
button[data-testid="stTab"] {
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    padding: 0.5rem 0.85rem !important;
    color: #94a3b8 !important;
    white-space: nowrap !important;
}

button[data-testid="stTab"][aria-selected="true"] {
    color: #3b82f6 !important;
    font-weight: 600 !important;
}

/* Buttons base & touch targets */
div[data-testid="stButton"] button,
.stButton > button {
    min-height: 44px !important;
    height: auto !important;
    padding: 0.55rem 0.85rem !important;
    white-space: normal !important;
    word-break: break-word !important;
    touch-action: manipulation;
}

div[data-testid="stButton"] button p,
.stButton > button p {
    white-space: normal !important;
    word-break: break-word !important;
    line-height: 1.3 !important;
    margin: 0 !important;
}

/* Primary Action Buttons (Submit to Sandbox Judge) */
button[kind="primary"],
button[data-testid="stBaseButton-primary"],
button[data-testid="baseButton-primary"],
div[data-testid="stButton"] button[kind="primary"],
.stButton button[kind="primary"] {
    background-color: #2563eb !important;
    background-image: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    border: 1px solid #3b82f6 !important;
    color: #ffffff !important;
    font-weight: 500 !important;
    box-shadow: 0 2px 4px rgba(37, 99, 235, 0.25) !important;
    transition: all 0.2s ease-in-out !important;
}

button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="baseButton-primary"]:hover,
div[data-testid="stButton"] button[kind="primary"]:hover,
.stButton button[kind="primary"]:hover {
    background-color: #1d4ed8 !important;
    background-image: linear-gradient(135deg, #1d4ed8, #1e40af) !important;
    border-color: #60a5fa !important;
    color: #ffffff !important;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4) !important;
    transform: translateY(-1px);
}

button[kind="primary"]:active,
button[data-testid="stBaseButton-primary"]:active,
button[data-testid="baseButton-primary"]:active,
div[data-testid="stButton"] button[kind="primary"]:active,
.stButton button[kind="primary"]:active {
    background-color: #1e40af !important;
    background-image: linear-gradient(135deg, #1e40af, #1e3a8a) !important;
    border-color: #1e3a8a !important;
    box-shadow: none !important;
    transform: translateY(0);
}

button[kind="primary"]:focus:not(:active),
button[data-testid="stBaseButton-primary"]:focus:not(:active),
button[data-testid="baseButton-primary"]:focus:not(:active) {
    border-color: #93c5fd !important;
    box-shadow: 0 0 0 0.2rem rgba(59, 130, 246, 0.4) !important;
}

/* Code Editor & Code Blocks */
div[data-testid="stTextArea"] textarea {
    font-family: 'JetBrains Mono', monospace !important;
    tab-size: 4;
}

div[data-testid="stCodeBlock"] {
    max-width: 100% !important;
}

div[data-testid="stCodeBlock"] pre {
    max-width: 100% !important;
    overflow-x: auto !important;
    white-space: pre !important;
    font-size: 0.85rem !important;
}

/* KaTeX formula overflow safety */
.katex-display {
    overflow-x: auto !important;
    overflow-y: hidden !important;
    max-width: 100% !important;
    padding-bottom: 0.25rem !important;
}

/* Dataframe & Tables safety */
div[data-testid="stDataFrame"] {
    width: 100% !important;
    max-width: 100% !important;
    overflow-x: auto !important;
}

/* ========================================================= */
/* Mobile Responsive Overrides: Tablets & Phones (max 768px) */
/* ========================================================= */
@media (max-width: 768px) {
    /* Critical Fix: Ensure block container clears fixed header toolbar */
    .block-container {
        padding-top: calc(5rem + env(safe-area-inset-top, 0px)) !important;
        padding-bottom: calc(2.5rem + env(safe-area-inset-bottom, 0px)) !important;
        padding-left: calc(0.85rem + env(safe-area-inset-left, 0px)) !important;
        padding-right: calc(0.85rem + env(safe-area-inset-right, 0px)) !important;
        max-width: 100% !important;
    }

    .main-header {
        font-size: 1.65rem !important;
        line-height: 1.25 !important;
        margin-top: 0.35rem !important;
        margin-bottom: 0.35rem !important;
    }

    .sub-header {
        font-size: 0.85rem !important;
        line-height: 1.45 !important;
        margin-bottom: 1.25rem !important;
    }

    .card {
        padding: 0.9rem 1rem !important;
        border-radius: 10px !important;
        margin-bottom: 1rem !important;
    }

    .hint-box {
        padding: 0.85rem 1rem !important;
        margin-top: 0.75rem !important;
        margin-bottom: 0.75rem !important;
    }

    .audit-box,
    .agent-bubble-tutor,
    .agent-bubble-keeper,
    .agent-bubble-keeper-rejected {
        padding: 0.65rem 0.85rem !important;
    }

    /* Tabs adjustments on mobile */
    button[data-testid="stTab"] {
        font-size: 0.85rem !important;
        padding: 0.45rem 0.65rem !important;
    }

    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 0.35rem !important;
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
    }

    /* Prevent mobile Safari & Android auto-zoom on inputs */
    input[type="text"],
    textarea,
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stSelectbox"] select {
        font-size: 16px !important;
    }

    /* Alerts padding on mobile */
    div[data-testid="stAlert"] {
        padding: 0.75rem 0.9rem !important;
    }
}

/* ========================================================= */
/* Phone-Specific Responsive Stacking (max 640px)            */
/* ========================================================= */
@media (max-width: 640px) {
    /* Stack multi-column button & input blocks gracefully */
    div[data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
        gap: 0.5rem !important;
    }

    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        width: 100% !important;
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }

    .main-header {
        font-size: 1.5rem !important;
    }
}
</style>
"""

def inject_custom_css() -> None:
    """Inject custom CSS rules into Streamlit page."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def get_rank_badge(rating: int | None) -> tuple[str, str]:
    """Return rank title and color according to Codeforces rating divisions."""
    if not rating:
        return "Unrated", "#94a3b8"
    if rating >= 3000:
        return "Legendary Grandmaster", "#ff0000"
    if rating >= 2600:
        return "International Grandmaster", "#ff0000"
    if rating >= 2400:
        return "Grandmaster", "#ff0000"
    if rating >= 2300:
        return "International Master", "#ff8c00"
    if rating >= 2100:
        return "Master", "#ff8c00"
    if rating >= 1900:
        return "Candidate Master", "#aa00aa"
    if rating >= 1600:
        return "Expert", "#0000ff"
    if rating >= 1400:
        return "Specialist", "#03a89e"
    if rating >= 1200:
        return "Pupil", "#008000"
    return "Newbie", "#808080"

def render_tag_chips(tags: list[str]) -> str:
    """Generate HTML string of tag chips, filtering out non-algorithmic/administrative tags."""
    valid_tags = [t for t in tags if is_valid_algorithmic_tag(t)]
    display_tags = valid_tags if valid_tags else (tags if tags else ["implementation"])
    return "".join(f'<span class="badge-tag">{t}</span>' for t in display_tags)

def render_weak_topics_summary(weak_topics: list[Any]) -> None:
    """Render weak topics in a clean bar chart and structured summary table."""
    if not weak_topics:
        st.info("No weak topics identified yet. Sync submission history to compute statistics.")
        return

    data = []
    for t in weak_topics:
        avg_r = getattr(t, "avg_rating", t.get("avg_rating_solved", None) if isinstance(t, dict) else None)
        data.append({
            "Topic": getattr(t, "tag", t.get("tag", "") if isinstance(t, dict) else ""),
            "Failure Score": getattr(t, "weighted_failure_score", t.get("weighted_failure_score", 0.0) if isinstance(t, dict) else 0.0),
            "Solve Ratio": f"{int(getattr(t, 'solved_ratio', t.get('solved_ratio', 0.0) if isinstance(t, dict) else 0.0) * 100)}%",
            "Attempts": getattr(t, "n_attempts", t.get("n_attempts", t.get("total_attempts", 0)) if isinstance(t, dict) else 0),
            "Avg Solved Rating": str(int(avg_r)) if avg_r and avg_r != "-" else "-"
        })
    df = pd.DataFrame(data)
    df_sorted = df.sort_values(by="Failure Score", ascending=False)
    
    # Focus chart on top 8 weaknesses so category labels remain legible on mobile
    top_n = min(8, len(df_sorted))
    chart_df = df_sorted.head(top_n).set_index("Topic")[["Failure Score"]]
    if len(df) > top_n:
        st.caption(f"Displaying Top {top_n} Algorithmic Weaknesses:")
    st.bar_chart(chart_df, color="#3b82f6")
    
    st.dataframe(
        df_sorted,
        width="stretch",
        hide_index=True,
        column_config={
            "Topic": st.column_config.TextColumn(
                "Topic",
                width="medium"
            ),
            "Failure Score": st.column_config.ProgressColumn(
                "Failure Score",
                help="Higher score indicates high failure rate weighted by difficulty and recency.",
                format="%.3f",
                min_value=0.0,
                max_value=1.0,
                width="medium"
            ),
            "Solve Ratio": st.column_config.TextColumn(
                "Solve %",
                help="Solved submissions ratio across all attempts",
                width="small"
            ),
            "Attempts": st.column_config.NumberColumn(
                "Tries",
                help="Total problem attempts in this topic",
                width="small"
            ),
            "Avg Solved Rating": st.column_config.TextColumn(
                "Avg Rating",
                help="Average Codeforces rating of solved problems",
                width="small"
            ),
        }
    )

def render_problem_card(problem: Any, statement: str) -> None:
    """Render active problem details, rating, tags, and problem statement."""
    if not problem:
        st.info("No active problem selected. Click 'Sync CF' to recommend a problem.")
        return

    cid = getattr(problem, "contest_id", "")
    idx = getattr(problem, "index", "")
    name = getattr(problem, "name", f"Problem {cid}{idx}")
    rating = getattr(problem, "rating", None)
    tags = getattr(problem, "tags", [])
    reason = getattr(problem, "reason", "Tailored practice problem based on algorithmic weakness.")
    cf_url = f"https://codeforces.com/problemset/problem/{cid}/{idx}"

    rating_html = f'<span class="badge-rating">{rating}</span>' if rating else ''
    tags_html = render_tag_chips(tags)

    st.markdown(
        f"""
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
                <div style="font-size: 1.25rem; font-weight: 700; color: #f8fafc; min-width: 0; word-break: break-word;">
                    {cid}{idx} &bull; {name}
                </div>
                <div style="flex-shrink: 0;">{rating_html}</div>
            </div>
            <div style="margin-bottom: 0.75rem;">{tags_html}</div>
            <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 0.5rem;">
                <strong>Why Selected:</strong> {reason}
            </div>
            <div style="font-size: 0.85rem;">
                <a href="{cf_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">View on Codeforces &rarr;</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("View Problem Statement", expanded=True):
        if statement:
            st.markdown(statement)
        else:
            st.markdown(f"Visit the [Codeforces Problem Page]({cf_url}) to read the full description and submit.")

def render_hint_box(draft: Any, verdict: Any = None) -> None:
    """Render the current approved hint without internal audit boilerplate."""
    if not draft:
        return

    level_names = {1: "Level 1: Nudge", 2: "Level 2: Approach", 3: "Level 3: Pseudocode"}
    lvl_str = level_names.get(draft.level, f"Level {draft.level}")

    st.markdown(
        f"""
        <div class="hint-box">
            <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #3b82f6; margin-bottom: 0.4rem;">
                Coach Hint ({lvl_str})
            </div>
            <div style="font-size: 1rem; color: #f8fafc; line-height: 1.6;">
                {draft.text}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_agent_trace(history: list[dict[str, Any]]) -> None:
    """Render chronological reasoning trace of the Tutor and Keeper exchange."""
    if not history:
        st.caption("No multi-agent interactions yet.")
        return

    for item in history:
        role = item.get("role", "system")
        item_type = item.get("type", "")
        
        if item_type == "draft":
            rev = item.get("revision", 0)
            lvl = item.get("level", 1)
            st.markdown(
                f"""
                <div class="agent-bubble-tutor">
                    <div style="font-size: 0.8rem; font-weight: 600; color: #60a5fa; margin-bottom: 0.2rem;">
                        Tutor Agent (Draft Level {lvl} | Revision {rev})
                    </div>
                    <div style="font-size: 0.9rem; color: #e2e8f0;">{item.get('text', '')}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        elif item_type == "submission_check":
            v = item.get("verdict", "OK")
            st.markdown(
                f"""
                <div class="card" style="padding: 0.75rem 1rem; margin-bottom: 0.5rem;">
                    <strong>Submission Event:</strong> Verdict received: <code>{v}</code>
                </div>
                """,
                unsafe_allow_html=True
            )

STARTER_TEMPLATES = {
    "cpp": """#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;

void solve() {
    int n;
    if (!(cin >> n)) return;
    cout << n << "\\n";
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    int t = 1;
    if (cin >> t) {
        while (t--) solve();
    }
    return 0;
}
""",
    "python3": """import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    print("Solution output")

if __name__ == '__main__':
    solve()
""",
    "java": """import java.util.Scanner;

public class Solution {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        if (sc.hasNext()) {
            int t = sc.nextInt();
            while (t-- > 0) {
            }
        }
    }
}
"""
}

def render_judge_verdict_banner(judge_verdict: Any) -> None:
    """Render modern styled card and telemetry for Sandbox Judge outcomes."""
    if not judge_verdict:
        return

    status = getattr(judge_verdict, "status", "UNKNOWN")
    passed = getattr(judge_verdict, "passed_count", 0)
    total = getattr(judge_verdict, "total_count", 0)
    time_ms = getattr(judge_verdict, "time_consumed_ms", 0.0)
    mem_bytes = getattr(judge_verdict, "memory_consumed_bytes", 0)
    mem_kb = round(mem_bytes / 1024, 1)

    color_map = {
        "AC": ("#10b981", "rgba(16, 185, 129, 0.12)", "Accepted"),
        "WA": ("#ef4444", "rgba(239, 68, 68, 0.12)", "Wrong Answer"),
        "TLE": ("#f59e0b", "rgba(245, 158, 11, 0.12)", "Time Limit Exceeded"),
        "MLE": ("#f59e0b", "rgba(245, 158, 11, 0.12)", "Memory Limit Exceeded"),
        "CE": ("#a855f7", "rgba(168, 85, 247, 0.12)", "Compilation Error"),
        "RE": ("#ef4444", "rgba(239, 68, 68, 0.12)", "Runtime Error"),
        "UNKNOWN": ("#94a3b8", "rgba(148, 163, 184, 0.12)", "Unknown")
    }

    border_color, bg_color, title_text = color_map.get(status, color_map["UNKNOWN"])
    failing_idx = getattr(judge_verdict, "failing_test_index", None)
    fail_detail = f"on Test #{failing_idx}" if (failing_idx and status != "AC") else ""

    st.markdown(
        f"""
        <div class="card" style="background: {bg_color}; border: 1px solid {border_color}; margin-top: 1rem; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.6rem; margin-bottom: 0.5rem;">
                <div style="font-size: 1.15rem; font-weight: 700; color: {border_color}; word-break: break-word;">
                    {title_text} {fail_detail}
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center;">
                    <span style="background: rgba(255,255,255,0.08); padding: 0.2rem 0.55rem; border-radius: 6px; font-size: 0.8rem; white-space: nowrap;">
                        {time_ms:.1f} ms
                    </span>
                    <span style="background: rgba(255,255,255,0.08); padding: 0.2rem 0.55rem; border-radius: 6px; font-size: 0.8rem; white-space: nowrap;">
                        {mem_kb} KB
                    </span>
                    <span style="background: rgba(255,255,255,0.08); padding: 0.2rem 0.55rem; border-radius: 6px; font-size: 0.8rem; white-space: nowrap;">
                        Passed: {passed}/{total}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if status == "CE" and getattr(judge_verdict, "compiler_output", ""):
        with st.expander("View Compiler Diagnostic Logs", expanded=True):
            st.code(judge_verdict.compiler_output, language="text")

    failing_res = getattr(judge_verdict, "failing_test_result", None)
    if failing_res:
        with st.expander(f"Inspect Failing Test Case #{failing_res.test_index}", expanded=True):
            col_in, col_out, col_exp = st.columns(3)
            with col_in:
                st.caption("Standard Input")
                st.code(failing_res.input_snippet or "[Empty]", language="text")
            with col_out:
                st.caption("Your Output")
                st.code(failing_res.user_output or "[No Output]", language="text")
            with col_exp:
                st.caption("Expected Output")
                st.code(failing_res.expected_output or "[Empty]", language="text")

def render_fuzz_result_banner(fuzz_result: Any) -> None:
    """Render differential fuzzing / stress testing result."""
    if not fuzz_result:
        return

    if fuzz_result.counterexample_found:
        st.markdown(
            f"""
            <div class="card" style="background: rgba(239, 68, 68, 0.12); border: 1px solid #ef4444; margin-top: 1rem; word-break: break-word;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.4rem;">
                    <div style="font-size: 1.1rem; font-weight: 700; color: #ef4444;">
                        Counterexample Discovered
                    </div>
                    <span style="background: rgba(239, 68, 68, 0.2); color: #fca5a5; font-size: 0.8rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 6px; white-space: nowrap;">
                        Trial {fuzz_result.trials_run}
                    </span>
                </div>
                <div style="font-size: 0.9rem; color: #cbd5e1; margin-bottom: 0.6rem; line-height: 1.4;">
                    The differential fuzzer caught a mismatch against the reference solution!
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        col_in, col_usr, col_ref = st.columns(3)
        with col_in:
            st.caption("Fuzzer Input")
            st.code(fuzz_result.failing_input or "", language="text")
        with col_usr:
            st.caption(f"Your Output ({fuzz_result.user_verdict})")
            st.code(fuzz_result.user_output or "", language="text")
        with col_ref:
            st.caption("Ground Truth Reference Output")
            st.code(fuzz_result.expected_output or "", language="text")
    else:
        st.success(f"Stress testing passed! No counterexamples found across {fuzz_result.trials_run} randomized trials.")

