from datetime import datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.models import ActivityLog, DevicePolicy, SessionState, WorkSession
from app.services.policy import is_within_active_window, should_present_for_trigger
from app.services.decision import DecisionAction, RuleBasedDecisionEngine, WorkContext
from app.services.groq_decision import GroqDecisionEngine, ResilientDecisionEngine
from app.services.startup import build_unlock_task_xml
from app.services.timer import SessionTimer, calculate_actual_minutes
from app.storage import SQLiteRepository


class CoreTests(unittest.TestCase):
    def test_timer_states_and_duration(self):
        start = datetime(2026, 1, 1, 9, 0); timer = SessionTimer(1, start)
        self.assertEqual(timer.remaining_seconds(start + timedelta(seconds=30)), 30)
        self.assertEqual(timer.tick(start + timedelta(minutes=1)), SessionState.COMPLETED)
        self.assertEqual(SessionTimer(2, start).cancel(), SessionState.CANCELLED)
        session = WorkSession(None, start, None, "coding", "task", 40)
        self.assertEqual(calculate_actual_minutes(session, start + timedelta(seconds=1)), 1)
        self.assertEqual(calculate_actual_minutes(session, start + timedelta(minutes=47, seconds=31)), 48)

    def test_policy(self):
        policy = DevicePolicy(False, True, "09:00", "18:00")
        self.assertTrue(is_within_active_window(policy, time(9)))
        self.assertFalse(is_within_active_window(policy, time(19)))
        self.assertTrue(should_present_for_trigger(policy, "manual", time(2)))
        self.assertFalse(should_present_for_trigger(policy, "login", time(10)))
        self.assertTrue(should_present_for_trigger(policy, "unlock", time(10)))

    def test_sqlite_persistence_and_relationship(self):
        with TemporaryDirectory() as directory:
            repo = SQLiteRepository(Path(directory) / "coach.db"); policy = DevicePolicy(False, True, "08:00", "17:00"); repo.save_policy(policy); self.assertEqual(repo.get_policy(), policy)
            session = repo.create_session(WorkSession(None, datetime.now(), None, "coding", "Write tests", 40)); self.assertIsNotNone(session.id)
            repo.add_activity_log(ActivityLog(None, session.id, datetime.now(), "python.exe", "", 3))
            session.ended_at = session.started_at + timedelta(minutes=40); session.actual_minutes = 40; session.result = "done"; repo.update_session_result(session)
            self.assertEqual(repo.list_today_sessions()[0].result, "done"); self.assertEqual(repo.list_activity_logs(session.id)[0].session_id, session.id); repo.close()

    def test_unfinished_session_is_recoverable(self):
        with TemporaryDirectory() as directory:
            repo = SQLiteRepository(Path(directory) / "coach.db")
            created = repo.create_session(WorkSession(None, datetime.now(), None, "coding", "Recover me", 40))
            self.assertEqual(repo.get_active_session().id, created.id)
            created.ended_at = datetime.now(); created.actual_minutes = 1; created.result = "cancelled"
            repo.update_session_result(created)
            self.assertIsNone(repo.get_active_session())
            repo.close()

    def test_decision_contract_and_offline_fallback(self):
        active = WorkSession(1, datetime.now(), None, "coding", "Resume task", 40)
        context = WorkContext("unlock", datetime.now(), active, (active,))
        decision = RuleBasedDecisionEngine().decide(context)
        self.assertEqual(decision.action, DecisionAction.RESUME_SESSION)
        fallback = ResilientDecisionEngine(None, RuleBasedDecisionEngine()).decide(context)
        self.assertEqual(fallback.reason_code, "active_session_exists")
        parsed = GroqDecisionEngine._parse({"action": "ask_for_work", "intent": None, "task_name": None, "planned_minutes": None, "confidence": 0.8, "reason_code": "needs_input"})
        self.assertEqual(parsed.action, DecisionAction.ASK_FOR_WORK)

    def test_unlock_task_definition_uses_session_unlock_and_app_trigger(self):
        xml = build_unlock_task_xml()
        self.assertIn("SessionStateChangeTrigger", xml)
        self.assertIn("SessionUnlock", xml)
        self.assertIn("--trigger unlock", xml)
        self.assertIn("MultipleInstancesPolicy>IgnoreNew", xml)
