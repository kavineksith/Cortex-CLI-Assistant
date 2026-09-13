"""
cortex.preferences
===================
Simple async-backed preferences store with sane defaults.
"""

from __future__ import annotations
from .storage import StorageManager

_DEFAULTS = {
    "name": "User",
    "reminder_check_interval": 30,
    "timezone": "local",
}


class UserPreferences:
    FILE = "user_preferences.json"

    def __init__(self, storage: StorageManager):
        self.storage = storage
        self._prefs: dict = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        stored = await self.storage.load_data(self.FILE, default={})
        merged = {**_DEFAULTS, **(stored or {})}
        self._prefs = merged
        self._loaded = True

    async def get(self, key: str, default=None):
        await self._ensure_loaded()
        return self._prefs.get(key, default)

    async def set(self, key: str, value) -> None:
        await self._ensure_loaded()
        self._prefs[key] = value
        await self.storage.save_data(self.FILE, self._prefs)

    def __repr__(self) -> str:
        return f"UserPreferences({self._prefs!r})"
