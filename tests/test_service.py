from datetime import date
from pathlib import Path

import pytest

from task_tracker.errors import TaskNotFoundError, ValidationError
from task_tracker.models import Priority, Status
from task_tracker.service import TaskService
from task_tracker.storage import InMemoryTaskRepository, JsonTaskRepository
from tests.helpers import FakeClock


def test_create_task_applies_defaults(service: TaskService, clock: FakeClock) -> None:
    task = service.create_task("  Write report  ")
    assert task.id == 1
    assert task.title == "Write report"
    assert task.description == ""
    assert task.priority is Priority.MEDIUM
    assert task.status is Status.TODO
    assert task.due_date is None
    assert task.created_at == clock.now
    assert task.completed_at is None


def test_create_task_with_all_fields(service: TaskService) -> None:
    task = service.create_task(
        "Pay rent", description="Landlord", priority="HIGH", due_date="2026-12-01"
    )
    assert task.description == "Landlord"
    assert task.priority is Priority.HIGH
    assert task.due_date == date(2026, 12, 1)


def test_ids_increment_and_are_never_reused(service: TaskService) -> None:
    first = service.create_task("a")
    second = service.create_task("b")
    service.delete_task(second.id)
    third = service.create_task("c")
    assert (first.id, second.id, third.id) == (1, 2, 3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"title": "   "},
        {"title": "x" * 201},
        {"title": "ok", "priority": "urgent"},
        {"title": "ok", "due_date": "soon"},
        {"title": "ok", "description": "bell\x07"},
    ],
)
def test_create_task_rejects_invalid_input_without_saving(kwargs: dict[str, str]) -> None:
    repo = InMemoryTaskRepository()
    service = TaskService(repo)
    with pytest.raises(ValidationError):
        service.create_task(**kwargs)
    assert repo.load().tasks == []
    assert repo.load().next_id == 1


@pytest.fixture
def populated(service: TaskService) -> TaskService:
    service.create_task("low todo", priority="low")  # 1
    service.create_task("high todo", priority="high")  # 2
    service.create_task("high done", priority="high")  # 3
    service.create_task("medium wip", priority="medium")  # 4
    service.complete_task(3)
    service.set_status(4, "in_progress")
    return service


def _ids(service: TaskService, **filters: str) -> list[int]:
    return [task.id for task in service.list_tasks(**filters)]


def test_list_without_filters_returns_everything_in_id_order(populated: TaskService) -> None:
    assert _ids(populated) == [1, 2, 3, 4]


def test_list_filters_by_status(populated: TaskService) -> None:
    assert _ids(populated, status="todo") == [1, 2]
    assert _ids(populated, status="done") == [3]
    assert _ids(populated, status="in_progress") == [4]


def test_list_filters_by_priority(populated: TaskService) -> None:
    assert _ids(populated, priority="high") == [2, 3]
    assert _ids(populated, priority="low") == [1]


def test_list_filters_combine(populated: TaskService) -> None:
    assert _ids(populated, status="todo", priority="high") == [2]
    assert _ids(populated, status="done", priority="low") == []


def test_list_rejects_invalid_filter_values(populated: TaskService) -> None:
    with pytest.raises(ValidationError):
        populated.list_tasks(status="finished")
    with pytest.raises(ValidationError):
        populated.list_tasks(priority="urgent")


def test_list_on_empty_store_returns_empty_list(service: TaskService) -> None:
    assert service.list_tasks() == []


def test_complete_task_sets_status_and_timestamp(service: TaskService, clock: FakeClock) -> None:
    task = service.create_task("finish me")
    clock.advance(minutes=45)
    done = service.complete_task(task.id)
    assert done.status is Status.DONE
    assert done.completed_at == clock.now
    assert service.get_task(task.id) == done


def test_completing_twice_keeps_original_completion_time(
    service: TaskService, clock: FakeClock
) -> None:
    task = service.create_task("finish me")
    first = service.complete_task(task.id)
    clock.advance(minutes=10)
    second = service.complete_task(task.id)
    assert second.completed_at == first.completed_at


def test_reopening_a_task_clears_completion_time(service: TaskService) -> None:
    task = service.create_task("flip-flop")
    service.complete_task(task.id)
    reopened = service.set_status(task.id, "todo")
    assert reopened.status is Status.TODO
    assert reopened.completed_at is None


def test_set_status_to_in_progress(service: TaskService) -> None:
    task = service.create_task("start me")
    assert service.set_status(task.id, Status.IN_PROGRESS).status is Status.IN_PROGRESS


def test_set_status_rejects_invalid_value_and_changes_nothing(service: TaskService) -> None:
    task = service.create_task("stay put")
    with pytest.raises(ValidationError):
        service.set_status(task.id, "finished")
    assert service.get_task(task.id).status is Status.TODO


def test_delete_removes_only_the_requested_task(service: TaskService) -> None:
    keep = service.create_task("keep")
    drop = service.create_task("drop")
    removed = service.delete_task(drop.id)
    assert removed.id == drop.id
    assert [t.id for t in service.list_tasks()] == [keep.id]


def test_unknown_ids_raise_not_found(service: TaskService) -> None:
    service.create_task("only one")
    with pytest.raises(TaskNotFoundError, match="99"):
        service.get_task(99)
    with pytest.raises(TaskNotFoundError):
        service.complete_task(99)
    with pytest.raises(TaskNotFoundError):
        service.set_status(99, "todo")
    with pytest.raises(TaskNotFoundError):
        service.delete_task(99)
    assert len(service.list_tasks()) == 1


def test_deleting_twice_raises_not_found(service: TaskService) -> None:
    task = service.create_task("once")
    service.delete_task(task.id)
    with pytest.raises(TaskNotFoundError):
        service.delete_task(task.id)


def test_state_survives_reload_from_disk(tmp_path: Path, clock: FakeClock) -> None:
    first = TaskService(JsonTaskRepository(tmp_path), clock=clock)
    created = first.create_task("Persist me", priority="low", due_date="2026-03-01")
    first.create_task("Delete me")
    first.complete_task(created.id)
    first.delete_task(2)

    second = TaskService(JsonTaskRepository(tmp_path))
    reloaded = second.get_task(created.id)
    assert reloaded == first.get_task(created.id)
    assert reloaded.status is Status.DONE
    assert reloaded.completed_at == clock.now
    assert reloaded.due_date == date(2026, 3, 1)
    assert [t.id for t in second.list_tasks()] == [1]
    # The id counter is persisted too, so ids are still not reused after a reload.
    assert second.create_task("next").id == 3
