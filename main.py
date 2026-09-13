#!/usr/bin/env python3
"""
main.py
=======
Command line entry point for the Cortex CLI Assistant.

Two usage modes:

    python main.py run                     # interactive REPL (parallel reminder checker)
    python main.py add-task "Buy milk" --priority high --due 2026-07-04T18:00:00
    python main.py list-tasks
    python main.py score-tasks             # parallel (multi-process) urgency scoring
    python main.py add-reminder "Call mom" 18:30
    python main.py list-reminders
    python main.py advice
    python main.py set-name "Alex"

Run ``python main.py --help`` for the full list.
"""

from __future__ import annotations
import argparse
import asyncio
import sys

from cortex.core import Assistant
from cortex.exceptions import CortexError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cortex",
        description="Cortex CLI Assistant - task, reminder and advice manager.",
    )
    parser.add_argument("--data-dir", default=None, help="Override the data directory.")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("run", help="Start the interactive assistant.")

    p_add = sub.add_parser("add-task", help="Add a new task.")
    p_add.add_argument("description")
    p_add.add_argument("--due", default=None, help="ISO 8601 due date, e.g. 2026-07-04T18:00:00")
    p_add.add_argument("--priority", default="medium", choices=["low", "medium", "high"])

    p_upd = sub.add_parser("update-task", help="Update a task field.")
    p_upd.add_argument("task_id", type=int)
    p_upd.add_argument("--status", default=None, choices=["pending", "in_progress", "completed"])
    p_upd.add_argument("--priority", default=None, choices=["low", "medium", "high"])

    p_del = sub.add_parser("delete-task", help="Delete a task by id.")
    p_del.add_argument("task_id", type=int)

    p_list = sub.add_parser("list-tasks", help="List all tasks (streams via async generator).")
    p_list.add_argument("--keyword", default=None, help="Filter by keyword.")

    sub.add_parser("score-tasks", help="Score task urgency using a process pool (parallel demo).")

    p_rem = sub.add_parser("add-reminder", help="Add a reminder.")
    p_rem.add_argument("text")
    p_rem.add_argument("time", help="HH:MM 24-hour time")

    sub.add_parser("list-reminders", help="List active reminders.")
    sub.add_parser("advice", help="Get a random piece of advice.")

    p_name = sub.add_parser("set-name", help="Set the user's preferred name.")
    p_name.add_argument("name")

    return parser


async def dispatch(args: argparse.Namespace) -> int:
    async with Assistant(data_dir=args.data_dir) as assistant:
        if args.action == "run":
            await assistant.run()
            return 0

        if args.action == "add-task":
            task = await assistant.tasks.add_task(args.description, args.due, args.priority)
            print(f"Added: {task}")

        elif args.action == "update-task":
            updates = {}
            if args.status:
                updates["status"] = args.status
            if args.priority:
                updates["priority"] = args.priority
            if not updates:
                print("Nothing to update - pass --status and/or --priority.")
                return 1
            task = await assistant.tasks.update_task(args.task_id, updates)
            print(f"Updated: {task}")

        elif args.action == "delete-task":
            task = await assistant.tasks.delete_task(args.task_id)
            print(f"Deleted: {task}")

        elif args.action == "list-tasks":
            count = 0
            async for task in assistant.tasks.iter_tasks(keyword=args.keyword):
                print(task)
                count += 1
            if count == 0:
                print("No tasks found.")

        elif args.action == "score-tasks":
            scores = await assistant.tasks.score_tasks_parallel()
            if not scores:
                print("No tasks to score.")
            for task_id, score in sorted(scores.items(), key=lambda kv: -kv[1]):
                print(f"Task #{task_id}: urgency score {score}")

        elif args.action == "add-reminder":
            reminder = await assistant.reminders.add_reminder(args.text, args.time)
            print(f"Added: {reminder}")

        elif args.action == "list-reminders":
            count = 0
            async for reminder in assistant.reminders.iter_active():
                print(reminder)
                count += 1
            if count == 0:
                print("No active reminders.")

        elif args.action == "advice":
            print(await assistant.advice.get_random())

        elif args.action == "set-name":
            await assistant.preferences.set("name", args.name)
            print(f"Name set to {args.name}.")

        return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(dispatch(args))
    except CortexError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
