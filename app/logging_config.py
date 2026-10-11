"""Structured JSON and standard logging configuration for CP Coach production."""
import os
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

class JSONLogFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON objects."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if hasattr(record, "thread_id"):
            log_entry["thread_id"] = record.thread_id
        if hasattr(record, "handle"):
            log_entry["handle"] = record.handle
        if hasattr(record, "audit_event"):
            log_entry["audit_event"] = record.audit_event
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def setup_logging(level: str | None = None) -> None:
    """Initialize structured logging based on environment configuration."""
    log_level_str = level or os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    use_json = os.getenv("LOG_FORMAT", "text").lower() == "json" or os.getenv("ENVIRONMENT") == "production"

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers on reload
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(JSONLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )

    root_logger.addHandler(handler)

def log_audit_event(event_name: str, payload: Dict[str, Any]) -> None:
    """Record a structured security or agent audit trail event."""
    logger = logging.getLogger("cp_coach.audit")
    extra = {"audit_event": event_name, **payload}
    logger.info(f"AUDIT [{event_name}]: {json.dumps(payload)}", extra=extra)
