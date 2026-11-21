"""Data model and validation rules for tasks.

Everything here is pure: no file access, no clock, no printing.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Self, TypeVar

from task_tracker.errors import ValidationError

MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000

_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Status(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


E = TypeVar("E", bound=StrEnum)


def _parse_enum(enum_cls: type[E], value: object, label: str) -> E:
    try:
        return enum_cls(str(value).strip().lower())
    except ValueError:
        allowed = ", ".join(member.value for member in enum_cls)
        raise ValidationError(f"Invalid {label} {value!r}; expected one of: {allowed}") from None


def parse_priority(value: str | Priority) -> Priority:
    return _parse_enum(Priority, value, "priority")


def parse_status(value: str | Status) -> Status:
    return _parse_enum(Status, value, "status")


def parse_due_date(value: str | date | None) -> date | None:
    """Accept ``None``/empty (no due date), a ``date``, or a strict ``YYYY-MM-DD`` string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        raise ValidationError("Due date must be a date (YYYY-MM-DD), not a datetime")
    if isinstance(value, date):
        return value
    text = value.strip()
    if not text:
        return None
    if not _DATE_PATTERN.fullmatch(text):
        raise ValidationError(f"Invalid due date {value!r}; use YYYY-MM-DD")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValidationError(f"Invalid due date {value!r}; not a real calendar date") from None


def _has_control_chars(text: str, allowed: str = "") -> bool:
    return any(unicodedata.category(ch) == "Cc" and ch not in allowed for ch in text)


def validate_title(title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        raise ValidationError("Title must not be empty")
    if len(cleaned) > MAX_TITLE_LENGTH:
        raise ValidationError(f"Title must be at most {MAX_TITLE_LENGTH} characters")
    if _has_control_chars(cleaned):
        raise ValidationError("Title must not contain control characters")
    return cleaned


def validate_description(description: str) -> str:
    cleaned = description.replace("\r\n", "\n").strip()
    if len(cleaned) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError(f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters")
    if _has_control_chars(cleaned, allowed="\n\t"):
        raise ValidationError("Description must not contain control characters")
    return cleaned


def _parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError(f"Task field {label!r} must be an ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"Task field {label!r} is not a valid timestamp: {value!r}") from None
    if parsed.tzinfo is None:
        raise ValidationError(f"Task field {label!r} must include a UTC offset: {value!r}")
    return parsed


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    description: str
    priority: Priority
    status: Status
    created_at: datetime
    due_date: date | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: object) -> Self:
        """Build a task from a stored record, validating every field."""
        if not isinstance(data, dict):
            raise ValidationError("Task record must be a JSON object")
        try:
            raw_id = data["id"]
            raw_title = data["title"]
            raw_description = data["description"]
            raw_priority = data["priority"]
            raw_status = data["status"]
            raw_created = data["created_at"]
        except KeyError as exc:
            raise ValidationError(f"Task record is missing field {exc.args[0]!r}") from None

        if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id < 1:
            raise ValidationError(f"Invalid task id {raw_id!r}; expected a positive integer")
        for label, raw in (
            ("title", raw_title),
            ("description", raw_description),
            ("priority", raw_priority),
            ("status", raw_status),
        ):
            if not isinstance(raw, str):
                raise ValidationError(f"Task field {label!r} must be a string")

        raw_due = data.get("due_date")
        if raw_due is not None and not isinstance(raw_due, str):
            raise ValidationError("Task field 'due_date' must be a string or null")
        raw_completed = data.get("completed_at")

        return cls(
            id=raw_id,
            title=validate_title(raw_title),
            description=validate_description(raw_description),
            priority=parse_priority(raw_priority),
            status=parse_status(raw_status),
            created_at=_parse_timestamp(raw_created, "created_at"),
            due_date=parse_due_date(raw_due),
            completed_at=(
                None if raw_completed is None else _parse_timestamp(raw_completed, "completed_at")
            ),
        )


@dataclass
class Snapshot:
    """Everything the repository persists: the tasks and the next id to hand out."""

    tasks: list[Task] = field(default_factory=list)
    next_id: int = 1
