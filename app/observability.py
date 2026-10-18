"""Observability and distributed tracing utilities integrating LangSmith with LangGraph."""
import os
import logging
from typing import Any

from app.config import settings, AppConfig

logger = logging.getLogger(__name__)

def configure_langsmith(cfg: AppConfig | None = None) -> bool:
    """Synchronize LangSmith configuration to environment variables for LangGraph tracing.
    
    Returns:
        bool: True if LangSmith tracing is enabled and active, False otherwise.
    """
    app_cfg = cfg or settings
    api_key = app_cfg.langchain_api_key or os.getenv("LANGCHAIN_API_KEY", "")
    explicit_tracing = (
        app_cfg.langchain_tracing_v2
        or os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")
    )
    
    is_explicit_false = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("false", "0", "no")
    enabled = explicit_tracing or (bool(api_key) and not is_explicit_false)

    if enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        if api_key:
            os.environ["LANGCHAIN_API_KEY"] = api_key
            
        project = app_cfg.langchain_project or os.getenv("LANGCHAIN_PROJECT", "cp-coach")
        os.environ["LANGCHAIN_PROJECT"] = project

        endpoint = app_cfg.langchain_endpoint or os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint

        logger.info(f"[Observability] LangSmith tracing ENABLED (Project: '{project}', Endpoint: '{endpoint}')")
        return True
    else:
        logger.debug("[Observability] LangSmith tracing disabled.")
        return False

def is_langsmith_enabled() -> bool:
    """Check whether LangSmith tracing is currently enabled."""
    return os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")

def get_langsmith_config(
    thread_id: str,
    handle: str = "anonymous",
    environment: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    run_name: str | None = None,
) -> dict[str, Any]:
    """Construct a LangGraph configuration dictionary with rich metadata and tags for LangSmith."""
    env_name = environment or settings.environment
    default_tags = ["cp-coach", f"env:{env_name}"]
    if tags:
        default_tags.extend(tags)
        
    meta = {
        "handle": handle,
        "environment": env_name,
        "thread_id": thread_id,
    }
    if metadata:
        meta.update(metadata)
        
    return {
        "configurable": {"thread_id": thread_id},
        "tags": list(dict.fromkeys(default_tags)),
        "metadata": meta,
        "run_name": run_name or f"cp_coach_{handle}_{thread_id[:8]}",
    }

def record_langsmith_feedback(
    run_id: str | None,
    key: str,
    score: float,
    comment: str = "",
) -> bool:
    """Safely log user or evaluator feedback to a LangSmith run without raising exceptions.
    
    Args:
        run_id: The UUID string of the LangSmith run.
        key: The feedback metric name (e.g. 'pedagogical_utility', 'spoiler_leakage').
        score: Numeric feedback value (e.g. 1.0 for helpful, 0.0 for spoiler).
        comment: Optional descriptive feedback text.
        
    Returns:
        bool: True if feedback was successfully submitted, False otherwise.
    """
    if not run_id:
        logger.debug("[Observability] Cannot record feedback: No run_id provided.")
        return False

    if not is_langsmith_enabled() or not os.getenv("LANGCHAIN_API_KEY"):
        logger.debug("[Observability] Skipping feedback: LangSmith not active or API key absent.")
        return False

    try:
        from langsmith import Client
        client = Client()
        client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
            comment=comment or None
        )
        logger.info(f"[Observability] Recorded feedback for run {run_id}: {key}={score}")
        return True
    except Exception as e:
        logger.warning(f"[Observability] Failed to record LangSmith feedback ({e}). Continuing safely.")
        return False