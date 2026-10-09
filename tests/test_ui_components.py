"""Unit tests for Streamlit UI components, rank badges, and helper functions."""
import pytest
from app.ui.components import (
    get_rank_badge,
    render_tag_chips,
    CUSTOM_CSS
)

def test_get_rank_badge_thresholds():
    """Verify rank badge title and color matching Codeforces official division scales."""
    assert get_rank_badge(None) == ("Unrated", "#94a3b8")
    assert get_rank_badge(0) == ("Unrated", "#94a3b8")
    assert get_rank_badge(1000) == ("Newbie", "#808080")
    assert get_rank_badge(1250) == ("Pupil", "#008000")
    assert get_rank_badge(1450) == ("Specialist", "#03a89e")
    assert get_rank_badge(1650) == ("Expert", "#0000ff")
    assert get_rank_badge(1950) == ("Candidate Master", "#aa00aa")
    assert get_rank_badge(2150) == ("Master", "#ff8c00")
    assert get_rank_badge(2350) == ("International Master", "#ff8c00")
    assert get_rank_badge(2450) == ("Grandmaster", "#ff0000")
    assert get_rank_badge(2650) == ("International Grandmaster", "#ff0000")
    assert get_rank_badge(3200) == ("Legendary Grandmaster", "#ff0000")

def test_render_tag_chips():
    """Verify render_tag_chips generates HTML span tags."""
    tags = ["dp", "trees", "greedy"]
    html = render_tag_chips(tags)
    for t in tags:
        assert f'<span class="badge-tag">{t}</span>' in html

def test_custom_css_structure():
    """Verify CUSTOM_CSS contains core styling tokens and font families."""
    assert "Inter" in CUSTOM_CSS
    assert "badge-rating" in CUSTOM_CSS
    assert "hint-box" in CUSTOM_CSS
    assert "agent-bubble-tutor" in CUSTOM_CSS
    assert "agent-bubble-keeper" in CUSTOM_CSS
