# Personal Work Coach — Codex / Claude Code Implementation Brief

> Status: MVP implementation specification
> Platform: Windows 10/11
> Primary goal: validate the desktop/session/activity-tracking loop before adding AI personalization.

## 1. Mission

Build a small Windows desktop application that intervenes when the user enters a Windows session, asks why the PC is being used, starts a bounded work session, records actual foreground application activity, and persists the session locally.

The MVP is successful when the following real-world loop works:

```text
Windows login / session unlock
        ↓
Personal Work Coach appears
        ↓
"왜 컴퓨터를 사용하려고 해?"
        ↓
Select intent
        ↓
Set task + timebox
        ↓
Run timer
        ↓
Record foreground app + idle state
        ↓
Finish / result
        ↓
Persist to SQLite
```

Do not turn this into an AI productivity platform during MVP implementation.

## 2. Agent operating rules

### Investigate before editing

Before changing code, inspect the repository and runtime environment. At minimum determine:

- current working directory
- git status and recent commits
- existing project structure
- Python version
- existing dependency management
- existing tests
- existing README / docs
- whether this is a new project or an existing application
- Windows-specific capabilities available in the environment

Never claim a file, API, architecture, or behavior without opening or verifying the relevant source/documentation.

### Plan before implementation

After reconnaissance, write a short implementation plan in `docs/implementation-plan.md` containing:

- discovered environment
- architecture decision
- Windows session-event approach
- foreground-window tracking approach
- startup approach
- data model
- verification plan
- known uncertainties

If a Windows-specific API is uncertain, build a minimal proof of concept first instead of implementing the whole application around an assumption.

### Scope discipline

Implement exactly the MVP defined here. Do not add:

- LLM/API integration
- cloud backend
- authentication/account system
- web frontend
- remote database
- OCR
- continuous screenshot analysis
- camera/microphone capture
- keyboard-content logging
- YouTube/site blocking
- ML/recommendation model
- mobile app
- multi-user architecture
- Docker unless the existing repository already requires it
- speculative abstractions for future phases

Prefer the smallest maintainable implementation. Do not create abstractions for one-time operations or hypothetical future requirements.

### Verification discipline

Tests verify requirements; tests must not be weakened or rewritten merely to make an implementation pass.

After each meaningful implementation phase, run the smallest relevant verification. At the end, perform the required Windows manual verification.

If something cannot be verified in the current environment, report it explicitly instead of marking it complete.

### Git discipline

Make small logical commits. Use Conventional Commits where appropriate, for example:

```text
feat: initialize desktop application
feat: add work intent flow
feat: add session timer
feat: add activity tracking
feat: add sqlite persistence
feat: add windows session handling
feat: add startup policy
test: add session and tracking tests
docs: add verification guide
```

Do not mix unrelated changes into one commit.

## 3. Product contract

### User intents

MVP intent choices:

- 코딩
- 구직
- 자소서 업데이트
- 문서 업데이트
- 학습
- 휴식
- 기타

Use stable internal identifiers rather than relying on display strings as database keys.

### Session events

The application needs to react to:

- Windows user login
- Windows session unlock

The password/PIN screen itself is not an application surface. The application appears after the user successfully unlocks the Windows session.

The application does not need to treat sleep itself as the primary event. Session unlock is the important resume point.

### Time policy

Support configurable automatic-launch policy:

```text
run_on_login: boolean
run_on_unlock: boolean
active_start_time: HH:MM
active_end_time: HH:MM
```

Example:

```text
run_on_login = true
run_on_unlock = true
active_start_time = 09:00
active_end_time = 18:00
```

When an OS-triggered event occurs outside the active window, do not automatically present the work prompt.

A user manually launching the application should remain distinguishable from an OS-triggered launch where practical.

## 4. Functional requirements

### FR-01 — Application startup

The desktop application must start normally from a user command.

Acceptance criteria:

- application opens without a backend/server
- application can be closed normally
- application does not require internet access for the MVP

### FR-02 — Windows login / unlock handling

Acceptance criteria:

- login event can trigger application presentation when enabled
- session unlock can trigger application presentation when enabled
- lock state itself does not start a work session
- behavior respects the configured active time window

The implementation method must be based on verified Windows behavior. Document the chosen mechanism and why it was selected.

### FR-03 — Intent screen

First user-facing screen after an eligible automatic launch:

```text
왜 컴퓨터를 사용하려고 해?

[코딩]
[구직]
[자소서 업데이트]
[문서 업데이트]
[학습]
[휴식]
[기타]
```

Selecting an intent moves the user into session setup.

### FR-04 — Session setup

Collect the minimum information needed to start a work session:

- intent
- task name
- planned minutes

Do not build a full calendar/task-management system in MVP.

### FR-05 — Timebox timer

Provide a countdown timer.

Required states:

```text
idle → running → completed
             ↘ cancelled
```

Pause/resume is optional and should only be implemented if it does not materially complicate the MVP.

At zero, transition to the result screen.

### FR-06 — Activity tracking

During an active work session, record:

```text
timestamp
session_id
process_name
window_title (optional / privacy-reviewed)
idle_seconds
```

The primary MVP signal is the foreground application/process.

Example:

```text
19:50 VSCode
19:57 Windows Terminal
20:03 Chrome
20:08 Chrome
20:12 VSCode
```

Do not infer that a particular application means distraction. Record facts only.

### FR-07 — Idle tracking

Define idle time as elapsed time since the last user input according to the Windows OS.

Do not label idle as "unproductive" in the data model.

### FR-08 — Session result

At the end of a session, show:

```text
[완료]
[부분 완료]
[막힘]
[중단]
```

Allow an optional short memo.

### FR-09 — Persistence

Use SQLite locally.

Minimum entities:

#### work_sessions

```text
id
started_at
ended_at
intent
task_name
planned_minutes
actual_minutes
result
memo
```

#### activity_logs

```text
id
session_id
timestamp
process_name
window_title
idle_seconds
```

#### device_policy

```text
id
run_on_login
run_on_unlock
active_start_time
active_end_time
```

The exact schema may be adjusted if the implementation has a concrete reason, but do not add speculative tables/entities.

## 5. UI scope

MVP screens:

```text
IntentScreen
SessionSetupScreen
TimerScreen
SessionResultScreen
HistoryScreen
SettingsScreen
```

Keep visual design functional and minimal. No design system, animations, or visual polish work unless required for usability.

### HistoryScreen

Show at least today's sessions:

```text
오늘

코딩 / Oracle 배포
40분 계획 / 47분 실제
부분 완료
```

Detailed activity visualization is optional for MVP and should not delay the core loop.

### SettingsScreen

Minimum settings:

- run on login
- run on unlock
- active start time
- active end time

## 6. Architecture

Preferred initial direction:

```text
Windows Desktop
│
├── PySide6 UI
├── Session Event Monitor
├── Activity Tracker
├── Session / Timer Service
├── SQLite Repository
└── Local Configuration
```

Likely technology choices:

- Python 3.x
- PySide6
- SQLite
- psutil
- pywin32 and/or native Windows API as justified by verification

Do not assume these exact libraries are correct if repository constraints or verified Windows behavior indicate otherwise.

No server is required for MVP.

## 7. Privacy boundary

This application is a personal activity tracker. Minimize collected data.

MVP must NOT collect:

- screenshots continuously
- webcam data
- microphone data
- keyboard input contents
- passwords/PINs
- clipboard contents
- remote telemetry

`window_title` can contain personal or sensitive text. Evaluate whether it is actually needed. If process name alone satisfies the MVP, prefer process name only.

## 8. Repository structure

If starting from an empty repository, a reasonable minimal structure is:

```text
personal-work-coach/
├── app/
│   ├── main.py
│   ├── ui/
│   ├── services/
│   ├── tracking/
│   ├── storage/
│   └── models/
├── tests/
├── docs/
├── requirements.txt
└── README.md
```

This is guidance, not a command to restructure an existing repository. If the repository already has a coherent structure, preserve it.

## 9. Implementation sequence

Implement in this order because it maximizes early validation:

### Phase 0 — Reconnaissance

Inspect repository and environment. Do not write application code yet.

### Phase 1 — Windows feasibility POC

Independently verify:

- a PySide6 window can launch
- active foreground process/window can be read
- idle time can be read
- login/session-unlock event can be observed using the selected mechanism

Record results in `docs/implementation-plan.md`.

### Phase 2 — Core local application

Implement:

```text
launch
→ intent
→ session setup
→ timer
→ result
```

### Phase 3 — Persistence

Add SQLite and session/activity persistence.

### Phase 4 — Activity tracking

Connect foreground process + idle tracking to the active session.

### Phase 5 — Windows integration

Add automatic launch and session unlock handling after the underlying mechanism has been verified.

### Phase 6 — Settings + history

Add only the minimum settings/history required by this specification.

### Phase 7 — End-to-end verification

Perform the manual Windows verification below.

## 10. Verification matrix

### Automated / local tests

Verify at minimum:

- session duration calculation
- planned vs actual duration calculation
- active-window policy evaluation
- session state transitions
- SQLite create/read/update behavior
- activity log → session relationship

### Manual Windows verification

```text
[ ] launch application manually
[ ] Windows login auto-launch
[ ] Windows lock
[ ] PIN/password unlock
[ ] application appears after unlock
[ ] automatic launch suppressed before configured start time
[ ] automatic launch allowed after configured start time
[ ] 1-minute timer completes
[ ] foreground process is recorded
[ ] idle period is recorded
[ ] result is saved
[ ] application restart retains history
```

For each item report PASS / FAIL / NOT VERIFIED.

## 11. Definition of Done

The MVP is complete only when:

- the application runs locally on Windows
- login and/or unlock behavior selected in settings works as specified
- intent selection works
- a timed session can start and finish
- foreground activity is recorded
- idle time is recorded
- session result is persisted to SQLite
- history can read persisted sessions
- relevant automated tests pass
- manual Windows verification has been performed or explicitly marked not verified
- README explains installation, launch, configuration, and verification
- no out-of-scope AI/cloud features were introduced

## 12. Failure handling

If a Windows API or library behaves differently from expectation:

1. reproduce the behavior with the smallest possible experiment
2. inspect the actual error/event data
3. check authoritative documentation when needed
4. choose the smallest viable alternative
5. update `docs/implementation-plan.md`
6. continue only after the technical uncertainty is resolved

Do not silently replace an uncertain mechanism with a fake timer or hardcoded behavior.

## 13. Required final report

At completion, report exactly these sections:

```text
## What changed

## Files changed

## Tests

## Windows manual verification

## Technical decisions

## Known limitations

## Next recommended step
```

Separate verified facts from assumptions. Do not claim that Windows login/unlock behavior was verified unless it was actually tested.

## 14. Explicitly deferred product roadmap

Do NOT implement these now. They are the reason the MVP is being instrumented correctly.

### Phase 2 — Personal statistics

- planned vs actual duration
- task-level average duration
- idle ratio
- foreground-app distribution
- interruption count
- overtime rate

### Phase 3 — Pattern detection

Example future insight:

```text
배포 설정
평균 계획: 35분
평균 실제: 52분
```

The system may later detect recurring delay patterns from accumulated sessions.

### Phase 4 — Adaptive scheduling

Use historical data to propose realistic timeboxes and split tasks into smaller execution targets.

### Phase 5 — LLM coach

Only after reliable structured activity data exists, add an LLM that can:

- propose today's work allocation
- estimate timeboxes from history
- explain repeated overruns
- suggest the next task
- identify recurring workflow patterns

The LLM should consume structured session/activity data rather than receiving continuous raw screen captures by default.

## 15. Product principle

The product is not primarily a blocking app.

It should evolve from:

```text
"YouTube를 30분 봤으니 차단"
```

toward:

```text
"네가 40분 동안 Oracle 배포를 하기로 했고,
실제로는 Chrome 18분 / VS Code 17분 / Terminal 5분을 사용했다.
이 작업은 최근 평균 52분이 걸렸다."
```

The MVP therefore prioritizes accurate session boundaries and factual activity logs over AI judgment.
