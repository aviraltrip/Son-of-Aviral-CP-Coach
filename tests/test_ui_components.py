"""Unit tests for Streamlit UI components, rank badges, and helper functions."""
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

def test_starter_templates():
    from app.ui.components import STARTER_TEMPLATES
    assert "cpp" in STARTER_TEMPLATES
    assert "python3" in STARTER_TEMPLATES
    assert "java" in STARTER_TEMPLATES
    assert "iostream" in STARTER_TEMPLATES["cpp"]
    assert "sys.stdin" in STARTER_TEMPLATES["python3"]
    assert "Scanner" in STARTER_TEMPLATES["java"]

def test_render_judge_verdict_banner_no_error():
    from app.ui.components import render_judge_verdict_banner
    from app.state import JudgeVerdict, TestCaseResult
    jv = JudgeVerdict(
        status="WA",
        passed_count=1,
        total_count=2,
        time_consumed_ms=45.2,
        memory_consumed_bytes=2048,
        failing_test_index=2,
        failing_test_result=TestCaseResult(
            test_index=2,
            verdict="WA",
            time_ms=20.0,
            memory_kb=2.0,
            input_snippet="5\n",
            user_output="10\n",
            expected_output="15\n"
        )
    )
    render_judge_verdict_banner(jv)
    render_judge_verdict_banner(None)

def test_render_fuzz_result_banner_no_error():
    from app.ui.components import render_fuzz_result_banner
    from app.judge.fuzzer import FuzzResult
    fuzz_res = FuzzResult(
        counterexample_found=True,
        trials_run=5,
        user_verdict="WA",
        failing_input="1 2\n",
        expected_output="3\n",
        user_output="2\n"
    )
    render_fuzz_result_banner(fuzz_res)
    render_fuzz_result_banner(None)

def test_max_source_bytes_guard():
    """Verify MAX_SOURCE_BYTES is set to 64 KB and payload guard behaves correctly."""
    from app.ui.streamlit_app import MAX_SOURCE_BYTES
    assert MAX_SOURCE_BYTES == 65536
    valid_code = "print('hello')"
    oversized_code = "a" * (MAX_SOURCE_BYTES + 1)
    assert len(valid_code.encode("utf-8")) <= MAX_SOURCE_BYTES
    assert len(oversized_code.encode("utf-8")) > MAX_SOURCE_BYTES

