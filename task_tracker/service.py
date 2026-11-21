"""Business logic. Knows nothing about files or the command line."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime

from task_tracker.errors import TaskNotFoundError
from task_tracker.models import (
    Priority,
    Snapshot,
    Status,
    Task,
    parse_due_date,
    parse_priority,
    parse_status,
    validate_description,
    validate_title,
)
from task_tracker.storage import TaskRepository

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskService:
    def __init__(self, repository: TaskRepository, clock: Clock = _utc_now) -> None:
        self._repository = repository
        self._clock = clock

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: str | Priority = Priority.MEDIUM,
        due_date: str | date | None = None,
    ) -> Task:
        # Validate everything first so bad input never touches storage.
        clean_title = validate_title(title)
        clean_description = validate_description(description)
        clean_priority = parse_priority(priority)
        clean_due = parse_due_date(due_date)

        snapshot = self._repository.load()
        task = Task(
            id=snapshot.next_id,
            title=clean_title,
            description=clean_description,
            priority=clean_priority,
            status=Status.TODO,
            created_at=self._clock(),
            due_date=clean_due,
        )
        snapshot.tasks.append(task)
        snapshot.next_id += 1
        self._repository.save(snapshot)
        return task

    def list_tasks(
        self,
        status: str | Status | None = None,
        priority: str | Priority | None = None,
    ) -> list[Task]:
        wanted_status = parse_status(status) if status is not None else None
        wanted_priority = parse_priority(priority) if priority is not None else None
        tasks = self._repository.load().tasks
        return sorted(
            (
                task
                for task in tasks
                if (wanted_status is None or task.status is wanted_status)
                and (wanted_priority is None or task.priority is wanted_priority)
            ),
            key=lambda task: task.id,
        )

    def get_task(self, task_id: int) -> Task:
        snapshot = self._repository.load()
        return snapshot.tasks[self._index_of(snapshot, task_id)]

    def set_status(self, task_id: int, status: str | Status) -> Task:
        new_status = parse_status(status)
        snapshot = self._repository.load()
        index = self._index_of(snapshot, task_id)
        current = snapshot.tasks[index]
        # Keep the original completion time if the task is already done.
        completed_at = (
            (current.completed_at or self._clock()) if new_status is Status.DONE else None
        )
        updated = replace(current, status=new_status, completed_at=completed_at)
        snapshot.tasks[index] = updated
        self._repository.save(snapshot)
        return updated

    def complete_task(self, task_id: int) -> Task:
        return self.set_status(task_id, Status.DONE)

    def delete_task(self, task_id: int) -> Task:
        snapshot = self._repository.load()
        index = self._index_of(snapshot, task_id)
        removed = snapshot.tasks.pop(index)
        self._repository.save(snapshot)
        return removed

    @staticmethod
    def _index_of(snapshot: Snapshot, task_id: int) -> int:
        for index, task in enumerate(snapshot.tasks):
            if task.id == task_id:
                return index
        raise TaskNotFoundError(task_id)
