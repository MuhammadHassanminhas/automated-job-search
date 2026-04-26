from __future__ import annotations

import logging
import re

import structlog

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PII_FIELDS = frozenset({"resume_md", "cover_letter_md", "email_body", "body"})


def _redact_pii(
    _logger: object,  # noqa: ARG001  # structlog processor protocol
    _method_name: str,  # noqa: ARG001  # structlog processor protocol
    event_dict: dict,
) -> dict:
    for field in _PII_FIELDS:
        if event_dict.get(field):
            event_dict[field] = "[REDACTED]"
    if isinstance(event_dict.get("event"), str):
        event_dict["event"] = _EMAIL_RE.sub("[REDACTED_EMAIL]", event_dict["event"])
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            _redact_pii,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


logger = structlog.get_logger()
