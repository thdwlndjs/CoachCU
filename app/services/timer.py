from __future__ import annotations

from datetime import datetime

from app.models import SessionState, WorkSession


class SessionTimer:
    def __init__(self, planned_minutes: int, started_at: datetime | None = None) -> None:
        if planned_minutes <= 0:
            raise ValueError("planned_minutes must be positive")
        self.planned_minutes = planned_minutes
        self.started_at = started_at or datetime.now()
        self.state = SessionState.RUNNING

    @property
    def planned_seconds(self) -> int:
        return self.planned_minutes * 60

    def elapsed_seconds(self, now: datetime | None = None) -> int:
        current = now or datetime.now()
        return max(0, int((current - self.started_at).total_seconds()))

    def remaining_seconds(self, now: datetime | None = None) -> int:
        return max(0, self.planned_seconds - self.elapsed_seconds(now))

    def tick(self, now: datetime | None = None) -> SessionState:
        if self.state != SessionState.RUNNING:
            return self.state
        if self.remaining_seconds(now) == 0:
            self.state = SessionState.COMPLETED
        return self.state

    def cancel(self) -> SessionState:
        if self.state == SessionState.RUNNING:
            self.state = SessionState.CANCELLED
        return self.state


def calculate_actual_minutes(session: WorkSession, ended_at: datetime) -> int:
    elapsed = max(0, int((ended_at - session.started_at).total_seconds()))
    return max(1, round(elapsed / 60))
