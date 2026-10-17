"""Safe structured logging helpers."""

from __future__ import annotations

import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format only known-safe logging fields as a compact JSON record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "event": getattr(record, "event", record.getMessage()),
            "level": record.levelname,
            "logger": record.name,
        }
        provider = getattr(record, "provider", None)
        if provider is not None:
            payload["provider"] = provider
        return json.dumps(payload, sort_keys=True)


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Return the package logger configured with a safe structured formatter."""
    logger = logging.getLogger("openagent_realtime_convo")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


def log_configuration_loaded(logger: logging.Logger, provider_name: str) -> None:
    """Log safe configuration metadata; credentials are intentionally omitted."""
    logger.info(
        "configuration_loaded",
        extra={"event": "configuration_loaded", "provider": provider_name},
    )
