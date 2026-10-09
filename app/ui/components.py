"""UI Component styling and presentation helpers for CP Coach Streamlit App."""
import streamlit as st

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
    """Generate HTML string of tag chips."""
    return "".join(f'<span class="badge-tag">{t}</span>' for t in tags)

def render_weak_topics_summary(weak_topics: list[Any]) -> None:
    """Render weak topics in a clean bar chart and structured summary table."""
    if not weak_topics:
        st.info("No weak topics identified yet. Sync submission history to compute statistics.")
        return

    import pandas as pd
    data = []
    for t in weak_topics:
        data.append({
            "Topic": getattr(t, "tag", t.get("tag", "")),
            "Failure Score": getattr(t, "weighted_failure_score", t.get("weighted_failure_score", 0.0)),
            "Solve Ratio": f"{int(getattr(t, 'solved_ratio', t.get('solved_ratio', 0.0)) * 100)}%",
            "Attempts": getattr(t, "n_attempts", t.get("n_attempts", t.get("total_attempts", 0))),
            "Avg Solved Rating": getattr(t, "avg_rating", t.get("avg_rating_solved", "-")) or "-"
        })
    df = pd.DataFrame(data)
    
    chart_df = df.set_index("Topic")[["Failure Score"]]
    st.bar_chart(chart_df, color="#3b82f6")
    
    st.dataframe(
        df,
        use_container_width=True,
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
