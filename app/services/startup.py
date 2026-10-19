from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import winreg
from html import escape
from pathlib import Path

APP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VALUE_NAME = "PersonalWorkCoach"
UNLOCK_TASK_NAME = "PersonalWorkCoach Unlock"


def build_startup_command() -> str:
    main_path = Path(__file__).resolve().parents[1] / "main.py"
    python = Path(sys.executable)
    return f'"{python}" "{main_path}" --trigger login --minimized'


def current_windows_account() -> str:
    """Use the token owner, not USERNAME, for Task Scheduler's principal."""
    if os.name != "nt":
        return os.environ.get("USERNAME", "")
    completed = subprocess.run(["whoami"], capture_output=True, text=True)
    account = completed.stdout.strip()
    if completed.returncode == 0 and account:
        return account
    return "\\".join(filter(None, (os.environ.get("USERDOMAIN"), os.environ.get("USERNAME"))))


def set_run_on_login(enabled: bool) -> None:
    if os.name != "nt":
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_VALUE_NAME, 0, winreg.REG_SZ, build_startup_command())
        else:
            try:
                winreg.DeleteValue(key, APP_VALUE_NAME)
            except FileNotFoundError:
                pass


def build_unlock_task_xml() -> str:
    """Build a per-user Task Scheduler task for every workstation unlock."""
    main_path = Path(__file__).resolve().parents[1] / "main.py"
    project_root = main_path.parents[1]
    account = current_windows_account()
    arguments = f'"{main_path}" --trigger unlock'
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Starts Personal Work Coach after this user unlocks Windows.</Description></RegistrationInfo>
  <Triggers><SessionStateChangeTrigger><Enabled>true</Enabled><UserId>{escape(account)}</UserId><Delay>PT3S</Delay><StateChange>SessionUnlock</StateChange></SessionStateChangeTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>{escape(account)}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowHardTerminate>false</AllowHardTerminate><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT0S</ExecutionTimeLimit></Settings>
  <Actions Context="Author"><Exec><Command>{escape(str(Path(sys.executable)))}</Command><Arguments>{escape(arguments)}</Arguments><WorkingDirectory>{escape(str(project_root))}</WorkingDirectory></Exec></Actions>
</Task>'''


def set_run_on_unlock(enabled: bool) -> None:
    """Create/remove the OS-owned unlock trigger, independent of app residency."""
    if os.name != "nt":
        return
    if not enabled:
        completed = subprocess.run(["schtasks", "/Delete", "/TN", UNLOCK_TASK_NAME, "/F"], capture_output=True, text=True)
        if completed.returncode not in (0, 1):
            raise OSError(completed.stderr.strip() or "Could not remove unlock task.")
        return
    task_file: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-16", suffix=".xml", delete=False) as handle:
            handle.write(build_unlock_task_xml())
            task_file = Path(handle.name)
        completed = subprocess.run(["schtasks", "/Create", "/TN", UNLOCK_TASK_NAME, "/XML", str(task_file), "/F"], capture_output=True, text=True)
        if completed.returncode != 0:
            raise OSError(completed.stderr.strip() or completed.stdout.strip() or "Could not create unlock task.")
    finally:
        if task_file:
            task_file.unlink(missing_ok=True)
