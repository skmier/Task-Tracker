import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from task_tracker.errors import StorageError
from task_tracker.models import Priority, Snapshot, Status, Task
from task_tracker.storage import (
    InMemoryTaskRepository,
    JsonTaskRepository,
    resolve_data_file,
)


def make_task(task_id: int = 1, title: str = "Task") -> Task:
    return Task(
        id=task_id,
        title=title,
        description="",
        priority=Priority.MEDIUM,
        status=Status.TODO,
        created_at=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
    )


def test_missing_file_loads_as_empty(tmp_path: Path) -> None:
    snapshot = JsonTaskRepository(tmp_path).load()
    assert snapshot.tasks == []
    assert snapshot.next_id == 1


@pytest.mark.parametrize("content", ["", "   \n\t "])
def test_empty_or_blank_file_loads_as_empty(tmp_path: Path, content: str) -> None:
    (tmp_path / "tasks.json").write_text(content, encoding="utf-8")
    snapshot = JsonTaskRepository(tmp_path).load()
    assert snapshot.tasks == []
    assert snapshot.next_id == 1


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    repo = JsonTaskRepository(tmp_path)
    repo.save(Snapshot(tasks=[make_task(1, "One"), make_task(2, "Two")], next_id=5))
    loaded = JsonTaskRepository(tmp_path).load()
    assert [t.title for t in loaded.tasks] == ["One", "Two"]
    assert loaded.next_id == 5


def test_save_creates_missing_directories(tmp_path: Path) -> None:
    repo = JsonTaskRepository(tmp_path / "a" / "b")
    repo.save(Snapshot(tasks=[make_task()], next_id=2))
    assert repo.path.is_file()
    assert repo.path.parent == (tmp_path / "a" / "b").resolve()


def test_save_leaves_no_temporary_files_behind(tmp_path: Path) -> None:
    repo = JsonTaskRepository(tmp_path)
    repo.save(Snapshot(tasks=[make_task()], next_id=2))
    repo.save(Snapshot(tasks=[make_task(), make_task(2)], next_id=3))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["tasks.json"]


def test_saved_file_is_valid_json_with_expected_shape(tmp_path: Path) -> None:
    repo = JsonTaskRepository(tmp_path)
    repo.save(Snapshot(tasks=[make_task()], next_id=2))
    payload = json.loads(repo.path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["next_id"] == 2
    assert payload["tasks"][0]["title"] == "Task"


def test_malformed_json_raises_and_leaves_file_untouched(tmp_path: Path) -> None:
    path = tmp_path / "tasks.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StorageError, match="not valid JSON"):
        JsonTaskRepository(tmp_path).load()
    assert path.read_text(encoding="utf-8") == "{not json"


def test_non_utf8_file_raises_storage_error(tmp_path: Path) -> None:
    (tmp_path / "tasks.json").write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(StorageError, match="Cannot read"):
        JsonTaskRepository(tmp_path).load()


def test_directory_in_place_of_file_raises_storage_error(tmp_path: Path) -> None:
    (tmp_path / "tasks.json").mkdir()
    with pytest.raises(StorageError, match="Cannot read"):
        JsonTaskRepository(tmp_path).load()


@pytest.mark.parametrize(
    "payload",
    [
        "[]",
        '"just a string"',
        "{}",
        '{"tasks": "nope"}',
        '{"version": 99, "tasks": []}',
        '{"tasks": [1]}',
        '{"tasks": [{"id": 1}]}',
        '{"tasks": [], "next_id": "7"}',
        '{"tasks": [], "next_id": true}',
    ],
)
def test_structurally_invalid_payloads_raise_storage_error(tmp_path: Path, payload: str) -> None:
    (tmp_path / "tasks.json").write_text(payload, encoding="utf-8")
    with pytest.raises(StorageError):
        JsonTaskRepository(tmp_path).load()


def test_duplicate_ids_raise_storage_error(tmp_path: Path) -> None:
    record = make_task(1).to_dict()
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [record, record]}), encoding="utf-8")
    with pytest.raises(StorageError, match="duplicate"):
        JsonTaskRepository(tmp_path).load()


def test_next_id_must_exceed_existing_ids(tmp_path: Path) -> None:
    payload = {"tasks": [make_task(4).to_dict()], "next_id": 4}
    (tmp_path / "tasks.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StorageError, match="next_id"):
        JsonTaskRepository(tmp_path).load()


def test_missing_next_id_is_derived_from_highest_id(tmp_path: Path) -> None:
    payload = {"tasks": [make_task(3).to_dict()]}
    (tmp_path / "tasks.json").write_text(json.dumps(payload), encoding="utf-8")
    assert JsonTaskRepository(tmp_path).load().next_id == 4


def test_save_failure_is_reported_as_storage_error(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory", encoding="utf-8")
    repo = JsonTaskRepository(blocker)
    with pytest.raises(StorageError, match="Cannot write"):
        repo.save(Snapshot(tasks=[make_task()], next_id=2))


@pytest.mark.parametrize(
    "filename",
    [
        "../escape.json",
        "sub/tasks.json",
        "/etc/passwd.json",
        "..",
        ".",
        "",
        "tasks.txt",
        "back\\slash.json",
        "nul\0byte.json",
    ],
)
def test_unsafe_file_names_are_rejected(tmp_path: Path, filename: str) -> None:
    with pytest.raises(StorageError, match="Invalid data file name"):
        resolve_data_file(tmp_path, filename)
    with pytest.raises(StorageError):
        JsonTaskRepository(tmp_path, filename)


def test_resolved_path_stays_inside_data_dir(tmp_path: Path) -> None:
    repo = JsonTaskRepository(tmp_path, "mine.json")
    assert repo.path == tmp_path.resolve() / "mine.json"


def test_symlink_pointing_outside_data_dir_is_rejected(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    try:
        (data_dir / "tasks.json").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    with pytest.raises(StorageError, match="outside the data directory"):
        JsonTaskRepository(data_dir)
    assert outside.read_text(encoding="utf-8") == "{}"


def test_in_memory_repository_isolates_snapshots() -> None:
    repo = InMemoryTaskRepository()
    snapshot = repo.load()
    snapshot.tasks.append(make_task())
    assert repo.load().tasks == []  # not saved yet
    repo.save(snapshot)
    snapshot.tasks.clear()
    assert len(repo.load().tasks) == 1  # later local mutation does not leak in
