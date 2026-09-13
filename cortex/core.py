"""
cortex.core
===========
The ``Assistant`` class wires every manager together and drives the
interactive REPL loop. Two coroutines run **in parallel** for the
whole life of a session:

1. the reminder-checker background task (``ReminderManager.start``)
2. the interactive read-eval-print loop (``Assistant.run``)

``asyncio.gather`` combined with ``run_in_executor`` for the blocking
``input()`` call keeps the terminal responsive while reminders can
still fire on schedule.
"""

from __future__ import annotations
import asyncio
import datetime
import logging

from . import nlp
from .exceptions import CortexError, CommandParseError
from .logger import setup_logging, audit
from .managers import TaskManager, ReminderManager, AdviceManager
from .preferences import UserPreferences
from .storage import StorageManager

_logger, _audit_logger = setup_logging()


class Assistant:
    """Coordinates storage, managers and the command loop.

    Implements ``__aenter__``/``__aexit__`` so it can be used as:

        async with Assistant() as assistant:
            await assistant.run()
    """

    def __init__(self, data_dir: str | None = None):
        self.storage = StorageManager(data_dir)
        self.preferences = UserPreferences(self.storage)
        self.tasks = TaskManager(self.storage)
        self.advice = AdviceManager(self.storage)
        self.reminders = ReminderManager(self.storage, on_trigger=self._on_reminder)
        self._running = False

    def __repr__(self) -> str:
        return f"Assistant(tasks={len(self.tasks)}, reminders={len(self.reminders)})"

    async def __aenter__(self) -> "Assistant":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.shutdown()

    async def _on_reminder(self, reminder) -> None:
        print(f"\n[REMINDER] {reminder.text}")

    async def handle_command(self, command_data: dict) -> str:
        """Execute a parsed command, returning the text to display."""
        command = command_data["command"]
        params = command_data.get("params", {})
        outcome = "ok"
        response = ""
        try:
            if command == "greeting":
                name = await self.preferences.get("name", "User")
                response = f"Hello {name}! How can I help you today?"
            elif command == "help":
                response = (
                    "Commands: hello, what's the time, what's the date, "
                    "advice, exit. Use the CLI subcommands (add-task, "
                    "list-tasks, add-reminder, ...) for structured actions."
                )
            elif command == "time_query":
                response = f"The current time is {datetime.datetime.now().strftime('%I:%M %p')}."
            elif command == "date_query":
                response = f"Today's date is {datetime.datetime.now().strftime('%B %d, %Y')}."
            elif command == "advice_query":
                response = f"Here's some advice: {await self.advice.get_random()}"
            elif command == "exit":
                response = "Goodbye! Have a great day."
                self._running = False
            else:
                response = "I'm not sure how to help with that. Try 'help'."
                outcome = "unhandled"
        except CortexError as exc:
            _logger.error(str(exc))
            response = f"Sorry, something went wrong: {exc.message}"
            outcome = "error"
        finally:
            audit(_audit_logger, "command_handled", command=command, outcome=outcome)
        return response

    async def _input_loop(self) -> None:
        loop = asyncio.get_running_loop()
        self._running = True
        name = await self.preferences.get("name", "User")
        print(f"Hello {name}! I'm Cortex. Type 'help' for commands, 'exit' to quit.")
        while self._running:
            try:
                user_text = await loop.run_in_executor(None, input, "cortex> ")
            except (EOFError, KeyboardInterrupt):
                break
            try:
                command_data = nlp.parse(user_text)
            except CommandParseError:
                continue
            reply = await self.handle_command(command_data)
            if reply:
                print(reply)

    async def run(self, reminder_interval: int = 30) -> None:
        """Run the interactive loop and the reminder checker in parallel."""
        self.reminders.start(interval=reminder_interval)
        try:
            await self._input_loop()
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        await self.reminders.stop()
        async with self.storage:
            pass
        _logger.info("Assistant session ended cleanly.")

    def __del__(self):
        # Best-effort accountability trail even on unexpected GC.
        try:
            logging.getLogger("cortex").debug("Assistant instance garbage collected.")
        except Exception:
            pass
