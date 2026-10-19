"""Provider-neutral, structured decisions for the work-entry workflow."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from app.models import WorkSession


class DecisionAction(str, Enum):
    RESUME_SESSION = "resume_session"
    ASK_FOR_WORK = "ask_for_work"
    SUGGEST_WORK = "suggest_work"


@dataclass(frozen=True)
class WorkContext:
    trigger: str
    current_time: datetime
    active_session: WorkSession | None
    today_sessions: tuple[WorkSession, ...]

    def as_prompt_state(self) -> dict:
        return {
            "trigger": self.trigger,
            "current_time": self.current_time.isoformat(timespec="minutes"),
            "active_session": self._session_state(self.active_session),
            "today_sessions": [self._session_state(session) for session in self.today_sessions[:10]],
        }

    @staticmethod
    def _session_state(session: WorkSession | None) -> dict | None:
        if session is None:
            return None
        return {
            "intent": session.intent,
            "task_name": session.task_name,
            "planned_minutes": session.planned_minutes,
            "result": session.result,
            "started_at": session.started_at.isoformat(timespec="minutes"),
        }


@dataclass(frozen=True)
class WorkDecision:
    action: DecisionAction
    intent: str | None
    task_name: str | None
    planned_minutes: int | None
    confidence: float
    reason_code: str


class DecisionEngine(Protocol):
    def decide(self, context: WorkContext) -> WorkDecision:
        """Return one validated, advisory workflow decision."""


class RuleBasedDecisionEngine:
    """Offline fail-safe used when an AI provider is unavailable."""

    def decide(self, context: WorkContext) -> WorkDecision:
        if context.active_session is not None:
            return WorkDecision(
                DecisionAction.RESUME_SESSION,
                context.active_session.intent,
                context.active_session.task_name,
                context.active_session.planned_minutes,
                1.0,
                "active_session_exists",
            )
        return WorkDecision(DecisionAction.ASK_FOR_WORK, None, None, None, 1.0, "no_active_session")
