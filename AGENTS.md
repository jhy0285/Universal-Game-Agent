# AGENTS.md — AI 코딩 에이전트용 작업 안내

이 저장소만 연결한 AI(Claude Code, Codex, Cursor 등)가 추가 설명 없이 바로 작업을 이어갈 수
있도록 정리한 안내입니다. 사람용 소개는 [README](README.md)입니다.

## 프로젝트 한 줄 요약

Universal Game Agent(UGA)는 **허가된 게임**을 로컬 CPU에서 플레이(Player)·정적 분석(Reverse)·
생성(Builder)하고 결과를 측정하는 Python 패키지(`src/uga`)입니다. 지원 범위는 **자체 제작한 2D
탑다운 아레나**입니다. 임의의 상용 게임을 이해하는 AI가 아닙니다. 실제로 구현·검증된 범위의
기준은 [docs/phase-status.md](docs/phase-status.md), 다음에 할 일은
[docs/next-steps.md](docs/next-steps.md)입니다. 작업 전에 이 두 문서를 먼저 읽으세요.

## 바로 시작하기

Python 3.11 또는 3.12와 [uv](https://docs.astral.sh/uv/)가 필요합니다(Windows는 `.venv\Scripts\`).

```sh
bash scripts/setup-cloud.sh                     # frozen 설치 → .venv, 마지막에 uga doctor
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python -m pytest -q                   # Godot/JADX/Ghidra가 없으면 외부 도구 7개는 skip
.venv/bin/uga player --seed 7 --output .uga/try # success: true, goal_complete
```

- 이 문서를 쓴 시점의 기본 기대값은 **89 passed / 7 skipped**입니다(테스트를 추가하면 숫자가 늘어납니다).
  실패가 있으면 코드를 건드리기 전에 환경 문제인지 먼저 확인하세요.
- `setup-cloud.sh`는 `python3.11`/`python3.12`가 PATH에 있어야 하고 인터프리터를 내려받지 않습니다.
  둘 다 없으면 설치된 다른 Python으로 직접 동기화합니다. 3.13.17에서 린트와 기본 pytest가
  통과함을 확인했지만 CI는 3.11/3.12만 검사합니다.

  ```sh
  uv sync --frozen --python /path/to/python3.13 --no-python-downloads
  ```

  uv가 인터프리터를 내려받게 하려면 소유자에게 먼저 확인하세요.
- 변경을 마치면 위 린트·포맷·pytest를 모두 통과시킨 뒤 푸시하세요. `bash scripts/validate.sh`는
  린트·pytest·고정 시드 벤치마크를 한 번에 실행합니다(`.venv` 필요).
- 서버를 띄웠다면 끝내기 전에 `.venv/bin/uga service stop`으로 정리합니다.

## 저장소 지도

| 경로 | 역할 |
|---|---|
| `src/uga/core/` | 공통 계약(`contracts.py`, Pydantic)과 오류 타입(`errors.py`) |
| `src/uga/orchestrator/` | `jobs.py` 작업 큐·워커 프로세스·watchdog·아티팩트 봉인, `worker.py` 작업 종류별 계약과 실행 |
| `src/uga/agents/player/` | 화면 캡처 → 인식(`perception.py`) → 정책(`policies.py`) → 입력 가드(`controller.py`), Windows 데스크톱(`desktop.py`) |
| `src/uga/agents/reverse/` | 샘플을 실행하지 않는 정적 분석, JADX/Ghidra/REA 어댑터 |
| `src/uga/agents/builder/` | GameSpec → Godot 템플릿 생성, 후보 수정(`revision.py`), Godot 검증 파이프라인 |
| `src/uga/evaluation/` | 고정 시드 벤치마크, 비교·승인·롤백(`experiments.py`) |
| `src/uga/memory/store.py` | SQLite(WAL) 작업·이벤트·체크포인트와 SHA-256 아티팩트 저장소 |
| `src/uga/supervisor/` | heartbeat/RSS 감시, 서비스 시작·중지, 장시간 soak |
| `src/uga/api.py`, `dashboard/` | 로컬 REST v1(토큰 필요)과 대시보드 |
| `src/uga/integrations/` | 외부 도구 실행(`process.py`), 로컬 MCP stdio(`mcp.py`), 에이전트 레지스트리 |
| `src/uga/cli.py` | `uga` 명령 진입점 |
| `test_games/`, `benchmarks/`, `configs/` | 자체 테스트 게임, 고정 시드, 입력 매핑 |
| `schemas/` | `uga schemas`로 생성한 JSON Schema(커밋됨) |
| `docs/` | 설계·운영·검증 기록. `docs/validation/*.json`은 실행 당시의 증거 |
| `.uga/` | 실행 상태·도구·토큰·산출물. **Git 제외**, 복원되지 않는다고 가정 |

## 반드시 지킬 규칙

1. **허가된 대상만 다룹니다.** 자동 입력과 분석은 `test_games/`의 자체 게임과 사용자가 명시적으로
   허가한 대상에만 씁니다. CAPTCHA 해결, 안티치트 우회, 게임 프로세스 메모리 읽기·쓰기는
   구현하지 않습니다.
2. **외부 실행 파일은 승인 후에만 실행합니다.** Godot/JADX/Ghidra/REA는 승인 플래그
   (`--allow-external-tools`, `TaskSpec.authorized`, pytest의 `--allow-godot`/`--allow-analyzers`)가
   있을 때만 `integrations/process.py`의 `run_tool`(절대 경로, `shell=False`, 시간·출력·RSS 제한)로
   실행합니다. 비신뢰 바이너리는 실행하지 않습니다.
3. **도구와 모델 가중치를 묵시적으로 내려받지 않습니다.** Laya/VLM 등은 호출자가 명시적으로
   주입하며 설치·라이선스·무결성 확인이 먼저입니다.
4. **검증을 부풀리지 않습니다.** 실제로 실행한 것만 "검증"이라고 기록합니다. 실행하지 못한 것은
   "미검증"으로 남기고, 환경이 달라 재현하지 못한 수치를 옮겨 적지 않습니다. 하트비트나 PID만으로
   장시간 검사를 통과 처리하지 않습니다.
5. **테스트를 건너뛰거나 끄지 않습니다.** 실패는 원인을 고칩니다. CI를 다시 돌리려고 빈 커밋을
   만들지 않습니다.
6. **비밀을 남기지 않습니다.** `.uga/api-token`을 커밋하거나 로그·이슈에 붙여 넣지 않습니다.

## 코드 규칙

- Python ≥ 3.11(`.python-version`은 3.11), Ruff `line-length = 100`, 규칙 `E,F,I,UP,B`.
  주변 코드의 주석 밀도와 이름 규칙을 따릅니다.
- 선(wire) 데이터는 `uga.core.contracts.Contract`를 상속합니다(`extra="forbid"`,
  `schema_version`). **호환되지 않는 변경은 버전을 올리고** `uga schemas`로 `schemas/`를 다시
  만들어 함께 커밋합니다(현재 일치하는지 검사하는 테스트는 없습니다).
- 모르는 값은 `None`이고 `Detection`의 신뢰도는 0입니다. 값을 지어내지 않습니다.
- 예상 가능한 실패는 `UGAError` 하위(`AuthorizationRequired`, `CapabilityUnavailable`,
  `SafetyStop`)로 올립니다. API가 각각 403/400으로 변환합니다.
- 새 작업 종류를 추가하려면 `orchestrator/worker.py`의 `validate_task` 계약 표와
  `execute_task`, `integrations/registry.py`, 테스트를 함께 고칩니다. API로는 등록된 작업만 실행하며
  임의 코드를 받지 않습니다.
- 새 의존성은 `pyproject.toml`에 추가하고 `uv lock`으로 `uv.lock`을 갱신합니다. CI는
  `uv sync --frozen`을 씁니다.
- 파일은 `memory.store.atomic_json`처럼 원자적으로 씁니다. 출력 디렉터리는 새 경로를 받으며 기존
  프로젝트를 덮어쓰지 않습니다.
- 오케스트레이터는 `spawn` 프로세스로 작업을 격리합니다. 워커 코드는 모듈 최상위에서 부수 효과를
  내지 않아야 합니다(Windows spawn 호환).

## 테스트 지침

- `tests/`는 기본적으로 외부 도구 없이 CPU만으로 통과해야 합니다. 외부 도구가 필요한 테스트는
  `--allow-godot`/`--allow-analyzers` 뒤에 둡니다(`tests/conftest.py`).
- 오케스트레이터·서비스·API 테스트는 실제 프로세스를 띄우므로 수십 초 걸립니다.
- 시간·프로세스·파일 시스템에 의존하는 버그는 수정 전에 재현 테스트를 먼저 만들고, 간헐 실패는
  여러 번 반복해 확인합니다.
- 알려진 경고: Starlette `TestClient`의 httpx deprecation 경고 1개(실패 아님).

## 문서·Git 규칙

- 동작이 바뀌면 [docs/phase-status.md](docs/phase-status.md)와 관련 문서를 같은 변경에서 갱신합니다.
  `docs/validation/*.json`은 실행 당시 증거이므로 손으로 고치지 않습니다. 새로 실행한 결과를
  새로 기록합니다.
- 기본값: 작업 브랜치에 커밋·푸시합니다. `main` 반영이나 PR 생성은 소유자(`jhy0285`)가 요청할 때만
  합니다. CI(Windows/Linux × Python 3.11/3.12)가 모두 통과해야 완료입니다.
- 커밋 메시지는 `fix(api): ...`, `feat(player): ...`, `docs: ...` 형식을 따릅니다.
- 문서 본문은 한국어, 코드·식별자·명령은 영어입니다.

## 알려진 함정

- `uga service start` 후 토큰은 매번 새로 만들어집니다. 대시보드는 출력된 `dashboard_url`로 엽니다.
- 같은 상태 디렉터리에는 오케스트레이터가 하나만 뜰 수 있습니다(파일 락). 테스트는 `tmp_path`를 씁니다.
- 16시간 soak는 **미완료**입니다. 이어서 돌리려면 새 출력 경로로 시작하고 기존 실행을 재시작하거나
  합산하지 않습니다([운영 문서](docs/operations.md)).
- Windows 실제 SendInput/MSS 입력은 **미검증**입니다. 사용자 PC에서만 확인할 수 있습니다
  ([Windows 가이드](docs/windows-testing.md)).
- Godot/JADX/Ghidra가 없는 환경에서는 `uga doctor`가 해당 항목을 `null`로 표시하는 것이 정상입니다.
