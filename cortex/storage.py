"""
cortex.storage
==============
Async, cached, crash-safe JSON storage layer.

Design notes
------------
* All disk I/O runs through ``asyncio.to_thread`` so blocking file
  operations never stall the event loop that also drives the reminder
  checker / input loop, while keeping the project dependency-free
  (standard library only).
* Writes are atomic: data is written to a ``.tmp`` file and then
  ``os.replace``'d into place, so a crash mid-write can never corrupt
  the real file.
* An ``asyncio.Lock`` per filename prevents two concurrent coroutines
  from writing the same file at once (a real risk once the reminder
  checker and the command loop run in parallel).
* ``BoundedCache`` caps how many parsed JSON payloads are kept in
  memory at once (a simple LRU via ``OrderedDict``) - this is the
  "memory management" piece: long sessions touching many files won't
  grow memory without bound.
"""

from __future__ import annotations
import asyncio
import json
import os
from collections import OrderedDict
from typing import Any

from .exceptions import StorageError
from .logger import setup_logging, audit as _audit_event

_logger, _audit_logger = setup_logging()


class BoundedCache:
    """A tiny LRU cache with dunder support (``len``, ``in``, ``[]``)."""

    def __init__(self, max_items: int = 32):
        self._max_items = max_items
        self._store: "OrderedDict[str, Any]" = OrderedDict()

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __getitem__(self, key: str) -> Any:
        value = self._store[key]
        self._store.move_to_end(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self._max_items:
            evicted_key, _ = self._store.popitem(last=False)
            _logger.debug("Cache eviction: %s", evicted_key)

    def __delitem__(self, key: str) -> None:
        del self._store[key]

    def get(self, key: str, default=None):
        return self._store[key] if key in self._store else default


class StorageManager:
    """Async JSON file storage with an in-memory bounded cache."""

    def __init__(self, data_dir: str | None = None, cache_size: int = 32):
        self.data_dir = data_dir or os.path.join(os.path.expanduser("~"), ".cortex_assistant")
        self._cache = BoundedCache(max_items=cache_size)
        self._locks: dict[str, asyncio.Lock] = {}
        self._ensure_data_directory()

    def __repr__(self) -> str:
        return f"StorageManager(data_dir={self.data_dir!r}, cached_files={len(self._cache)})"

    def _ensure_data_directory(self) -> None:
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Failed to create data directory {self.data_dir}: {exc}") from exc

    def _lock_for(self, filename: str) -> asyncio.Lock:
        if filename not in self._locks:
            self._locks[filename] = asyncio.Lock()
        return self._locks[filename]

    def path_for(self, filename: str) -> str:
        return os.path.join(self.data_dir, filename)

    async def save_data(self, filename: str, data: Any) -> bool:
        """Atomically persist ``data`` as JSON under ``filename``."""
        file_path = self.path_for(filename)
        tmp_path = file_path + ".tmp"

        def _write() -> None:
            with open(tmp_path, "w") as fh:
                fh.write(json.dumps(data, indent=2, default=str))
            os.replace(tmp_path, file_path)

        async with self._lock_for(filename):
            try:
                await asyncio.to_thread(_write)
                self._cache[filename] = data
                _audit_event(_audit_logger, "storage_write", filename=filename)
                return True
            except (OSError, TypeError) as exc:
                _logger.error("Failed to save %s: %s", filename, exc)
                raise StorageError(f"Error saving data to {filename}: {exc}") from exc

    async def load_data(self, filename: str, default: Any = None):
        """Load JSON data, using the bounded cache when possible."""
        if filename in self._cache:
            return self._cache[filename]

        file_path = self.path_for(filename)
        if not os.path.exists(file_path):
            return default if default is not None else {}

        def _read() -> str:
            with open(file_path, "r") as fh:
                return fh.read()

        async with self._lock_for(filename):
            try:
                raw = await asyncio.to_thread(_read)
                data = json.loads(raw) if raw.strip() else (default if default is not None else {})
                self._cache[filename] = data
                return data
            except json.JSONDecodeError as exc:
                _logger.error("Corrupt JSON in %s: %s", filename, exc)
                return default if default is not None else {}
            except OSError as exc:
                raise StorageError(f"Error reading {filename}: {exc}") from exc

    async def __aenter__(self) -> "StorageManager":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # Nothing persistent to release, but flushing the cache keeps
        # memory bounded between long-lived assistant sessions.
        self._cache = BoundedCache(max_items=self._cache._max_items)
