# 다음 작업 (인수인계)

작성: 2026-10-29. 기준 커밋 `dc7cc51`(브랜치 `claude/eager-newton-rt8mr1`). 이 문서는 **무엇이 남았고,
무엇이 끝나면 완료인지**를 정리합니다. 구현된 범위와 검증 결과의 기준은
[phase-status.md](phase-status.md), 작업 규칙은 [AGENTS.md](../AGENTS.md)입니다.

각 항목의 표시: **[바로 가능]** 외부 도구 없이 클라우드에서 할 수 있음 ·
**[도구/네트워크]** 외부 도구나 모델 다운로드 허용이 필요함 · **[소유자 PC]** 사용자의 Windows PC에서만
검증할 수 있음. 아래 수치와 동작은 2026-10-28~29에 Linux Python 3.13.17에서 직접 실행해 확인했습니다.

## 현재 상태 한눈에

- 린트·포맷 통과, 기본 pytest **89 passed / 7 skipped**(건너뛴 7개는 Godot/JADX/Ghidra 필요),
  라인 커버리지 73%. 최신 푸시 커밋의 GitHub CI는 Windows/Linux × Python 3.11/3.12 네 조합
  모두 통과했습니다([실행 기록](https://github.com/jhy0285/Universal-Game-Agent/actions/runs/40613342587)).
- 이번 세션의 Godot/JADX/Ghidra 외부 도구 테스트는 이 환경에 도구가 없어 **다시 실행하지 못했습니다.**
  해당 결과는 [validation/](validation/)의 이전 기록 그대로입니다.
- 검증되지 않은 것: Windows 실제 SendInput/MSS, Laya/VLM 실추론, GPU/VRAM, 16시간 soak 완료,
  임의 게임 인식·분석·생성, Unity.

## 우선순위 작업

### 1. 오케스트레이터 모니터 스레드 장애 처리 **[바로 가능]** — 신뢰성 버그

**문제.** `Orchestrator._monitor`(`src/uga/orchestrator/jobs.py`)는 `_tick`에서 예외가 나면
`monitor-error` 체크포인트를 쓰고 `_stop`을 세운 뒤 스레드가 끝납니다. 재시작이나 정리가 없습니다.
2026-10-29에 `_tick`에 예외를 주입해 재현했습니다.

- 실행 중이던 작업은 DB에서 **`running`으로 남고** 워커 프로세스도 살아 있습니다.
- 마감 시각·heartbeat·RSS 감시가 모두 멈춰 작업이 끝나지 않을 수 있습니다.
- 새 작업은 `UGAError: orchestrator is closed`로 거부됩니다. `/health`는 `degraded`만 알려줍니다.
- 서버를 다시 시작해야 `running` 레코드가 `failed`로 정리됩니다.

**완료 기준.** 모니터 장애 시 (a) 실행 중 워커를 종료하고 작업을 원인과 함께 `failed`로 기록하거나
모니터를 안전하게 재시작하며, (b) 그 동작을 `_tick` 예외 주입 테스트로 고정하고,
(c) `/health`와 대시보드가 원인을 보여 줍니다. 수정 전에 재현 테스트를 먼저 만듭니다.

### 2. 기본 테스트 커버리지 보강 **[바로 가능]**

외부 도구 없이 채울 수 있는 공백입니다(`pytest --cov=uga --cov-report=term-missing`로 확인).

| 모듈 | 현재 | 비고 |
|---|---:|---|
| `supervisor/service.py` | 0% | `ServiceManager`의 소유권 확인·상태·중지·포트 검증. 지금은 `scripts/smoke-http.py`로만 확인 |
| `orchestrator/worker.py` | 42% | `execute_task`의 builder/reverse/workflow 분기, `analysis_path` 경로 제한 |
| `cli.py` | 56% | 하위 명령 인자 검증과 오류 코드 |
| `agents/builder/godot.py`, `pipeline.py` | 19~23% | 외부 Godot 필요 부분은 가짜 `run_tool`로 분기만 검증 |

**완료 기준.** 전체 커버리지 ≥ 80%, 새 skip 없음, 느린 테스트(수 초 이상)는 최소화.

### 3. 계약 스키마 드리프트 테스트 **[바로 가능]** — 작음

`schemas/*.schema.json`은 `uga schemas`로 만든 커밋 산출물입니다. 지금은 모델과 일치하지만(2026-10-29
`diff -r`로 확인) 이를 강제하는 테스트가 없습니다. 생성 결과와 커밋된 파일을 비교하는 테스트를
추가하고, 불일치 시 `uga schemas`를 실행하라는 메시지를 냅니다.

### 4. CI에 포맷 검사 추가 **[바로 가능]** — 작음

`.github/workflows/ci.yml`은 `ruff check`만 실행하고 `ruff format --check`는 실행하지 않습니다.
저장소는 현재 포맷 검사를 통과하므로(새 클론에서 Python 3.11.17로 확인) 단계를 추가하면 됩니다. 추가 후 CI 네 조합이
통과하는지 확인하세요.

### 5. 인식 계층 일반화 **[바로 가능]** (설계 필요)

`agents/player/perception.py`의 `PixelPerception`은 정확히 일치하는 RGB 값과 좌상단 서명
픽셀(`test_game.SIGNATURE`)에만 반응합니다. 다른 게임에는 쓸 수 없습니다. 또 `components()`는 파이썬
BFS이고 컴포넌트마다 `min(remaining)`을 호출해 프레임이 커지면 느려집니다.

- 프로파일을 교체할 수 있는 인터페이스로 분리하고, 두 번째(합성) 게임 프로파일을 같은 계약
  (`GameState`, 신뢰도, `null`)으로 통과시킵니다. 알 수 없는 화면은 계속 안전 정지여야 합니다.
- 큰 프레임(예: 640×448)에서 지연을 측정하고 필요하면 `numpy`/`scipy.ndimage` 등을 의존성에 추가합니다
  (`uv lock` 포함, [AGENTS.md](../AGENTS.md) 참조).
- **완료 기준.** 기존 5개 시드 벤치마크의 성공률·인식 정확도 100%를 유지하고, 새 프로파일 테스트와
  지연 측정이 [phase-status.md](phase-status.md)에 기록됩니다. 임의 게임 인식을 주장하지 않습니다.

### 6. Windows 실제 GUI 검증 **[소유자 PC]**

[windows-testing.md](windows-testing.md)의 순서(`doctor` → pytest → `service` → Godot →
`desktop-check` → `desktop-play`)를 사용자 PC에서 실행합니다. 최근 SendInput에 scan code를 추가했지만
실제 Windows에서는 확인한 적이 없습니다.

**완료 기준.** 실행 결과(`desktop-check`의 `ready_for_input`, `desktop-play`의 성공 여부와 입력 반영률)를
새 JSON 기록으로 `docs/validation/`에 남기고 phase-status를 갱신합니다. AI는 이 결과를 추측하지 않고
사용자가 제공한 출력만 기록합니다.

### 7. 실제 모델 정책 비교 (Laya/LLM) **[도구/네트워크]**

`LayaPolicy`·`LLMPolicy`는 주입형 틀만 있고 실추론은 한 번도 하지 않았습니다. 모델 카드 도메인
`huggingface.co`가 이전 환경에서 proxy 403으로 막혔습니다([cloud-environment.md](cloud-environment.md)).
허용 도메인, 체크포인트 라이선스, 무결성(해시)을 먼저 확인하고, 같은 CPU에서 `RuleBasedPolicy`와
성공률·지연·메모리를 같은 시드로 비교합니다. Laya는 텍스트 상태 결정 모델이며 이미지 입력이 아닙니다.
upstream의 속도·정확도 수치를 UGA 측정치로 옮겨 적지 않습니다.

### 8. 16시간 soak 재실행 **[도구/네트워크]** (장시간 가동 머신)

이전 실행은 약 10시간 16분에서 중단되어 미완료입니다. 새 출력 경로로 시작합니다.

```sh
.venv/bin/uga soak-service start --seconds 57600 --output .uga/long-run-new
.venv/bin/uga soak-service status --output .uga/long-run-new
```

완료는 16시간 경과와 최종 `summary.json`이 있을 때만 인정합니다. 중단된 실행을 재시작하거나 시간을
합산하지 않습니다([operations.md](operations.md)).

## 더 큰 후속 과제 (설계 먼저)

- **Reverse 심화.** 현재는 정규식 기반 구조 추출(`semantic_resolution: false`)이고 JADX/Ghidra는
  자체 fixture에서만 검증했습니다. 도구 결과에서 메커니즘 후보를 `hypothesis`로 정리하되, 근거 없으면
  `unknown`을 유지합니다.
- **Builder 다양화.** `generate()`는 HP 100·속도 4와 `top_down_arena`만 허용합니다. 템플릿 변형이나
  파라미터 확장 시 Godot 검증(`validate-godot.py`)과 함께 늘립니다. Unity는 경계 파일(`unity.py`)만
  있습니다.
- **자기개선 통계.** 현재 개선 후보는 5개 시드의 단일 실험이며 제안 상태·미적용입니다. 일반화를
  주장하려면 시드 수와 반복을 늘리고 같은 조건 비교(`evaluation/experiments.py`)를 거칩니다.

## 작업 후 체크리스트

1. `ruff check .` · `ruff format --check .` · `pytest -q` 통과.
2. 동작이 바뀌면 [phase-status.md](phase-status.md)와 관련 문서를 갱신하고, **실제로 실행한 것만** 적습니다.
3. 작업 브랜치에 푸시하고 CI(네 조합) 결과를 확인합니다.
4. 이 문서에서 끝낸 항목을 지우거나 완료 기록으로 옮깁니다.
