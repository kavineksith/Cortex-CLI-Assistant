"""
cortex.nlp
==========
A small, dependency-free command parser. Kept intentionally simple
(regex based) so the whole project runs with zero external services -
no internet/API key needed for the CLI to be usable.
"""

from __future__ import annotations
import re

from .exceptions import CommandParseError

_PATTERNS: dict[str, str] = {
    "greeting": r"\b(?:hey|hi|hello)\b",
    "help": r"\b(?:help|commands|what can you do)\b",
    "time_query": r"\b(?:what'?s the time|current time)\b",
    "date_query": r"\b(?:what'?s the date|today'?s date)\b",
    "advice_query": r"\b(?:advice|advise me|give me advice)\b",
    "exit": r"\b(?:exit|quit|goodbye|bye)\b",
}


def parse(text: str) -> dict:
    """Parse free text into a ``{"command": ..., "params": {...}}`` dict.

    Raises:
        CommandParseError: if ``text`` is empty/whitespace only.
    """
    if text is None or not text.strip():
        raise CommandParseError("Empty input received.")

    lowered = text.lower().strip()
    for command, pattern in _PATTERNS.items():
        if re.search(pattern, lowered):
            return {"command": command, "params": {"text": text}}

    return {"command": "unknown", "params": {"text": text}}
