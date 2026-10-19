# Personal Work Coach

Windows용 개인 작업 세션 코치 MVP입니다. 의도와 작업명을 정해 시간 제한 세션을 시작하고, 활성 앱과 Windows 유휴 시간을 로컬 SQLite에 기록합니다. 인터넷, 계정, 클라우드 서비스는 사용하지 않습니다.

## 설치 및 실행

프로젝트 루트의 `run.ps1`이 권장 실행 방법입니다. Python 패키지가 없으면 첫 실행 때 `requirements.txt`에서 자동 설치합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

개발용 데이터베이스 경로도 전달할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 --db C:\path\coach.db
```

PowerShell 실행 정책을 이미 설정했다면 다음처럼 실행해도 됩니다.

```powershell
.\run.ps1
```

수동 설치 및 실행 방법은 다음과 같습니다.

```powershell
python -m pip install -r requirements.txt
python -m app.main
```

Python 3.10 이상과 Windows 10/11이 필요합니다. 기본 데이터베이스는 `%LOCALAPPDATA%\PersonalWorkCoach\coach.db`입니다.

## 사용

1. 의도를 고르고 작업명과 계획 시간을 입력합니다.
2. 세션 중에는 매분 활성 프로세스와 Windows 유휴 시간이 로컬에 기록됩니다.
3. 종료 또는 중단 후 결과와 선택 메모를 저장합니다.
4. 오늘 기록 화면에서 저장된 세션을 확인합니다.

설정에서 로그인 시 실행, 잠금 해제 시 표시, 자동 표시 활성 시간대를 변경할 수 있습니다. 로그인 자동 실행은 현재 사용자 Run 레지스트리 키를 사용합니다.

앱을 한 번 실행하면 현재 사용자용 Windows 작업 스케줄러 작업 `PersonalWorkCoach Unlock`도 등록됩니다. 따라서 앱을 직접 종료했더라도 다음 잠금 해제 시 Windows가 `--trigger unlock`으로 앱을 다시 시작합니다. 이미 앱이 실행 중이면 새 창을 만들지 않고 기존 창으로 잠금 해제 신호를 전달합니다. 잠금 해제 설정을 끄면 이 작업도 제거됩니다.

## 판단 엔진 (Groq / 향후 JEV)

작업 진입 시 앱은 `DecisionEngine` 계약을 통해 하나의 구조화된 판단을 받습니다. 현재는 `GROQ_API_KEY`가 설정돼 있으면 Groq를 사용하고, 키가 없거나 호출에 실패하면 외부 호출 없이 로컬 규칙 엔진으로 안전하게 전환합니다. 실제 세션 시작·저장·종료 권한은 UI와 로컬 코드에 남아 있으며, 모델은 제안만 합니다.

Groq 키는 소스 파일에 저장하지 말고 사용자 환경 변수로 설정합니다. 새 PowerShell 창을 연 뒤 앱을 실행하세요.

```powershell
[Environment]::SetEnvironmentVariable("GROQ_API_KEY", "your_key_here", "User")
```

선택적으로 모델을 지정할 수 있으며 기본값은 `openai/gpt-oss-20b`입니다.

```powershell
[Environment]::SetEnvironmentVariable("GROQ_MODEL", "openai/gpt-oss-20b", "User")
```

JEV 접근 권한이 생기면 `DecisionEngine` 계약을 구현한 공급자만 추가하면 됩니다. UI, 세션 저장소, 잠금 해제 처리 코드를 다시 작성할 필요가 없습니다.

## 테스트

```powershell
python -m unittest discover -v
```
