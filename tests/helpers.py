"""Small test utilities shared by several test modules."""

from datetime import UTC, datetime, timedelta


class FakeClock:
    """A controllable replacement for the service's clock."""

    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 1, 15, 9, 30, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, minutes: int = 0) -> None:
        self.now += timedelta(minutes=minutes)
