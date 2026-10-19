from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QTimer, QTime, Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton, QSpinBox, QStackedWidget, QTextEdit, QTimeEdit, QVBoxLayout, QWidget

from app.models import ActivityLog, DevicePolicy, INTENTS, RESULTS, WorkSession
from app.services.policy import should_present_for_trigger
from app.services.decision import DecisionAction, RuleBasedDecisionEngine, WorkContext
from app.services.groq_decision import GroqDecisionEngine, ResilientDecisionEngine
from app.services.session_events import WM_WTSSESSION_CHANGE, WindowsSessionEventMonitor
from app.services.startup import set_run_on_login, set_run_on_unlock
from app.services.single_instance import SingleInstance
from app.services.timer import SessionTimer, calculate_actual_minutes
from app.storage import SQLiteRepository
from app.tracking import WindowsActivityTracker


class NativeEventFilter(QAbstractNativeEventFilter):
    """Forwards Windows WTS notifications delivered to Qt's native window."""

    def __init__(self, monitor: WindowsSessionEventMonitor) -> None:
        super().__init__()
        self.monitor = monitor

    def nativeEventFilter(self, event_type, message):
        try:
            import ctypes

            class MSG(ctypes.Structure):
                _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint), ("wParam", ctypes.c_size_t), ("lParam", ctypes.c_ssize_t), ("time", ctypes.c_uint), ("pt", ctypes.c_long * 2)]

            native = MSG.from_address(message.__int__())
            if native.message == WM_WTSSESSION_CHANGE:
                self.monitor.handle_native_message(native.message, native.wParam)
        except Exception:
            pass
        return False, 0


class MainWindow(QMainWindow):
    def __init__(self, repository: SQLiteRepository, trigger: str = "manual", minimized: bool = False) -> None:
        super().__init__()
        self.repository, self.trigger = repository, trigger
        self.tracker = WindowsActivityTracker()
        self.current_intent = ""
        self.current_session: WorkSession | None = None
        self.session_timer: SessionTimer | None = None
        self.decision_engine = ResilientDecisionEngine(GroqDecisionEngine.from_environment(), RuleBasedDecisionEngine())
        self.session_monitor: WindowsSessionEventMonitor | None = None
        self.native_filter: NativeEventFilter | None = None
        self.tick_timer, self.activity_timer = QTimer(self), QTimer(self)
        self.tick_timer.timeout.connect(self._on_timer_tick); self.tick_timer.setInterval(1_000)
        self.activity_timer.timeout.connect(self._record_activity); self.activity_timer.setInterval(60_000)
        self.stack = QStackedWidget(); self.setCentralWidget(self.stack)
        self.setWindowTitle("Personal Work Coach"); self.resize(520, 420)
        self._build_intent(); self._build_setup(); self._build_timer(); self._build_result(); self._build_history(); self._build_settings()
        self._install_session_unlock_monitor()
        if should_present_for_trigger(self.repository.get_policy(), trigger, datetime.now().time()): self._present_for_trigger(trigger)
        else: self.show_history()
        if minimized: self.showMinimized()

    def _install_session_unlock_monitor(self) -> None:
        self.session_monitor = WindowsSessionEventMonitor(int(self.winId()), self._handle_unlock)
        if self.session_monitor.start():
            self.native_filter = NativeEventFilter(self.session_monitor)
            QCoreApplication.instance().installNativeEventFilter(self.native_filter)

    def closeEvent(self, event) -> None:
        if self.session_monitor:
            self.session_monitor.stop()
        self.repository.close()
        super().closeEvent(event)

    def _screen(self, title: str):
        screen = QWidget(); layout = QVBoxLayout(screen); heading = QLabel(title)
        heading.setAlignment(Qt.AlignCenter); heading.setStyleSheet("font-size: 22px; font-weight: 600;"); layout.addWidget(heading)
        return screen, layout

    def _build_intent(self) -> None:
        screen, layout = self._screen("컴퓨터를 사용하려고?")
        for key, label in INTENTS:
            button = QPushButton(label); button.clicked.connect(lambda checked=False, value=key: self._select_intent(value)); layout.addWidget(button)
        layout.addStretch(); nav = QHBoxLayout()
        for text, target in (("오늘 기록", self.show_history), ("설정", self.show_settings)):
            b = QPushButton(text); b.clicked.connect(target); nav.addWidget(b)
        layout.addLayout(nav); self.intent_screen = screen; self.stack.addWidget(screen)

    def _build_setup(self) -> None:
        screen, layout = self._screen("작업 세션 설정")
        self.intent_label, self.task_input, self.minutes_input = QLabel(), QLineEdit(), QSpinBox()
        self.task_input.setPlaceholderText("작업 이름"); self.minutes_input.setRange(1, 240); self.minutes_input.setValue(40)
        form = QFormLayout(); form.addRow("의도", self.intent_label); form.addRow("작업", self.task_input); form.addRow("계획 시간(분)", self.minutes_input); layout.addLayout(form)
        for text, target in (("시작", self._start_session), ("뒤로", self.show_intent)):
            b = QPushButton(text); b.clicked.connect(target); layout.addWidget(b)
        layout.addStretch(); self.setup_screen = screen; self.stack.addWidget(screen)

    def _build_timer(self) -> None:
        screen, layout = self._screen("진행 중"); self.timer_task_label, self.remaining_label = QLabel(), QLabel("00:00")
        self.timer_task_label.setAlignment(Qt.AlignCenter); self.remaining_label.setAlignment(Qt.AlignCenter); self.remaining_label.setStyleSheet("font-size: 44px; font-weight: 700;")
        cancel = QPushButton("중단"); cancel.clicked.connect(self._cancel_session)
        for item in (self.timer_task_label, self.remaining_label, cancel): layout.addWidget(item)
        layout.addStretch(); self.timer_screen = screen; self.stack.addWidget(screen)

    def _build_result(self) -> None:
        screen, layout = self._screen("세션 결과"); self.result_combo, self.memo_input = QComboBox(), QTextEdit()
        for key, label in RESULTS: self.result_combo.addItem(label, key)
        self.memo_input.setPlaceholderText("메모 (선택)"); form = QFormLayout(); form.addRow("결과", self.result_combo); form.addRow("메모", self.memo_input)
        save = QPushButton("저장"); save.clicked.connect(self._save_result); layout.addLayout(form); layout.addWidget(save); layout.addStretch()
        self.result_screen = screen; self.stack.addWidget(screen)

    def _build_history(self) -> None:
        screen, layout = self._screen("오늘"); self.history_list = QListWidget(); layout.addWidget(self.history_list)
        refresh = QPushButton("새로고침"); refresh.clicked.connect(self._load_history); layout.addWidget(refresh); nav = QHBoxLayout()
        for text, target in (("새 세션", self.show_intent), ("설정", self.show_settings)):
            b = QPushButton(text); b.clicked.connect(target); nav.addWidget(b)
        layout.addLayout(nav); self.history_screen = screen; self.stack.addWidget(screen)

    def _build_settings(self) -> None:
        screen, layout = self._screen("설정"); self.run_login_check, self.run_unlock_check = QCheckBox("로그인 시 실행"), QCheckBox("잠금 해제 시 표시")
        self.start_time_input, self.end_time_input = QTimeEdit(), QTimeEdit()
        for field in (self.start_time_input, self.end_time_input): field.setDisplayFormat("HH:mm")
        form = QFormLayout(); form.addRow(self.run_login_check); form.addRow(self.run_unlock_check); form.addRow("활성 시작", self.start_time_input); form.addRow("활성 종료", self.end_time_input)
        save, back = QPushButton("저장"), QPushButton("기록으로"); save.clicked.connect(self._save_settings); back.clicked.connect(self.show_history)
        layout.addLayout(form); layout.addWidget(save); layout.addWidget(back); layout.addStretch(); self.settings_screen = screen; self.stack.addWidget(screen)

    def show_intent(self) -> None:
        self.stack.setCurrentWidget(self.intent_screen); self.showNormal(); self.raise_(); self.activateWindow()

    def _present_for_trigger(self, trigger: str) -> None:
        """Apply an advisory decision while keeping session mutation in the UI layer."""
        active = self.current_session or self.repository.get_active_session()
        decision = self.decision_engine.decide(
            WorkContext(trigger, datetime.now(), active, tuple(self.repository.list_today_sessions()))
        )
        if decision.action == DecisionAction.RESUME_SESSION and active is not None:
            self.current_session = active
            self.session_timer = SessionTimer(active.planned_minutes, active.started_at)
            self.timer_task_label.setText(active.task_name)
            self.stack.setCurrentWidget(self.timer_screen)
            self.tick_timer.start(); self.activity_timer.start(); self._record_activity(); self._update_remaining()
            self.showNormal(); self.raise_(); self.activateWindow()
            return
        if decision.action == DecisionAction.SUGGEST_WORK:
            self.current_intent = decision.intent or "other"
            self.intent_label.setText(dict(INTENTS).get(self.current_intent, self.current_intent))
            self.task_input.setText(decision.task_name or "")
            if decision.planned_minutes:
                self.minutes_input.setValue(decision.planned_minutes)
            self.stack.setCurrentWidget(self.setup_screen)
            self.showNormal(); self.raise_(); self.activateWindow()
            return
        self.show_intent()

    def show_history(self) -> None:
        self._load_history(); self.stack.setCurrentWidget(self.history_screen)

    def show_settings(self) -> None:
        policy = self.repository.get_policy(); self.run_login_check.setChecked(policy.run_on_login); self.run_unlock_check.setChecked(policy.run_on_unlock)
        self.start_time_input.setTime(QTime.fromString(policy.active_start_time, "HH:mm")); self.end_time_input.setTime(QTime.fromString(policy.active_end_time, "HH:mm")); self.stack.setCurrentWidget(self.settings_screen)

    def _select_intent(self, intent: str) -> None:
        self.current_intent = intent; self.intent_label.setText(dict(INTENTS).get(intent, intent)); self.stack.setCurrentWidget(self.setup_screen)

    def _start_session(self) -> None:
        task = self.task_input.text().strip()
        if not task: QMessageBox.warning(self, "작업 필요", "작업 이름을 입력하세요."); return
        self.current_session = self.repository.create_session(WorkSession(None, datetime.now(), None, self.current_intent, task, self.minutes_input.value()))
        self.session_timer = SessionTimer(self.current_session.planned_minutes, self.current_session.started_at); self.timer_task_label.setText(task); self.stack.setCurrentWidget(self.timer_screen)
        self.tick_timer.start(); self.activity_timer.start(); self._record_activity(); self._update_remaining()

    def _on_timer_tick(self) -> None:
        if self.session_timer and self.session_timer.tick().value == "completed": self._finish_session("done")
        self._update_remaining()

    def _update_remaining(self) -> None:
        seconds = self.session_timer.remaining_seconds() if self.session_timer else 0; self.remaining_label.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")

    def _cancel_session(self) -> None:
        if self.session_timer: self.session_timer.cancel()
        self._finish_session("cancelled")

    def _finish_session(self, default_result: str) -> None:
        if not self.current_session: return
        self.tick_timer.stop(); self.activity_timer.stop(); ended_at = datetime.now(); self.current_session.ended_at = ended_at; self.current_session.actual_minutes = calculate_actual_minutes(self.current_session, ended_at)
        self.result_combo.setCurrentIndex(max(0, self.result_combo.findData(default_result))); self.stack.setCurrentWidget(self.result_screen)

    def _save_result(self) -> None:
        if not self.current_session: return
        self.current_session.result = self.result_combo.currentData(); self.current_session.memo = self.memo_input.toPlainText().strip(); self.repository.update_session_result(self.current_session)
        self.current_session = None; self.session_timer = None; self.task_input.clear(); self.memo_input.clear(); self.show_history()

    def _record_activity(self) -> None:
        if not self.current_session or self.current_session.id is None: return
        s = self.tracker.snapshot(); self.repository.add_activity_log(ActivityLog(None, self.current_session.id, datetime.now(), s.process_name, s.window_title, s.idle_seconds))

    def _load_history(self) -> None:
        self.history_list.clear(); intents, results = dict(INTENTS), dict(RESULTS)
        for session in self.repository.list_today_sessions():
            actual = session.actual_minutes if session.actual_minutes is not None else "-"; result = results.get(session.result or "", session.result or "진행 중")
            self.history_list.addItem(f"{intents.get(session.intent, session.intent)} / {session.task_name}\n{session.planned_minutes}분 계획 / {actual}분 실제\n{result}")

    def _save_settings(self) -> None:
        policy = DevicePolicy(self.run_login_check.isChecked(), self.run_unlock_check.isChecked(), self.start_time_input.time().toString("HH:mm"), self.end_time_input.time().toString("HH:mm")); self.repository.save_policy(policy)
        try:
            set_run_on_login(policy.run_on_login)
            set_run_on_unlock(policy.run_on_unlock)
        except OSError as exc: QMessageBox.warning(self, "시작 설정 실패", str(exc))
        self.show_history()

    def _handle_unlock(self) -> None:
        if should_present_for_trigger(self.repository.get_policy(), "unlock", datetime.now().time()):
            self._present_for_trigger("unlock")

    def handle_external_trigger(self, trigger: str) -> None:
        if trigger in {"login", "unlock", "manual"} and should_present_for_trigger(self.repository.get_policy(), trigger, datetime.now().time()):
            self._present_for_trigger(trigger)


def run_app(repository: SQLiteRepository, trigger: str, minimized: bool) -> int:
    app = QApplication([])
    if SingleInstance.notify_existing(trigger):
        repository.close()
        return 0
    window = MainWindow(repository, trigger, minimized)
    instance = SingleInstance(window.handle_external_trigger)
    instance.listen()
    if not minimized: window.show()
    return app.exec()
