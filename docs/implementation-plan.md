# Implementation Plan

## Discovered Environment

- Working directory: `C:\Users\dev\Desktop\CoachCU`
- Repository state: not currently a git repository; no commit history is available.
- Existing project structure: only `Personal_Work_Coach_Codex_Task_Request.md` was present before implementation.
- Python version: Python 3.10.11.
- Dependency management: none existed; this MVP will use `requirements.txt`.
- Existing tests: none existed.
- Existing README/docs: only the task request existed.
- Windows capabilities observed:
  - `sys.platform` reports `win32`.
  - `ctypes.windll` is available.
  - `psutil` is installed in the current environment.
  - `PySide6` is not installed in the current environment.
  - `pywin32` is not installed in the current environment.

## Architecture Decision

Use a small Python desktop application with clear boundaries:

- `app/ui`: PySide6 screens and main window.
- `app/services`: session timer, policy, startup, and Windows session event handling.
- `app/tracking`: foreground process and idle-time tracking.
- `app/storage`: SQLite repository.
- `app/models`: stable dataclasses and identifiers.

The core model, policy, timer, and SQLite behavior remain testable without PySide6.

## Windows Session-Event Approach

Login auto-launch will use the current user's Windows Run registry key:

`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`

This starts the application after Windows user login when `run_on_login` is enabled.

Session unlock will be observed while the app process is running by registering a hidden/native window for `WTSRegisterSessionNotification` and handling `WM_WTSSESSION_CHANGE` with `WTS_SESSION_UNLOCK`.

This approach is selected because Windows does not expose the password/PIN screen as an app surface; the relevant event is after a successful unlock. The app should therefore be launched on login and kept available to receive unlock events.

Current verification status: API availability is plausible through `ctypes.windll` on this machine, but live lock/unlock behavior still requires manual Windows verification.

## Foreground-Window Tracking Approach

Use native Windows APIs through `ctypes`:

- `GetForegroundWindow`
- `GetWindowThreadProcessId`
- `OpenProcess`
- `QueryFullProcessImageNameW`
- `GetWindowTextW`

Process name is the primary MVP signal. Window title is optional and privacy-sensitive, so the app stores it only when the local setting `capture_window_title` is enabled internally; the MVP default is process-name first.

## Startup Approach

The Settings screen writes the login startup policy to SQLite and mirrors `run_on_login` into the HKCU Run key. Manual launches remain distinct from OS-triggered launches through a `--trigger` command-line argument, with `manual` as the default.

## Data Model

SQLite tables:

- `work_sessions`
  - `id`
  - `started_at`
  - `ended_at`
  - `intent`
  - `task_name`
  - `planned_minutes`
  - `actual_minutes`
  - `result`
  - `memo`
- `activity_logs`
  - `id`
  - `session_id`
  - `timestamp`
  - `process_name`
  - `window_title`
  - `idle_seconds`
- `device_policy`
  - `id`
  - `run_on_login`
  - `run_on_unlock`
  - `active_start_time`
  - `active_end_time`

## Verification Plan

Automated tests:

- Session duration calculation.
- Planned vs actual duration calculation.
- Active-window policy evaluation.
- Session state transitions.
- SQLite create/read/update behavior.
- Activity log to session relationship.

Manual Windows verification:

- Launch application manually.
- Windows login auto-launch.
- Windows lock.
- PIN/password unlock.
- Application appears after unlock.
- Automatic launch suppressed before configured start time.
- Automatic launch allowed after configured start time.
- 1-minute timer completes.
- Foreground process is recorded.
- Idle period is recorded.
- Result is saved.
- Application restart retains history.

## Known Uncertainties

- PySide6 is not installed in the current environment, so GUI launch verification requires installing dependencies.
- Live login/unlock behavior cannot be fully verified without an interactive Windows session lock/unlock cycle.
- Registry startup writes are user-specific and require testing on the target Windows account.
