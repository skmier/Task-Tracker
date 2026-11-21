from pathlib import Path

import pytest

from task_tracker.service import TaskService
from task_tracker.storage import JsonTaskRepository
from tests.helpers import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def repo(tmp_path: Path) -> JsonTaskRepository:
    return JsonTaskRepository(tmp_path)


@pytest.fixture
def service(repo: JsonTaskRepository, clock: FakeClock) -> TaskService:
    return TaskService(repo, clock=clock)
