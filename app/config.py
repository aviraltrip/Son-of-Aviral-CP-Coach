import os
from typing import Literal
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=True)

class AppConfig(BaseSettings):
    """Strongly-typed application settings loaded from environment variables."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    environment: Literal["development", "production", "testing"] = Field(
        default="development",
        description="Application operational mode"
    )

    database_path: str = Field(default="cp_coach.db", description="SQLite database path")
    checkpoints_db_path: str = Field(default="checkpoints.db", description="LangGraph checkpoints SQLite path")
    checkpoints_persist: bool = Field(default=True, description="Enable persistent checkpointer")

    judge_backend: Literal["isolated_subprocess", "judge0", "disabled"] = Field(
        default="isolated_subprocess",
        description="Execution engine for code submissions"
    )
    judge0_url: str = Field(default="https://judge0-ce.p.rapidapi.com", description="Judge0 instance base URL")
    judge0_api_key: str = Field(default="", description="Judge0 API Key")

    auth_mode: Literal["disabled", "optional", "required"] = Field(
        default="optional",
        description="User authentication requirement level"
    )
    app_passkey: str = Field(default="", description="Master passkey for privileged access")

    google_api_key: str = Field(default="", description="Google Gemini API Key")
    openrouter_api_key: str = Field(default="", description="OpenRouter API Key")
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")

    tutor_model_name: str = Field(default="gemini-1.5-flash")
    keeper_model_name: str = Field(default="gemini-1.5-flash")
    analyst_model_name: str = Field(default="gemini-1.5-flash")

    langchain_tracing_v2: bool = Field(default=False, description="Enable LangSmith distributed tracing")
    langchain_api_key: str = Field(default="", description="LangSmith API Key")
    langchain_project: str = Field(default="cp-coach", description="LangSmith project name")
    langchain_endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith API endpoint")

    def has_any_llm_key(self) -> bool:
        """Check if at least one valid LLM provider API key is configured."""
        return bool(
            self.google_api_key
            or os.getenv("GEMINI_API_KEY")
            or self.openrouter_api_key
            or self.openai_api_key
            or self.anthropic_api_key
        )

    def validate_production_readiness(self) -> list[str]:
        """Verify configuration against production security standards."""
        warnings: list[str] = []
        if self.environment == "production":
            if not self.has_any_llm_key():
                warnings.append("No real LLM provider API keys configured in production environment.")
            if self.judge_backend == "isolated_subprocess":
                warnings.append("Judge backend is set to local subprocess; external sandbox (judge0) is recommended for production multi-tenancy.")
            if self.auth_mode == "disabled":
                warnings.append("Authentication is disabled in production environment.")
        return warnings

def sync_langsmith_env(target_cfg: AppConfig | None = None) -> bool:
    """Sync LangSmith configuration directly to process environment variables for LangGraph tracing."""
    target = target_cfg or settings
    api_key = target.langchain_api_key or os.getenv("LANGCHAIN_API_KEY", "")
    explicit_tracing = (
        target.langchain_tracing_v2
        or os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")
    )
    is_explicit_false = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("false", "0", "no")
    enabled = explicit_tracing or (bool(api_key) and not is_explicit_false)
    if enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        if api_key:
            os.environ["LANGCHAIN_API_KEY"] = api_key
        project = target.langchain_project or os.getenv("LANGCHAIN_PROJECT", "cp-coach")
        os.environ["LANGCHAIN_PROJECT"] = project
        endpoint = target.langchain_endpoint or os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
        return True
    return False

settings = AppConfig()
sync_langsmith_env(settings)

def get_settings() -> AppConfig:
    """Return singleton application settings instance."""
    return settings

