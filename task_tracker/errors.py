"""Exception types shared by all modules."""


class TaskTrackerError(Exception):
    """Base class for every error this application raises on purpose."""


class ValidationError(TaskTrackerError):
    """User-supplied (or stored) data does not satisfy the model's rules."""


class TaskNotFoundError(TaskTrackerError):
    """No task exists with the requested id."""

    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task {task_id} not found")
        self.task_id = task_id


class StorageError(TaskTrackerError):
    """The data file could not be read, parsed, written, or located safely."""
