"""
cortex.models
=============
Lightweight data models for Tasks and Reminders.

``__slots__`` is used on every model to cut per-instance memory
overhead (no per-object ``__dict__``), which matters once a session
accumulates thousands of tasks/reminders in memory.

Each model implements a set of dunder methods so they behave like
proper first class objects instead of bare dicts:

* ``__repr__``   - unambiguous debug representation
* ``__str__``    - human friendly display string
* ``__eq__`` / ``__hash__`` - value based comparisons
* ``__lt__``     - default sort order (by priority / time)
* ``__iter__``   - allows ``dict(task)`` style conversion
"""

from __future__ import annotations
import datetime
import itertools
from typing import Iterator

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


class Task:
    __slots__ = ("id", "description", "due_date", "priority", "status", "created_at")

    _id_counter = itertools.count(1)

    def __init__(
        self,
        description: str,
        due_date: str | None = None,
        priority: str = "medium",
        status: str = "pending",
        created_at: str | None = None,
        id: int | None = None,
    ):
        self.id = id if id is not None else next(Task._id_counter)
        self.description = description
        self.due_date = due_date
        self.priority = priority if priority in _PRIORITY_RANK else "medium"
        self.status = status
        self.created_at = created_at or datetime.datetime.now().isoformat()

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id}, description={self.description!r}, "
            f"priority={self.priority!r}, status={self.status!r})"
        )

    def __str__(self) -> str:
        due = f", due {self.due_date}" if self.due_date else ""
        return f"#{self.id} [{self.priority}] {self.description} ({self.status}{due})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Task) and self.id == other.id

    def __hash__(self) -> int:
        return hash(("Task", self.id))

    def __lt__(self, other: "Task") -> bool:
        return _PRIORITY_RANK.get(self.priority, 9) < _PRIORITY_RANK.get(other.priority, 9)

    def __iter__(self) -> Iterator[tuple[str, object]]:
        for key in self.__slots__:
            yield key, getattr(self, key)

    def to_dict(self) -> dict:
        return dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(**data)


class Reminder:
    __slots__ = ("id", "text", "time", "created_at", "active")

    _id_counter = itertools.count(1)

    def __init__(
        self,
        text: str,
        time: str,
        created_at: str | None = None,
        active: bool = True,
        id: int | None = None,
    ):
        self.id = id if id is not None else next(Reminder._id_counter)
        self.text = text
        self.time = time
        self.created_at = created_at or datetime.datetime.now().isoformat()
        self.active = active

    def __repr__(self) -> str:
        return f"Reminder(id={self.id}, text={self.text!r}, time={self.time!r}, active={self.active})"

    def __str__(self) -> str:
        state = "active" if self.active else "done"
        return f"#{self.id} at {self.time} - {self.text} [{state}]"

    def __eq__(self, other) -> bool:
        return isinstance(other, Reminder) and self.id == other.id

    def __hash__(self) -> int:
        return hash(("Reminder", self.id))

    def __iter__(self) -> Iterator[tuple[str, object]]:
        for key in self.__slots__:
            yield key, getattr(self, key)

    def to_dict(self) -> dict:
        return dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Reminder":
        return cls(**data)
