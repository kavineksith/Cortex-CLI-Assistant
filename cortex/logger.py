"""
cortex.logger
=============
Centralised logging configuration.

Two log streams are produced for accountability:

1. ``logs/cortex.log``   - rotating, human readable operational log
                            (INFO/DEBUG/WARNING/ERROR).
2. ``logs/audit.log``    - rotating, one-line-per-event JSON audit trail
                            of every user command and its outcome, so a
                            run can be reconstructed after the fact.

Both handlers rotate at 1 MB with 5 backups kept, which bounds disk and
memory usage for long running sessions (memory management concern).
"""

from __future__ import annotations
import json
import logging
import logging.handlers
import os
import datetime

_LOG_DIR_DEFAULT = os.path.join(os.getcwd(), "logs")


class JsonAuditFormatter(logging.Formatter):
    """Formats audit records as a single JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        extra = getattr(record, "extra_data", None)
        if extra:
            payload["data"] = extra
        return json.dumps(payload, default=str)


def setup_logging(log_dir: str | None = None, level: int = logging.INFO) -> tuple[logging.Logger, logging.Logger]:
    """Configure and return (operational_logger, audit_logger).

    Idempotent: calling this more than once will not duplicate handlers.
    """
    log_dir = log_dir or _LOG_DIR_DEFAULT
    os.makedirs(log_dir, exist_ok=True)

    op_logger = logging.getLogger("cortex")
    audit_logger = logging.getLogger("cortex.audit")

    if op_logger.handlers:  # already configured
        return op_logger, audit_logger

    op_logger.setLevel(level)
    op_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "cortex.log"), maxBytes=1_000_000, backupCount=5
    )
    op_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    op_logger.addHandler(op_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    op_logger.addHandler(console_handler)

    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    audit_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "audit.log"), maxBytes=1_000_000, backupCount=5
    )
    audit_handler.setFormatter(JsonAuditFormatter())
    audit_logger.addHandler(audit_handler)

    return op_logger, audit_logger


def audit(audit_logger: logging.Logger, event: str, **data) -> None:
    """Record a single accountable event, e.g. a command execution."""
    audit_logger.info(event, extra={"extra_data": data})
