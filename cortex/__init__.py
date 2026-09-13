"""Cortex CLI Assistant - async, parallel, accountable task/reminder helper."""

from .core import Assistant
from .exceptions import CortexError

__all__ = ["Assistant", "CortexError"]
__version__ = "2.0.0"
