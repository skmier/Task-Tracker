import json
from datetime import UTC, date, datetime
from typing import Any

import pytest

from task_tracker.errors import ValidationError
from task_tracker.models import (
    MAX_DESCRIPTION_LENGTH,
    MAX_TITLE_LENGTH,
    Priority,
    Status,
    Task,
    parse_due_date,
    parse_priority,
    parse_status,
    validate_description,
    validate_title,
)


def _record(**overrides: object) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": 1,
        "title": "Write tests",
        "description": "Cover the core flows",
        "priority": "high",
        "status": "todo",
        "due_date": "2026-12-31",
        "created_at": "2026-01-15T09:30:00+00:00",
        "completed_at": None,
    }
    record.update(overrides)
    return record


def test_parse_priority_accepts_case_and_whitespace() -> None:
    assert parse_priority(" HIGH ") is Priority.HIGH
    assert parse_priority(Priority.LOW) is Priority.LOW


@pytest.mark.parametrize("bad", ["urgent", "", "1"])
def test_parse_priority_rejects_unknown_values(bad: str) -> None:
    with pytest.raises(ValidationError, match="priority"):
        parse_priority(bad)


def test_parse_status_accepts_all_statuses() -> None:
    assert parse_status("todo") is Status.TODO
    assert parse_status("In_Progress") is Status.IN_PROGRESS
    assert parse_status(Status.DONE) is Status.DONE


def test_parse_status_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError, match="status"):
        parse_status("finished")


def test_parse_due_date_accepts_none_blank_date_and_iso_string() -> None:
    assert parse_due_date(None) is None
    assert parse_due_date("  ") is None
    assert parse_due_date(date(2026, 5, 1)) == date(2026, 5, 1)
    assert parse_due_date("2026-12-31") == date(2026, 12, 31)


@pytest.mark.parametrize("bad", ["2026-13-01", "12/31/2026", "2026-1-5", "tomorrow", "2026-02-30"])
def test_parse_due_date_rejects_bad_strings(bad: str) -> None:
    with pytest.raises(ValidationError, match="due date"):
        parse_due_date(bad)


def test_parse_due_date_rejects_datetime() -> None:
    with pytest.raises(ValidationError, match="not a datetime"):
        parse_due_date(datetime(2026, 1, 1, tzinfo=UTC))


def test_validate_title_strips_and_enforces_limits() -> None:
    assert validate_title("  hello  ") == "hello"
    assert validate_title("x" * MAX_TITLE_LENGTH) == "x" * MAX_TITLE_LENGTH
    with pytest.raises(ValidationError, match="empty"):
        validate_title("   ")
    with pytest.raises(ValidationError, match="at most"):
        validate_title("x" * (MAX_TITLE_LENGTH + 1))


def test_validate_title_rejects_control_characters() -> None:
    with pytest.raises(ValidationError, match="control"):
        validate_title("bad\x1b[31mtitle")
    with pytest.raises(ValidationError, match="control"):
        validate_title("line1\nline2")


def test_validate_description_allows_newlines_and_normalizes_crlf() -> None:
    assert validate_description("a\r\nb\tc") == "a\nb\tc"
    assert validate_description("") == ""


def test_validate_description_rejects_limits_and_control_characters() -> None:
    with pytest.raises(ValidationError, match="at most"):
        validate_description("x" * (MAX_DESCRIPTION_LENGTH + 1))
    with pytest.raises(ValidationError, match="control"):
        validate_description("bell\x07")


def test_task_round_trips_through_dict_and_json() -> None:
    task = Task.from_dict(_record(status="done", completed_at="2026-01-16T10:00:00+00:00"))
    assert task.due_date == date(2026, 12, 31)
    assert task.status is Status.DONE
    restored = Task.from_dict(json.loads(json.dumps(task.to_dict())))
    assert restored == task


def test_task_from_dict_allows_missing_optional_fields() -> None:
    record = _record()
    del record["due_date"]
    del record["completed_at"]
    task = Task.from_dict(record)
    assert task.due_date is None
    assert task.completed_at is None


@pytest.mark.parametrize("bad", ["text", [], None, 5])
def test_task_from_dict_rejects_non_objects(bad: object) -> None:
    with pytest.raises(ValidationError, match="JSON object"):
        Task.from_dict(bad)


@pytest.mark.parametrize(
    "field", ["id", "title", "description", "priority", "status", "created_at"]
)
def test_task_from_dict_rejects_missing_required_field(field: str) -> None:
    record = _record()
    del record[field]
    with pytest.raises(ValidationError, match=field):
        Task.from_dict(record)


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": 0},
        {"id": -3},
        {"id": True},
        {"id": "1"},
        {"title": 5},
        {"title": "   "},
        {"description": None},
        {"priority": "urgent"},
        {"status": "finished"},
        {"due_date": 20261231},
        {"due_date": "not-a-date"},
        {"created_at": "yesterday"},
        {"created_at": "2026-01-15T09:30:00"},  # naive timestamp
        {"created_at": 123},
        {"completed_at": "nope"},
    ],
)
def test_task_from_dict_rejects_invalid_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Task.from_dict(_record(**overrides))
