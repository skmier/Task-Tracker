"""Persistence layer: a JSON-file repository plus an in-memory one for tests."""

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

from task_tracker.errors import StorageError, ValidationError
from task_tracker.models import Snapshot, Task

SCHEMA_VERSION = 1
DEFAULT_FILENAME = "tasks.json"


class TaskRepository(Protocol):
    def load(self) -> Snapshot: ...

    def save(self, snapshot: Snapshot) -> None: ...


class InMemoryTaskRepository:
    """Non-persistent repository; handy for unit-testing the service in isolation."""

    def __init__(self) -> None:
        self._snapshot = Snapshot()

    def load(self) -> Snapshot:
        return Snapshot(tasks=list(self._snapshot.tasks), next_id=self._snapshot.next_id)

    def save(self, snapshot: Snapshot) -> None:
        self._snapshot = Snapshot(tasks=list(snapshot.tasks), next_id=snapshot.next_id)


def resolve_data_file(data_dir: Path, filename: str) -> Path:
    """Return the absolute path of ``filename`` inside ``data_dir``, or raise.

    ``filename`` must be a plain ``*.json`` name: no separators, no ``..``, no NUL.
    The fully resolved path (symlinks followed) must still sit directly in the
    resolved data directory, so a symlink cannot redirect writes elsewhere.
    """
    if (
        not filename
        or filename in {".", ".."}
        or any(ch in filename for ch in ("/", "\\", "\0"))
        or not filename.endswith(".json")
    ):
        raise StorageError(
            f"Invalid data file name {filename!r}: use a plain file name ending in .json"
        )
    root = data_dir.resolve()
    candidate = (root / filename).resolve()
    if candidate.parent != root:
        raise StorageError(f"Data file {filename!r} resolves outside the data directory")
    return candidate


class JsonTaskRepository:
    """Stores all tasks in one JSON file inside a fixed data directory."""

    def __init__(self, data_dir: Path | str, filename: str = DEFAULT_FILENAME) -> None:
        self._path = resolve_data_file(Path(data_dir), filename)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Snapshot:
        """Missing or blank file -> empty snapshot. Corrupt content -> StorageError.

        Corrupt files are never silently replaced, so the user's data is not lost.
        """
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Snapshot()
        except (OSError, UnicodeDecodeError) as exc:
            raise StorageError(f"Cannot read {self._path}: {exc}") from exc
        if not raw.strip():
            return Snapshot()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StorageError(
                f"{self._path} is not valid JSON ({exc}); fix or move the file and retry"
            ) from exc
        return _snapshot_from_payload(payload, self._path)

    def save(self, snapshot: Snapshot) -> None:
        """Write atomically: temp file in the same directory, fsync, then rename."""
        payload = {
            "version": SCHEMA_VERSION,
            "next_id": snapshot.next_id,
            "tasks": [task.to_dict() for task in snapshot.tasks],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        tmp_name: str | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=self._path.parent, prefix=f".{self._path.stem}-", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self._path)
        except OSError as exc:
            if tmp_name is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_name)
            raise StorageError(f"Cannot write {self._path}: {exc}") from exc


def _snapshot_from_payload(payload: object, path: Path) -> Snapshot:
    if not isinstance(payload, dict):
        raise StorageError(f"{path}: top-level JSON value must be an object")
    version = payload.get("version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise StorageError(f"{path}: unsupported schema version {version!r}")
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list):
        raise StorageError(f"{path}: 'tasks' must be a list")

    tasks: list[Task] = []
    seen_ids: set[int] = set()
    for index, record in enumerate(raw_tasks):
        try:
            task = Task.from_dict(record)
        except ValidationError as exc:
            raise StorageError(f"{path}: invalid task at index {index}: {exc}") from exc
        if task.id in seen_ids:
            raise StorageError(f"{path}: duplicate task id {task.id}")
        seen_ids.add(task.id)
        tasks.append(task)

    highest = max(seen_ids, default=0)
    next_id = payload.get("next_id", highest + 1)
    if isinstance(next_id, bool) or not isinstance(next_id, int) or next_id <= highest:
        raise StorageError(f"{path}: 'next_id' must be an integer greater than every task id")
    return Snapshot(tasks=tasks, next_id=next_id)
