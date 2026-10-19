from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


INTENTS = [
    ("coding", "코딩"),
    ("job_search", "구직"),
    ("resume_update", "자소서 업데이트"),
    ("document_update", "문서 업데이트"),
    ("study", "학습"),
    ("break", "휴식"),
    ("other", "기타"),
]

RESULTS = [
    ("done", "완료"),
    ("partial", "부분 완료"),
    ("failed", "망함"),
    ("cancelled", "중단"),
]


class SessionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DevicePolicy:
    run_on_login: bool = True
    run_on_unlock: bool = True
    active_start_time: str = "09:00"
    active_end_time: str = "18:00"


@dataclass
class WorkSession:
    id: Optional[int]
    started_at: datetime
    ended_at: Optional[datetime]
    intent: str
    task_name: str
    planned_minutes: int
    actual_minutes: Optional[int] = None
    result: Optional[str] = None
    memo: str = ""


@dataclass
class ActivityLog:
    id: Optional[int]
    session_id: int
    timestamp: datetime
    process_name: str
    window_title: str
    idle_seconds: int
