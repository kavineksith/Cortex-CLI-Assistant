# Cortex CLI Assistant

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A dependency-free, **async**, **parallel**, CLI personal assistant for
managing tasks, reminders, and daily advice — rewritten from a
voice-based prototype into a robust, scriptable command-line tool
with a proper accountability trail.

---

## 1. The problem this solves

The original prototype this project grew out of was a single 900-line
script that mixed speech I/O, business logic, and storage together. It
had several practical issues:

- **Blocking I/O everywhere.** Every file read/write and every voice
  interaction blocked the whole program, so nothing could happen
  concurrently (e.g. a reminder could never fire while the assistant
  was waiting on input).
- **No real error taxonomy.** Failures were caught with bare
  `except Exception` blocks and mostly just logged, making it hard to
  tell *what* failed and *why* after the fact.
- **Unbounded memory growth.** Every loaded JSON file stayed cached
  forever with no eviction strategy.
- **Hard external dependencies.** `SpeechRecognition`, `pyttsx3`,
  `gTTS`, and a working microphone were required just to try the
  assistant, which is a poor fit for servers, containers, or CI.
- **No audit trail.** There was no reliable way to reconstruct what a
  session actually did.

**Cortex CLI Assistant** solves this by:

| Problem | Solution |
|---|---|
| Blocking I/O | `asyncio` throughout; file I/O offloaded via `asyncio.to_thread`; reminders run as a background `asyncio.Task` in parallel with the input loop |
| Unclear failures | An OOP custom exception hierarchy (`CortexError` and subclasses) with stable error codes |
| Unbounded memory | A bounded LRU cache (`BoundedCache`) and `__slots__`-based models cap memory use |
| Hard dependencies | Zero third-party runtime dependencies — pure standard library, keyboard/text only, no microphone required |
| No accountability | A structured, rotating **audit log** (`logs/audit.log`) records every command and its outcome as JSON, alongside a human-readable operational log (`logs/cortex.log`) |
| Slow bulk computation | CPU-bound task-urgency scoring runs in parallel across processes via `ProcessPoolExecutor` |

---

## 2. How it works — architecture

```
cortex_cli/
├── main.py                 # CLI entry point (argparse + asyncio.run)
├── cortex/
│   ├── __init__.py         # Public package API
│   ├── core.py             # Assistant orchestrator, async REPL loop
│   ├── exceptions.py       # OOP custom exception hierarchy
│   ├── logger.py           # Rotating operational + JSON audit logging
│   ├── managers.py         # TaskManager, ReminderManager, AdviceManager
│   ├── models.py           # Task / Reminder value objects (__slots__, dunders)
│   ├── nlp.py               # Lightweight regex command parser
│   ├── preferences.py      # User preference storage
│   └── storage.py          # Async, cached, atomic JSON storage layer
├── data/                   # Default/example data files
├── logs/                   # Rotating log output (created at runtime)
├── scripts/
│   ├── install.sh          # Bash setup script (venv + deps)
│   └── run.sh              # Bash launcher wrapping main.py
├── requirements.txt        # Intentionally empty — stdlib only
├── LICENSE
└── README.md
```

### Concepts demonstrated

- **Async Python**: `async def` methods across `StorageManager`,
  `TaskManager`, `ReminderManager`, `Assistant`; the REPL and the
  reminder checker run concurrently via `asyncio.create_task`.
- **Generators / async generators**: `TaskManager.iter_tasks()` and
  `ReminderManager.iter_active()` `yield` items lazily instead of
  materializing full lists.
- **Dunder methods**: `__repr__`, `__str__`, `__eq__`, `__hash__`,
  `__lt__`, `__iter__`, `__next__`, `__len__`, `__contains__`,
  `__getitem__`/`__setitem__`, `__aenter__`/`__aexit__`, `__del__`.
- **OOP custom exceptions**: a `CortexError` base class with typed
  subclasses (`StorageError`, `ValidationError`, `TaskNotFoundError`,
  `ReminderError`, `CommandParseError`, `ConcurrencyError`), each
  carrying a numeric code for log correlation.
- **Parallelism**: `ProcessPoolExecutor` for CPU-bound task scoring
  (`score-tasks`), running alongside `asyncio` for I/O-bound
  concurrency (reminder checker + REPL).
- **Memory management**: `__slots__` on all models, a bounded LRU
  cache for loaded JSON files, log rotation to cap disk usage.
- **Accountability logging**: every command execution, storage write,
  and reminder firing is recorded as a structured JSON line in
  `logs/audit.log`, in addition to human-readable operational logs in
  `logs/cortex.log`.

---

## 3. Installation

### Prerequisites

- Python 3.10 or higher
- Bash (for the helper scripts; optional — you can always call
  `python3 main.py` directly)

### Setup

```bash
git clone <this-repo-url> cortex_cli   # or unzip the release archive
cd cortex_cli
chmod +x scripts/*.sh
./scripts/install.sh
```

`scripts/install.sh` creates a `.venv` virtual environment, verifies
your Python version, and installs `requirements.txt` (which is empty
by design — no third-party runtime packages are required).

---

## 4. Usage

### Interactive mode

```bash
./scripts/run.sh run
# or directly:
python3 main.py run
```

Inside the interactive prompt (`cortex>`), try:

```
hello
what's the time
what's the date
advice
help
exit
```

While the interactive loop runs, a **background task** independently
checks for due reminders every 30 seconds (configurable) and prints
them as soon as they fire — this happens in parallel with whatever
you're typing.

### Structured CLI commands

```bash
# Tasks
python3 main.py add-task "Buy groceries" --priority high --due 2026-07-04T18:00:00
python3 main.py list-tasks
python3 main.py list-tasks --keyword groceries
python3 main.py update-task 1 --status completed
python3 main.py delete-task 1
python3 main.py score-tasks          # parallel, multi-process urgency scoring

# Reminders
python3 main.py add-reminder "Call mom" 18:30
python3 main.py list-reminders

# Advice & preferences
python3 main.py advice
python3 main.py set-name "Alex"

# Custom data directory (useful for testing)
python3 main.py --data-dir ./my_data add-task "Test task"
```

Run `python3 main.py --help` or `python3 main.py <command> --help` for
full argument details.

### Where data lives

By default, all JSON data (`tasks.json`, `reminders.json`,
`user_preferences.json`) is stored under `~/.cortex_assistant/`.
Override this with `--data-dir /path/to/dir`.

---

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ERROR: Python 3.10+ is required` | Old Python on `PATH` | Install Python 3.10+, or point `python3` to a newer interpreter |
| `Error: Task ID N not found.` | You referenced an id that was deleted or never created | Run `list-tasks` to see current ids |
| `Error: Invalid time format, expected HH:MM.` | Reminder time wasn't 24-hour `HH:MM` | Use e.g. `09:05`, `18:30` |
| Nothing happens when a reminder should fire | The reminder checker only runs during `run` mode (it's a background task tied to that session) | Keep `python3 main.py run` active, or re-run `list-reminders` to confirm it's still `active` |
| `PermissionError` / can't write data | Data directory isn't writable | Pass `--data-dir` pointing at a writable location |
| Corrupted `tasks.json` after a crash | Should not happen — writes are atomic (`os.replace` after a full temp-file write) | If it does, check `logs/cortex.log` for the `StorageError` and inspect the `.tmp` file left behind |
| Want to see exactly what happened in a session | Structured JSON events are in `logs/audit.log`; human-readable narrative is in `logs/cortex.log` | `tail -f logs/audit.log` while running |

---

## 6. How to run tests / sanity-check the build

```bash
# Quick smoke test with an isolated data directory
python3 main.py --data-dir /tmp/cortex_demo add-task "Demo task" --priority high
python3 main.py --data-dir /tmp/cortex_demo list-tasks
python3 main.py --data-dir /tmp/cortex_demo score-tasks
```

---

## 7. Disclaimer

This project is an educational / portfolio piece intended to
demonstrate modern Python patterns (async I/O, generators, custom
exceptions, parallelism, structured logging). It is **not** a
production-hardened system:

- Data is stored as plain, unencrypted JSON on the local filesystem.
- There is no authentication, multi-user isolation, or network
  exposure protection built in — do not expose this tool over a
  network without adding your own security layer.
- The developer(s) make no guarantees about reliability, data
  durability, or fitness for any particular purpose. Use at your own
  risk, and keep backups of anything important.

---

## License

Released under the [MIT License](LICENSE).
