AGENTS.md

Instructions for AI coding agents (and humans) working in this repository. Keep this file short and accurate. If a command here stops working, fix the file in the same change.

Purpose

Task Tracker is a small command-line task manager. Tasks are stored in one local JSON file. It is a learning project: no network, no secrets, no real personal data.

Architecture

Python 3.11+, standard library only at runtime (dependencies = []).

task_tracker/
  errors.py    exception types
  models.py    Task dataclass, Priority/Status enums, validation, (de)serialization
  storage.py   TaskRepository protocol, JsonTaskRepository (atomic writes), InMemoryTaskRepository
  service.py   business logic (create, list, set status, delete)
  cli.py       argparse commands and output formatting
  __main__.py  enables `python -m task_tracker`
tests/         pytest suite: test_models, test_storage, test_service, test_cli

Dependency direction is one way: cli -> service -> storage -> models -> errors. Do not import "upwards" (for example, models.py must not import from service.py). models.py is pure: no file access, no clock, no printing.

Setup
bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # pytest, ruff, mypy; needs network access

The app itself needs no installation: run it from the project root.

Safe commands (agents may run these without asking)
bash
python -m pytest -q              # tests (expected: all pass; 122 at commit 3c964cf)
ruff check .                     # lint
ruff format --check .            # formatting check (does not change files)
mypy                             # strict type check
python -m task_tracker --help    # CLI help

Run the full gate before every commit:

bash
python -m pytest -q && ruff check . && ruff format --check . && mypy

When trying the CLI by hand, ALWAYS point it at a temporary folder so real data is not touched:

bash
python -m task_tracker --data-dir "$(mktemp -d)" add "Example" -p high
Commands that need human approval first
ruff format . (rewrites files; allowed only on files you are already changing).
pip install ... or any change to pyproject.toml dependencies.
Creating, renaming, or deleting files outside task_tracker/, tests/, and the docs listed below.
git commit / git push (commit only when asked; never push to main directly).
Forbidden actions
No secrets: never create or commit .env files, tokens, keys, or real personal data.
No production deployment, publishing to PyPI, or changing any CI/release settings.
No destructive commands: rm -rf, git reset --hard, git push --force, git clean -fdx, deleting data/.
No unreviewed dependency changes: do not add, remove, or bump packages on your own.
Do not read or write outside the project folder, except mktemp -d scratch folders.
Do not edit or delete tests to make them pass. If a test is wrong, explain why and ask.
Do not invent results: report test and build output exactly as it appeared, and say which checks you did not run.
Coding conventions
Line length 100; formatting and import order are enforced by ruff.
Full type annotations; mypy runs in strict mode on task_tracker and tests.
Raise errors from task_tracker/errors.py (ValidationError, TaskNotFoundError, StorageError). The CLI turns them into error: ... on stderr with exit code 1; argparse usage errors exit with 2.
Validate input before touching storage. Never silently overwrite a corrupt data file.
Keep changes small and focused: one concern per change.
Test expectations
Every behavior change comes with a test in the matching tests/test_*.py file.
Tests use pytest tmp_path or InMemoryTaskRepository; they must never touch a real data/ folder.
Before saying a task is done, run the full gate above and quote the real result.
Behavior that must not break (acceptance criteria)
add gives the next id, status todo, default priority medium; ids are never reused.
list is sorted by id; --status and --priority filters combine.
completed_at is set only for done, and the original time is kept if already done.
Invalid input gives error: ... on stderr and exit code 1; usage errors give exit code 2.
A corrupt data file is never overwritten; writes are atomic; --file cannot leave the data directory.
Known limitations (do not "fix" silently; discuss first)
No file locking: parallel commands can lose updates (observed: 20 parallel add kept 5 tasks).
.gitignore does not yet ignore data/ or Python caches.
No CI and no coverage measurement yet.
Review gates
A human reviews every diff before merge. Agent output is a proposal, not an approved change.
Summarize each change with: what changed, why, commands run, and their actual results.