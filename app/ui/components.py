import streamlit as st
import pandas as pd
from typing import Any
from app.data.stats import is_valid_algorithmic_tag

CUSTOM_CSS = """
<style>
/* Modern typography & base layout */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

code, pre {
    font-family: 'JetBrains Mono', monospace !important;
}

/* Header & Card Containers */
.main-header {
    font-size: 2.1rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 0.2rem;
}

.sub-header {
    color: #94a3b8;
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
}

.card {
    background: rgba(30, 41, 59, 0.4);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
    backdrop-filter: blur(8px);
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
}

.badge-tag {
    background: rgba(148, 163, 184, 0.12);
    color: #cbd5e1;
    font-size: 0.75rem;
    font-weight: 500;
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    margin-right: 0.4rem;
    display: inline-block;
}

.hint-box {
    background: rgba(15, 23, 42, 0.6);
    border-left: 4px solid #3b82f6;
    border-radius: 0 8px 8px 0;
    padding: 1rem 1.25rem;
    margin-top: 1rem;
    margin-bottom: 1rem;
}

.audit-box {
    background: rgba(15, 23, 42, 0.4);
    border: 1px dashed rgba(148, 163, 184, 0.2);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: #94a3b8;
    margin-top: 0.5rem;
}

.agent-bubble-tutor {
    background: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
}

.agent-bubble-keeper {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
}

.agent-bubble-keeper-rejected {
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
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
    
    chart_df = df.set_index("Topic")[["Failure Score"]]
    st.bar_chart(chart_df, color="#3b82f6")
    
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Failure Score": st.column_config.ProgressColumn(
                "Failure Score (Decay + Bayes)",
                help="Higher score indicates high failure rate weighted by difficulty and recency.",
                format="%.3f",
                min_value=0.0,
                max_value=1.0,
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
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <div style="font-size: 1.3rem; font-weight: 700; color: #f8fafc;">
                    {cid}{idx} &bull; {name}
                </div>
                <div>{rating_html}</div>
            </div>
            <div style="margin-bottom: 0.75rem;">{tags_html}</div>
            <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 0.5rem;">
                💡 <strong>Why Selected:</strong> {reason}
            </div>
            <div style="font-size: 0.85rem;">
                🔗 <a href="{cf_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">View on Codeforces &rarr;</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("📜 View Problem Statement", expanded=True):
        if statement:
            st.markdown(statement)
        else:
            st.markdown(f"Visit the [Codeforces Problem Page]({cf_url}) to read the full description and submit.")

def render_hint_box(draft: Any, verdict: Any) -> None:
    """Render the current approved hint and Keeper audit verification badge."""
    if not draft:
        return

    level_names = {1: "Level 1: Nudge", 2: "Level 2: Approach", 3: "Level 3: Pseudocode"}
    lvl_str = level_names.get(draft.level, f"Level {draft.level}")
    audit_text = verdict.reason if verdict else "Verified by Keeper Agent."
    
    st.markdown(
        f"""
        <div class="hint-box">
            <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #3b82f6; margin-bottom: 0.4rem;">
                💬 Coach Hint ({lvl_str})
            </div>
            <div style="font-size: 1rem; color: #f8fafc; line-height: 1.5; margin-bottom: 0.6rem;">
                {draft.text}
            </div>
            <div class="audit-box">
                🛡️ <strong>Keeper Safety Audit:</strong> {audit_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_agent_trace(history: list[dict[str, Any]]) -> None:
    """Render chronological reasoning trace of the Tutor ⇄ Keeper exchange."""
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
                        🤖 Tutor Agent (Draft Level {lvl} | Revision {rev})
                    </div>
                    <div style="font-size: 0.9rem; color: #e2e8f0;">{item.get('text', '')}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        elif item_type == "submission_check":
            v = item.get("verdict", "OK")
            icon = "✅" if v == "OK" else "❌"
            st.markdown(
                f"""
                <div class="card" style="padding: 0.75rem 1rem; margin-bottom: 0.5rem;">
                    <strong>{icon} Submission Event:</strong> Verdict received: <code>{v}</code>
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
    // Write your solution logic here
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
    # Process test cases
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
                // Solution logic
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
        "AC": ("#10b981", "rgba(16, 185, 129, 0.12)", "✅ Accepted"),
        "WA": ("#ef4444", "rgba(239, 68, 68, 0.12)", "❌ Wrong Answer"),
        "TLE": ("#f59e0b", "rgba(245, 158, 11, 0.12)", "⏱️ Time Limit Exceeded"),
        "MLE": ("#f59e0b", "rgba(245, 158, 11, 0.12)", "💾 Memory Limit Exceeded"),
        "CE": ("#a855f7", "rgba(168, 85, 247, 0.12)", "⚠️ Compilation Error"),
        "RE": ("#ef4444", "rgba(239, 68, 68, 0.12)", "💥 Runtime Error"),
        "UNKNOWN": ("#94a3b8", "rgba(148, 163, 184, 0.12)", "❓ Unknown")
    }

    border_color, bg_color, title_text = color_map.get(status, color_map["UNKNOWN"])
    failing_idx = getattr(judge_verdict, "failing_test_index", None)
    fail_detail = f"on Test #{failing_idx}" if (failing_idx and status != "AC") else ""

    st.markdown(
        f"""
        <div style="background: {bg_color}; border: 1px solid {border_color}; border-radius: 10px; padding: 1rem 1.25rem; margin-top: 1rem; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <div style="font-size: 1.15rem; font-weight: 700; color: {border_color};">
                    {title_text} {fail_detail}
                </div>
                <div style="font-size: 0.85rem; color: #cbd5e1;">
                    <span style="background: rgba(255,255,255,0.08); padding: 0.2rem 0.6rem; border-radius: 6px; margin-right: 0.4rem;">
                        ⚡ {time_ms:.1f} ms
                    </span>
                    <span style="background: rgba(255,255,255,0.08); padding: 0.2rem 0.6rem; border-radius: 6px; margin-right: 0.4rem;">
                        💾 {mem_kb} KB
                    </span>
                    <span style="background: rgba(255,255,255,0.08); padding: 0.2rem 0.6rem; border-radius: 6px;">
                        Passed: {passed}/{total}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if status == "CE" and getattr(judge_verdict, "compiler_output", ""):
        with st.expander("🔍 View Compiler Diagnostic Logs", expanded=True):
            st.code(judge_verdict.compiler_output, language="text")

    failing_res = getattr(judge_verdict, "failing_test_result", None)
    if failing_res:
        with st.expander(f"⚠️ Inspect Failing Test Case #{failing_res.test_index}", expanded=True):
            col_in, col_out, col_exp = st.columns(3)
            with col_in:
                st.caption("📥 Standard Input")
                st.code(failing_res.input_snippet or "[Empty]", language="text")
            with col_out:
                st.caption("📤 Your Output")
                st.code(failing_res.user_output or "[No Output]", language="text")
            with col_exp:
                st.caption("🎯 Expected Output")
                st.code(failing_res.expected_output or "[Empty]", language="text")


def render_fuzz_result_banner(fuzz_result: Any) -> None:
    """Render differential fuzzing / stress testing result."""
    if not fuzz_result:
        return

    if fuzz_result.counterexample_found:
        st.markdown(
            f"""
            <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid #ef4444; border-radius: 10px; padding: 1rem 1.25rem; margin-top: 1rem;">
                <div style="font-size: 1.1rem; font-weight: 700; color: #ef4444; margin-bottom: 0.4rem;">
                    💥 Counterexample Discovered (Trial {fuzz_result.trials_run})
                </div>
                <div style="font-size: 0.9rem; color: #cbd5e1; margin-bottom: 0.6rem;">
                    The differential fuzzer caught a mismatch against the reference solution!
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        col_in, col_usr, col_ref = st.columns(3)
        with col_in:
            st.caption("📥 Fuzzer Input")
            st.code(fuzz_result.failing_input or "", language="text")
        with col_usr:
            st.caption(f"❌ Your Output ({fuzz_result.user_verdict})")
            st.code(fuzz_result.user_output or "", language="text")
        with col_ref:
            st.caption("✅ Ground Truth Reference Output")
            st.code(fuzz_result.expected_output or "", language="text")
    else:
        st.success(f"🎉 Stress testing passed! No counterexamples found across {fuzz_result.trials_run} randomized trials.")

