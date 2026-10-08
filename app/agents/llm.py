"""Unified LLM client factory supporting Gemini, OpenAI, Anthropic, and local mock fallback."""
import os
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

class MockLLM:
    """Deterministic fallback LLM for testing or when API keys are absent."""
    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name

    def invoke(self, messages: Any) -> Any:
        prompt_str = str(messages)
        
        if "Audit the draft strictly" in prompt_str or "Private Reference Solution" in prompt_str:
            if "dp[" in prompt_str and "Level 1" in prompt_str:
                content = json.dumps({
                    "approved": False,
                    "reason": "Level 1 hint leaked dynamic programming recurrence notation (dp[...]).",
                    "leak_severity": "major"
                })
            else:
                content = json.dumps({
                    "approved": True,
                    "reason": "Hint satisfies safety guidelines for the requested level.",
                    "leak_severity": "none"
                })
        elif "Submission Verdict" in prompt_str:
            content = "Diagnostic Hint: Verify base conditions and handle single-child or edge-case constraints carefully."
        elif "Level 1" in prompt_str:
            content = "Observe how each step reduces the problem state. What invariant remains unchanged?"
        elif "Level 2" in prompt_str:
            content = "Traverse the tree structure using Depth-First Search and compute the transition costs at each node."
        else:
            content = "Let dp[u] be the minimum operations to reach a leaf. Compute dp[u] = min(dp[left], dp[right])."

        class MockResponse:
            def __init__(self, text: str):
                self.content = text
        return MockResponse(content)

def get_llm(model_type: str = "tutor") -> Any:
    """Instantiate configured LLM provider or fallback to MockLLM."""
    google_key = os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if google_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model_name = os.getenv("TUTOR_MODEL_NAME", "gemini-1.5-flash") if model_type == "tutor" else os.getenv("KEEPER_MODEL_NAME", "gemini-1.5-flash")
            return ChatGoogleGenerativeAI(model=model_name, google_api_key=google_key, temperature=0.2)
        except ImportError:
            pass

    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            model_name = "gpt-4o" if model_type == "tutor" else "gpt-4o-mini"
            return ChatOpenAI(model=model_name, api_key=openai_key, temperature=0.2)
        except ImportError:
            pass

    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model="claude-3-5-sonnet-20240620", api_key=anthropic_key, temperature=0.2)
        except ImportError:
            pass

    return MockLLM(model_name=f"mock-{model_type}")
