"""Centralized application settings and production configuration validator."""
import os
from typing import Literal, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    """Strongly-typed application settings loaded from environment variables."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Runtime Environment
    environment: Literal["development", "production", "testing"] = Field(
        default="development",
        description="Application operational mode"
    )

    # Persistence
    database_path: str = Field(default="cp_coach.db", description="SQLite database path")
    checkpoints_db_path: str = Field(default="checkpoints.db", description="LangGraph checkpoints SQLite path")
    checkpoints_persist: bool = Field(default=True, description="Enable persistent checkpointer")

    # Sandbox Judge Configuration
    judge_backend: Literal["isolated_subprocess", "judge0", "disabled"] = Field(
        default="isolated_subprocess",
        description="Execution engine for code submissions"
    )
    judge0_url: str = Field(default="https://judge0-ce.p.rapidapi.com", description="Judge0 instance base URL")
    judge0_api_key: str = Field(default="", description="Judge0 API Key")

    # Authentication & Access Control
    auth_mode: Literal["disabled", "optional", "required"] = Field(
        default="optional",
        description="User authentication requirement level"
    )
    app_passkey: str = Field(default="", description="Master passkey for privileged access")

    # LLM Providers
    openrouter_api_key: str = Field(default="", description="OpenRouter API Key")
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")
    google_api_key: str = Field(default="", description="Google Gemini API Key")

    # Model Defaults
    tutor_model_name: str = Field(default="anthropic/claude-3.5-sonnet")
    keeper_model_name: str = Field(default="openai/gpt-4o-mini")
    analyst_model_name: str = Field(default="openai/gpt-4o-mini")

    def has_any_llm_key(self) -> bool:
        """Check if at least one valid LLM provider API key is configured."""
        return bool(
            self.openrouter_api_key
            or self.openai_api_key
            or self.anthropic_api_key
            or self.google_api_key
        )

    def validate_production_readiness(self) -> List[str]:
        """Verify configuration against production security standards."""
        warnings: List[str] = []
        if self.environment == "production":
            if not self.has_any_llm_key():
                warnings.append("No real LLM provider API keys configured in production environment.")
            if self.judge_backend == "isolated_subprocess":
                warnings.append("Judge backend is set to local subprocess; external sandbox (judge0) is recommended for production multi-tenancy.")
            if self.auth_mode == "disabled":
                warnings.append("Authentication is disabled in production environment.")
        return warnings

# Global settings instance
settings = AppConfig()
