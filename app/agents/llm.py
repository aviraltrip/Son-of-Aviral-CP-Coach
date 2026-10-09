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
        if isinstance(messages, list):
            prompt_str = "\n".join(
                m.get("content", "") if isinstance(m, dict) else getattr(m, "content", str(m))
                for m in messages
            )
            last_m = messages[-1] if messages else {}
            user_content = last_m.get("content", "") if isinstance(last_m, dict) else getattr(last_m, "content", str(last_m))
        else:
            prompt_str = str(messages)
            user_content = prompt_str
        
        # 1. Keeper Audit Prompts
        if "Audit the draft strictly" in prompt_str or "Private Reference Solution" in prompt_str:
            draft_part = ""
            if "Tutor's Draft Hint to Audit:" in prompt_str:
                draft_part = prompt_str.split("Tutor's Draft Hint to Audit:")[1]
            else:
                draft_part = prompt_str
                
            if "Level 1" in prompt_str and ("dp[" in draft_part or "leak" in draft_part.lower()):
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
                
        # 2. Targeted Diagnostics on WA / TLE
        elif "TIME_LIMIT_EXCEEDED" in prompt_str or "TIME_LIMIT_EXCEEDED" in user_content:
            content = "Diagnostic Hint: Your solution might be recomputing values. Aim for a single tree traversal in O(N) time."
        elif "WRONG_ANSWER" in prompt_str or "WRONG_ANSWER" in user_content:
            content = "Diagnostic Hint: Your logic may miss key edge cases. Check if the root is already a leaf."
        elif "Submission Verdict" in prompt_str or "Submission Verdict" in user_content:
            content = "Diagnostic Hint: Verify base conditions and handle single-child or edge-case constraints carefully."
            
        # 3. Tutor Hint Generation
        elif "Previous Draft Rejected by Keeper" in user_content:
            content = "[Revision 1] Think about problem constraints and what each choice represents."
        elif "Level 3" in user_content:
            content = "Let dp[u] be min modifications. For leaf dp[u]=0, else dp[u] = min(dp[left] + (s[u]!='L'), dp[right] + (s[u]!='R'))."
        elif "Level 2" in user_content:
            content = "Consider defining a tree traversal (like DFS). At each vertex, calculate the cost of moving left vs right."
        elif "Level 1" in user_content:
            content = "Notice that from any node, you want to reach any valid leaf with minimum operations. What does the optimal path look like?"
        else:
            content = "Notice that from any node, you want to reach any valid leaf with minimum operations. What does the optimal path look like?"

        class MockResponse:
            def __init__(self, text: str):
                self.content = text
        return MockResponse(content)

def get_llm(model_type: str = "tutor") -> Any:
    """Instantiate configured LLM provider or fallback to MockLLM."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if openrouter_key:
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
            if model_type == "tutor":
                model_name = os.getenv("TUTOR_MODEL_NAME", "anthropic/claude-3.5-sonnet")
            elif model_type == "analyst":
                model_name = os.getenv("ANALYST_MODEL_NAME", "openai/gpt-4o-mini")
            else:
                model_name = os.getenv("KEEPER_MODEL_NAME", "openai/gpt-4o-mini")

            return ChatOpenAI(
                model=model_name,
                api_key=openrouter_key,
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                temperature=0.2
            )
        except ImportError:
            pass

    if google_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
            if model_type == "tutor":
                model_name = os.getenv("TUTOR_MODEL_NAME", "gemini-1.5-flash")
            elif model_type == "analyst":
                model_name = os.getenv("ANALYST_MODEL_NAME", "gemini-1.5-flash")
            else:
                model_name = os.getenv("KEEPER_MODEL_NAME", "gemini-1.5-flash")
            return ChatGoogleGenerativeAI(model=model_name, google_api_key=google_key, temperature=0.2)
        except ImportError:
            pass

    if openai_key:
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
            if model_type == "tutor":
                model_name = os.getenv("TUTOR_MODEL_NAME", "gpt-4o")
            elif model_type == "analyst":
                model_name = os.getenv("ANALYST_MODEL_NAME", "gpt-4o-mini")
            else:
                model_name = os.getenv("KEEPER_MODEL_NAME", "gpt-4o-mini")
            return ChatOpenAI(model=model_name, api_key=openai_key, temperature=0.2)
        except ImportError:
            pass

    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore
            model_name = os.getenv("TUTOR_MODEL_NAME", "claude-3-5-sonnet-20240620") if model_type == "tutor" else os.getenv("KEEPER_MODEL_NAME", "claude-3-haiku-20240307")
            return ChatAnthropic(model=model_name, api_key=anthropic_key, temperature=0.2)
        except ImportError:
            pass

    return MockLLM(model_name=f"mock-{model_type}")
