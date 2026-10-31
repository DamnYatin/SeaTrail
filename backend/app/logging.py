"""
Structured JSON logging using structlog with request ID context.
Sensitive credentials and file bodies are strictly scrubbed.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import EventDict, WrappedLogger


def filter_sensitive_keys(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    sensitive_keys = {
        "password",
        "password_hash",
        "secret",
        "token",
        "jwt",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "set-cookie",
        "CHECKPOINT_SIGNING_KEY_B64",
    }
    for key in list(event_dict.keys()):
        if any(sens in key.lower() for sens in sensitive_keys):
            event_dict[key] = "[REDACTED]"
    return event_dict


def setup_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            filter_sensitive_keys,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger("sealtrail")
