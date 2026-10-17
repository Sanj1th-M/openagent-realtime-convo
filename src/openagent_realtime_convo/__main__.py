"""Configuration validation entry point for local development."""

from __future__ import annotations

import sys

from .config import AppConfig, ConfigurationError
from .logging import configure_logging, log_configuration_loaded


def main() -> int:
    """Validate configuration and report a safe, structured status event."""
    logger = configure_logging()
    try:
        configuration = AppConfig.from_environment()
    except ConfigurationError as error:
        logger.error("configuration_invalid", extra={"event": "configuration_invalid"})
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    log_configuration_loaded(logger, configuration.provider.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
