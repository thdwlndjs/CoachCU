from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.models import ActivityLog, DevicePolicy, WorkSession


def default_db_path() -> Path:
    return Path.home() / "AppData" / "Local" / "PersonalWorkCoach" / "coach.db"


class SQLiteRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.migrate()

    def close(self) -> None:
        self.connection.close()

    def migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS work_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                intent TEXT NOT NULL,
                task_name TEXT NOT NULL,
                planned_minutes INTEGER NOT NULL,
                actual_minutes INTEGER,
                result TEXT,
                memo TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                process_name TEXT NOT NULL,
                window_title TEXT NOT NULL DEFAULT '',
                idle_seconds INTEGER NOT NULL,
                FOREIGN KEY(session_id) REFERENCES work_sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS device_policy (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                run_on_login INTEGER NOT NULL,
                run_on_unlock INTEGER NOT NULL,
                active_start_time TEXT NOT NULL,
                active_end_time TEXT NOT NULL
            );
            """
        )
        if self.connection.execute("SELECT COUNT(*) FROM device_policy").fetchone()[0] == 0:
            self.save_policy(DevicePolicy())
        self.connection.commit()

    def create_session(self, session: WorkSession) -> WorkSession:
        cursor = self.connection.execute(
            """
            INSERT INTO work_sessions (
                started_at, ended_at, intent, task_name, planned_minutes,
                actual_minutes, result, memo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.started_at.isoformat(timespec="seconds"),
                session.ended_at.isoformat(timespec="seconds") if session.ended_at else None,
                session.intent,
                session.task_name,
                session.planned_minutes,
                session.actual_minutes,
                session.result,
                session.memo,
            ),
        )
        self.connection.commit()
        session.id = int(cursor.lastrowid)
        return session

    def update_session_result(self, session: WorkSession) -> None:
        if session.id is None:
            raise ValueError("session must be saved before it can be updated")
        self.connection.execute(
            """
            UPDATE work_sessions
            SET ended_at = ?, actual_minutes = ?, result = ?, memo = ?
            WHERE id = ?
            """,
            (
                session.ended_at.isoformat(timespec="seconds") if session.ended_at else None,
                session.actual_minutes,
                session.result,
                session.memo,
                session.id,
            ),
        )
        self.connection.commit()

    def add_activity_log(self, log: ActivityLog) -> ActivityLog:
        cursor = self.connection.execute(
            """
            INSERT INTO activity_logs (
                session_id, timestamp, process_name, window_title, idle_seconds
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                log.session_id,
                log.timestamp.isoformat(timespec="seconds"),
                log.process_name,
                log.window_title,
                log.idle_seconds,
            ),
        )
        self.connection.commit()
        log.id = int(cursor.lastrowid)
        return log

    def list_today_sessions(self, now: datetime | None = None) -> list[WorkSession]:
        current = now or datetime.now()
        start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        end = current.replace(hour=23, minute=59, second=59, microsecond=0)
        rows = self.connection.execute(
            """
            SELECT * FROM work_sessions
            WHERE started_at BETWEEN ? AND ?
            ORDER BY started_at DESC
            """,
            (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def get_active_session(self) -> WorkSession | None:
        """Return the most recent unfinished session, if the app was interrupted."""
        row = self.connection.execute(
            "SELECT * FROM work_sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return self._row_to_session(row) if row else None

    def list_activity_logs(self, session_id: int) -> list[ActivityLog]:
        rows = self.connection.execute(
            "SELECT * FROM activity_logs WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        ).fetchall()
        return [self._row_to_activity(row) for row in rows]

    def get_policy(self) -> DevicePolicy:
        row = self.connection.execute("SELECT * FROM device_policy WHERE id = 1").fetchone()
        return DevicePolicy(
            run_on_login=bool(row["run_on_login"]),
            run_on_unlock=bool(row["run_on_unlock"]),
            active_start_time=row["active_start_time"],
            active_end_time=row["active_end_time"],
        )

    def save_policy(self, policy: DevicePolicy) -> None:
        self.connection.execute(
            """
            INSERT INTO device_policy (id, run_on_login, run_on_unlock, active_start_time, active_end_time)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                run_on_login = excluded.run_on_login,
                run_on_unlock = excluded.run_on_unlock,
                active_start_time = excluded.active_start_time,
                active_end_time = excluded.active_end_time
            """,
            (
                int(policy.run_on_login),
                int(policy.run_on_unlock),
                policy.active_start_time,
                policy.active_end_time,
            ),
        )
        self.connection.commit()

    def _row_to_session(self, row: sqlite3.Row) -> WorkSession:
        return WorkSession(
            id=row["id"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            intent=row["intent"],
            task_name=row["task_name"],
            planned_minutes=row["planned_minutes"],
            actual_minutes=row["actual_minutes"],
            result=row["result"],
            memo=row["memo"],
        )

    def _row_to_activity(self, row: sqlite3.Row) -> ActivityLog:
        return ActivityLog(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            process_name=row["process_name"],
            window_title=row["window_title"],
            idle_seconds=row["idle_seconds"],
        )
