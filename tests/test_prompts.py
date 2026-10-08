"""Unit tests for prompt formatting and rubric builders."""
import pytest
from app.prompts.tutor_prompt import build_tutor_prompt, TUTOR_SYSTEM_PROMPT
from app.prompts.keeper_prompt import build_keeper_prompt, KEEPER_SYSTEM_PROMPT
from app.prompts.targeted_hint_prompt import build_targeted_hint_prompt

def test_tutor_prompt_levels():
    p1 = build_tutor_prompt("Problem ABC", hint_level=1)
    assert "Level 1" in p1
    assert "Problem ABC" in p1
    
    p2 = build_tutor_prompt("Problem ABC", hint_level=2)
    assert "Level 2" in p2
    
    p3 = build_tutor_prompt("Problem ABC", hint_level=3)
    assert "Level 3" in p3

def test_tutor_prompt_with_feedback():
    p = build_tutor_prompt("Problem ABC", hint_level=1, keeper_feedback="Do not mention segment tree")
    assert "CRITICAL - Previous Draft Rejected by Keeper" in p
    assert "Do not mention segment tree" in p

def test_keeper_prompt_structure():
    kp = build_keeper_prompt("Statement 123", "int solution();", hint_level=2, draft_text="Draft hint text")
    assert "Statement 123" in kp
    assert "int solution();" in kp
    assert "Draft hint text" in kp

def test_targeted_hint_prompt():
    th = build_targeted_hint_prompt("Statement XYZ", "TIME_LIMIT_EXCEEDED")
    assert "TIME_LIMIT_EXCEEDED" in th
    assert "Statement XYZ" in th
