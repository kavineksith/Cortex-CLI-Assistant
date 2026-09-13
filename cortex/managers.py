"""
cortex.managers
===============
Business-logic managers: tasks, reminders and advice.

Highlights
----------
* ``TaskManager.iter_tasks`` is an **async generator** - callers use
  ``async for task in manager.iter_tasks(...)`` and never have to hold
  the whole list in memory at once if the backing store grows large.
* ``TaskManager.score_tasks_parallel`` demonstrates **parallel**
  (CPU-bound) execution using ``concurrent.futures.ProcessPoolExecutor``
  run from the asyncio loop via ``run_in_executor``.
* ``ReminderManager`` runs its due-reminder checks as a background
  ``asyncio.Task`` so it executes concurrently with the interactive
  command loop (parallel I/O-bound work).
* ``AdviceManager`` implements ``__iter__``/``__next__`` so it can be
  used directly as a Python iterator (``next(advice_manager)``) with a
  自动 shuffle-and-cycle behaviour.
"""

from __future__ import annotations
import asyncio
import datetime
import random
import re
from concurrent.futures import ProcessPoolExecutor
from typing import AsyncIterator, Iterable

from .exceptions import TaskNotFoundError, ValidationError, ReminderError, ConcurrencyError
from .logger import setup_logging, audit
from .models import Task, Reminder
from .storage import StorageManager

_logger, _audit_logger = setup_logging()

_PRIORITY_WEIGHTS = {"high": 3, "medium": 2, "low": 1}


def _score_task(task_dict: dict) -> tuple[int, int]:
    """Pure function (importable/picklable) used for parallel scoring.

    Runs in a worker process - deliberately CPU-bound & side-effect
    free so it is safe to execute outside the main event loop.
    """
    weight = _PRIORITY_WEIGHTS.get(task_dict.get("priority", "medium"), 2)
    overdue_penalty = 0
    due = task_dict.get("due_date")
    if due:
        try:
            due_dt = datetime.datetime.fromisoformat(due)
            if due_dt < datetime.datetime.now():
                overdue_penalty = 5
        except ValueError:
            pass
    return task_dict["id"], weight + overdue_penalty


class TaskManager:
    FILE = "tasks.json"

    def __init__(self, storage: StorageManager):
        self.storage = storage
        self._tasks: list[Task] = []
        self._loaded = False

    def __len__(self) -> int:
        return len(self._tasks)

    def __repr__(self) -> str:
        return f"TaskManager(tasks={len(self._tasks)})"

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        raw = await self.storage.load_data(self.FILE, default=[])
        self._tasks = [Task.from_dict(t) for t in raw]
        self._loaded = True

    async def _persist(self) -> None:
        await self.storage.save_data(self.FILE, [t.to_dict() for t in self._tasks])

    async def add_task(self, description: str, due_date: str | None, priority: str) -> Task:
        if not description or not description.strip():
            raise ValidationError("Task description cannot be empty.")
        await self._ensure_loaded()
        next_id = max((t.id for t in self._tasks), default=0) + 1
        task = Task(description=description.strip(), due_date=due_date, priority=priority, id=next_id)
        self._tasks.append(task)
        await self._persist()
        audit(_audit_logger, "task_added", id=task.id, description=task.description)
        return task

    async def update_task(self, task_id: int, updates: dict) -> Task:
        await self._ensure_loaded()
        for task in self._tasks:
            if task.id == task_id:
                for key, value in updates.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                await self._persist()
                audit(_audit_logger, "task_updated", id=task_id, updates=updates)
                return task
        raise TaskNotFoundError(f"Task ID {task_id} not found.")

    async def delete_task(self, task_id: int) -> Task:
        await self._ensure_loaded()
        for idx, task in enumerate(self._tasks):
            if task.id == task_id:
                deleted = self._tasks.pop(idx)
                await self._persist()
                audit(_audit_logger, "task_deleted", id=task_id)
                return deleted
        raise TaskNotFoundError(f"Task ID {task_id} not found.")

    async def iter_tasks(self, keyword: str | None = None) -> AsyncIterator[Task]:
        """Async generator yielding tasks, optionally filtered by keyword."""
        await self._ensure_loaded()
        pattern = re.compile(keyword, re.IGNORECASE) if keyword else None
        for task in self._tasks:
            if pattern is None or pattern.search(task.description):
                yield task
            await asyncio.sleep(0)  # cooperative yield to the event loop

    async def get_all(self) -> list[Task]:
        return [t async for t in self.iter_tasks()]

    async def score_tasks_parallel(self, max_workers: int = 4) -> dict[int, int]:
        """Score every task's urgency using a process pool (parallelism demo)."""
        await self._ensure_loaded()
        if not self._tasks:
            return {}
        loop = asyncio.get_running_loop()
        payloads = [t.to_dict() for t in self._tasks]
        try:
            with ProcessPoolExecutor(max_workers=max_workers) as pool:
                results = await asyncio.gather(
                    *[loop.run_in_executor(pool, _score_task, p) for p in payloads]
                )
            return dict(results)
        except Exception as exc:  # pragma: no cover - defensive
            raise ConcurrencyError(f"Parallel scoring failed: {exc}") from exc


class ReminderManager:
    FILE = "reminders.json"

    def __init__(self, storage: StorageManager, on_trigger=None):
        self.storage = storage
        self._reminders: list[Reminder] = []
        self._loaded = False
        self._on_trigger = on_trigger  # async callable(reminder)
        self._bg_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def __len__(self) -> int:
        return len(self._reminders)

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        raw = await self.storage.load_data(self.FILE, default=[])
        self._reminders = [Reminder.from_dict(r) for r in raw]
        self._loaded = True

    async def _persist(self) -> None:
        await self.storage.save_data(self.FILE, [r.to_dict() for r in self._reminders])

    async def add_reminder(self, text: str, time_str: str) -> Reminder:
        if not text:
            raise ValidationError("Reminder text cannot be empty.")
        try:
            parsed = datetime.datetime.strptime(time_str, "%H:%M").time()
        except ValueError as exc:
            raise ReminderError("Invalid time format, expected HH:MM.") from exc
        await self._ensure_loaded()
        next_id = max((r.id for r in self._reminders), default=0) + 1
        reminder = Reminder(text=text, time=parsed.strftime("%H:%M:%S"), id=next_id)
        self._reminders.append(reminder)
        await self._persist()
        audit(_audit_logger, "reminder_added", id=reminder.id, time=reminder.time)
        return reminder

    async def iter_active(self) -> AsyncIterator[Reminder]:
        await self._ensure_loaded()
        for reminder in self._reminders:
            if reminder.active:
                yield reminder
            await asyncio.sleep(0)

    async def _check_once(self) -> None:
        now = datetime.datetime.now().time()
        async for reminder in self.iter_active():
            r_time = datetime.datetime.strptime(reminder.time, "%H:%M:%S").time()
            delta = abs(
                datetime.datetime.combine(datetime.date.today(), now)
                - datetime.datetime.combine(datetime.date.today(), r_time)
            ).total_seconds()
            if delta < 60:
                reminder.active = False
                audit(_audit_logger, "reminder_fired", id=reminder.id, text=reminder.text)
                if self._on_trigger:
                    await self._on_trigger(reminder)
        await self._persist()

    async def _loop(self, interval: int) -> None:
        while not self._stop_event.is_set():
            try:
                await self._check_once()
            except Exception as exc:  # keep the background task alive
                _logger.error("Reminder check failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    def start(self, interval: int = 30) -> None:
        """Start the reminder checker as a parallel background task."""
        self._stop_event.clear()
        self._bg_task = asyncio.create_task(self._loop(interval), name="reminder-checker")
        _logger.info("Reminder checker started (interval=%ss)", interval)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._bg_task:
            await self._bg_task


class AdviceManager:
    """Cycles through advice strings; also usable as a plain iterator."""

    FILE = "advice.json"
    _DEFAULT_ADVICE = [
        "Take breaks and stay hydrated.",
        "Set realistic, achievable goals.",
        "Review your progress regularly.",
    ]

    def __init__(self, storage: StorageManager):
        self.storage = storage
        self._items: list[str] = []
        self._loaded = False
        self._pool: list[str] = []

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        data = await self.storage.load_data(self.FILE, default=self._DEFAULT_ADVICE)
        self._items = list(data) if data else list(self._DEFAULT_ADVICE)
        self._loaded = True
        self._refill()

    def _refill(self) -> None:
        self._pool = self._items.copy()
        random.shuffle(self._pool)

    def __iter__(self) -> "AdviceManager":
        return self

    def __next__(self) -> str:
        if not self._loaded:
            raise RuntimeError("AdviceManager not loaded; call `await get_random()` at least once first.")
        if not self._pool:
            self._refill()
        return self._pool.pop()

    async def get_random(self) -> str:
        await self._ensure_loaded()
        return next(self)
