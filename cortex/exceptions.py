"""
cortex.exceptions
==================
Custom, OOP based exception hierarchy for the Cortex CLI Assistant.

Every exception carries an internal `code` (used for accountability /
audit logging) and a human readable `message`. Overriding `__str__`
and `__repr__` gives consistent, greppable log lines, e.g.:

    [CORTEX-1002] StorageError: Could not write tasks.json (disk full)
"""

from __future__ import annotations
import datetime


class CortexError(Exception):
    """Base class for every error raised inside the Cortex assistant.

    Attributes:
        message (str): Human readable description of the failure.
        code (int): Stable numeric error code for log correlation.
        timestamp (datetime.datetime): When the error was constructed.
    """

    code: int = 1000

    def __init__(self, message: str, *, code: int | None = None):
        self.message = message
        self.code = code if code is not None else self.__class__.code
        self.timestamp = datetime.datetime.now()
        super().__init__(self.message)

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"[CORTEX-{self.code}] {self.__class__.__name__}: {self.message}"

    def __repr__(self) -> str:  # pragma: no cover - trivial formatting
        return (
            f"{self.__class__.__name__}(message={self.message!r}, "
            f"code={self.code}, timestamp={self.timestamp.isoformat()!r})"
        )

    def to_dict(self) -> dict:
        """Serialise the error for structured/audit logging."""
        return {
            "error": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


class ConfigurationError(CortexError):
    """Raised when configuration / preferences cannot be loaded or are invalid."""
    code = 1001


class StorageError(CortexError):
    """Raised when reading/writing a JSON data file fails."""
    code = 1002


class ValidationError(CortexError):
    """Raised when user supplied data fails validation (bad date, empty text, ...)."""
    code = 1003


class TaskNotFoundError(CortexError):
    """Raised when a task id does not exist."""
    code = 1004


class ReminderError(CortexError):
    """Raised for reminder scheduling/parsing failures."""
    code = 1005


class CommandParseError(CortexError):
    """Raised when the NLP/command engine cannot parse user input."""
    code = 1006


class ConcurrencyError(CortexError):
    """Raised when a parallel task (asyncio task / process) fails unexpectedly."""
    code = 1007
