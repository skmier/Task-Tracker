# Task Tracker

A small, dependency-free task tracker for the command line. Tasks are stored in a
single local JSON file. Requires **Python 3.11+**; the runtime has no third-party
dependencies.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # installs pytest, ruff, mypy (needs network access)
```

If you already have `pytest`, `ruff` and `mypy` available, you can skip the install:
the app itself runs straight from the project folder.

## Run

Everything runs with `python -m task_tracker <command>` from the project root
(after `pip install -e .` you can also use the `task-tracker` command).

```bash
python -m task_tracker add "Write report" -d "Q4 numbers" -p high --due 2026-12-01
python -m task_tracker add "Water plants"                  # priority defaults to medium
python -m task_tracker list
python -m task_tracker list --status todo --priority high  # filters combine
python -m task_tracker show 1                              # all fields, incl. description
python -m task_tracker status 1 in_progress                # todo | in_progress | done
python -m task_tracker done 1                              # shortcut for status done
python -m task_tracker delete 2
```

| Command | Purpose |
| --- | --- |
| `add TITLE [-d TEXT] [-p low\|medium\|high] [--due YYYY-MM-DD]` | Create a task |
| `list [--status S] [--priority P]` | List tasks, optionally filtered |
| `show ID` | Show every field of one task |
| `status ID {todo,in_progress,done}` | Change status |
| `done ID` | Mark completed |
| `delete ID` | Delete a task |

**Exit codes:** `0` success, `1` handled error (message on stderr), `2` bad command-line usage.

### Where data lives

By default in `./data/tasks.json` (relative to where you run the command; the folder is
created on first write and is git-ignored). Options available before the command name:

- `--data-dir DIR` (or env var `TASK_TRACKER_DATA_DIR`): the data directory.
- `--file NAME.json`: a different file *inside* that directory (a separate task list).

```bash
python -m task_tracker --data-dir ~/my-tasks --file work.json list
```

## Test, lint, type-check

```bash
python -m pytest             # unit + integration tests
ruff check .                 # lint
ruff format --check .        # formatting (drop --check to apply)
mypy                         # strict type-checking (config in pyproject.toml)
```

Everything in one go:

```bash
python -m pytest && ruff check . && ruff format --check . && mypy
```

Tests use pytest's `tmp_path`, so they never touch your real data folder.

## Project layout

```
task_tracker/
  errors.py     exception types
  models.py     Task dataclass, enums, validation and (de)serialization
  storage.py    repository protocol, JSON-file repository, safe path handling
  service.py    business logic (create / list / status / delete)
  cli.py        argparse commands and output formatting
  __main__.py   enables `python -m task_tracker`
tests/          pytest suite (models, storage, service, CLI)
```

Dependencies point one way: `cli → service → storage → models → errors`. The service only
depends on the small `TaskRepository` protocol, so it is tested against an in-memory
repository as well as the real JSON one.

## Data-handling behaviour

- **Missing, empty or whitespace-only file** is treated as an empty task list.
- **Malformed JSON, wrong structure, invalid records, duplicate ids** raise a clear error
  and the file is **left untouched**. Corrupt data is never silently overwritten.
- **Writes are atomic**: a temp file in the same directory is fsynced, then renamed over
  the data file, so a crash cannot leave a half-written file.
- Ids are never reused after deletion (the next id is stored in the file).

## Security notes

- No secrets, tokens or personal data are used or included anywhere in the project.
- `--file` must be a plain `*.json` name (no `/`, `\`, `..`, or NUL). The fully resolved
  path (symlinks followed) must be directly inside the resolved data directory, so a
  symlink inside the data folder cannot redirect reads or writes elsewhere.
- `--data-dir` is the one place you choose where data lives; it is the trusted root that
  all file operations are confined to.
- Titles reject control characters and descriptions reject all except newline and tab,
  so stored text cannot inject terminal escape sequences when printed.
- Title and description lengths are capped (200 / 2000 characters).
