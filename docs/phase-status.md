# 단계별 구현 및 검증 현황

검증 머신: **Linux / Python 3.11.17·3.12.14 / CPU / Godot 4.6.3**.
2026-10-21 검증에서 두 Python 런타임 모두 **77개 테스트, 실패·오류·건너뜀 0개**입니다.
코드 검증 기준 커밋은 `2325340`입니다. Windows 11 런타임과 원격 CI는 미실행입니다.
수치는 [전체 결과](validation/results.json), [엔진](validation/godot.json),
[분석 도구](validation/reverse.json), [실제 화면](validation/screen.json)에 있습니다.

| PHASE | 상태 | 실제 구현·검증 | 남은 범위 |
|---|---|---|---|
| 0 Repository & Architecture | **완료: 기반 구현** | 설치 가능한 패키지, frozen lock, 7개 공통 계약, CLI/API, ADR·CI, Linux Python 3.11/3.12 실제 테스트 | Windows 런타임·원격 CI 미실행 |
| 1 Local Test Game | **완료: 자체 아레나** | Godot 실제 import, 이동·벽·HP/아이템·인증 정지·전투/목표 6개 검사, 5개 시드 플레이 | Windows 창에서의 검증은 별도 |
| 2 Player MVP | **완료: 자체 Linux 아레나 범위** | 실제 Godot 창 MSS 캡처→픽셀 인식→규칙/A*→자체 입력 브리지→효과 확인; 5개 시드 성공; 인식 정확도 100% | 실제 Windows MSS/SendInput, 일반 게임 인식 미검증 |
| 3 Laya / VLM | **부분 완료** | 공식 API·메타데이터 조사, 정책 인터페이스, 별도 전략 프로세스와 fast 제어 분리 | 가중치 라이선스·무결성·실추론, OCR/VLM 및 모델 비교 미실행 |
| 4 Supervisor | **부분 완료** | heartbeat, PID 식별, timeout·RSS 제한, 제한 복구, checkpoint, 로그 회전, 백그라운드 soak 관리·실제 시간 milestone | CPU 16시간 검사 진행 중; 실제 PC 게임/모델 12~16시간 운영 미검증 |
| 5 Reverse Agent | **완료: 자체 정적 분석 fixture 범위** | 실제 JADX class/DEX-APK, Ghidra ELF 함수·호출, REA discovery·읽기 전용 ELF 분석; CLI·REST·UI, provenance·GameSpec 정규화 | 일반 게임 메커니즘 추론·Windows 도구 실행 미검증; REA 전체 도구 검증 아님 |
| 6 Builder Agent | **부분 완료** | Godot 생성·실제 import/smoke/play, Linux export·실행, Windows 교차 export, 해시 기반 후보 수정·확인한 오류 자동 복구 | 임의 자연어 게임 생성·일반 오류 수정·Unity 미구현; Windows 실행 미검증 |
| 7 Integrated Workflow | **완료: 지원하는 아레나 범위** | Builder→Reverse→Godot Player, Reverse→Builder→Godot Player, CLI·HTTP에서 2-enemy GameSpec 보존·아티팩트 해시 검증 | 임의 바이너리 메커니즘 복원·Windows 화면 통합 미검증 |
| 8 Self-Improvement | **부분 완료** | 고정 조건·harness 해시 비교, 경로 거리 후보, 불변 증거, 명시적 승인·원자 적용·회귀 롤백 테스트, 실제 후보 측정 | 임의 코드/모델 개선 미구현; 현재 후보는 **제안 상태**, 미적용 |
| 9 Long-run & Dashboard | **부분 완료** | Chromium에서 세 에이전트 제출·완료·미리보기, 실제 HTTP·서비스 재시작, 공식 MCP SDK, 같은 CPU 연속 실행의 30분·2/4/8시간 통과 | 16시간 검사 진행 중; GPU/VRAM·실제 PC 게임/모델 장시간 운영 미검증 |

## 실제 실행과 재현

외부 도구는 사용자가 승인한 자체 프로젝트와 fixture에 한해 실행했습니다. 다음 명령은
저장소 루트 기준이며, 재실행할 때 결과 경로는 새 경로로 지정해야 합니다.

```sh
bash scripts/setup-cloud.sh   # 연속 2회 성공, frozen install
.venv/bin/ruff check .
.venv/bin/ruff format --check .
uv lock --check --python 3.12 --no-python-downloads
.venv/bin/python -m pytest --allow-godot --allow-analyzers --junitxml=.uga/validation/current-python312-tests.xml --cov=uga --cov-report=json:.uga/validation/current-python312-coverage.json
.uga/python311-venv/bin/python -m pytest --allow-godot --allow-analyzers --junitxml=.uga/validation/current-python311-tests.xml
.venv/bin/python scripts/validate-godot.py --allow-external-tools --export --output .uga/validation/engine-release-final
.venv/bin/python scripts/validate-godot-screen.py --allow-external-tools --xvfb .uga/tools/xvfb/usr/bin/Xvfb --output .uga/validation/godot-screen-final
.venv/bin/python scripts/smoke-engine-http.py --allow-external-tools --output .uga/validation/live-engine-http.json
.venv/bin/python scripts/smoke-analysis-http.py --allow-external-tools --input-dir .uga/validation/reverse-real/inputs --output .uga/validation/analysis-http.json
.uga/mcp-client-venv/bin/python scripts/validate-mcp-sdk.py --python .venv/bin/python --output .uga/validation/mcp-sdk
.venv/bin/uga service start
.venv/bin/python scripts/smoke-http.py
uv build --python 3.12 --no-python-downloads
```

최종 JUnit: Python 3.11.17에서 **77 passed / 63.556초**, Python 3.12.14에서
**77 passed / 68.095초**. 완결된 XML의 testcase도 각각 77개이며 실패·오류·건너뜀은 없습니다.
환경 재연결로 두 shell 세션의 종료 코드 핸들은 소실되어, 완료된 XML을 근거로 기록했습니다.
실제 Godot 검사 5개와 JADX/Ghidra 검사 2개를 포함합니다. 기본 pytest는 외부 도구 검사
7개를 건너뜁니다. 라인 커버리지는 **75.53%**이며 자식 프로세스·플랫폼 경로는 측정 범위가
제한됩니다. Starlette TestClient의 httpx deprecation 경고 1개는 테스트 실패가 아닙니다.

Ruff lint·format, frozen lock, Node 24.19.0의 JavaScript 문법 검사를 통과했습니다.
실제 Chromium에서도 Player, Builder의 Godot 검사, Reverse의 JADX 작업을 제출·완료했고,
160×112 미리보기와 데스크톱/모바일 화면을 확인했습니다. uncaught JavaScript 오류는 0개입니다.
REA와 공식 MCP SDK 검증은 별도 실행입니다. 원격 CI·실모델 검사는 미실행입니다.

HTTP에서 생성→분석→Godot 플레이와 아티팩트 **21개**, JADX/Ghidra 작업과 각각 **5개·3개**의
크기·SHA-256을 확인했습니다. 서비스 시작 재사용·정지·재시작도 검사했습니다. wheel은 frozen
production 의존성을 설치한 별도 가상환경에서 저장소 밖의 `python -I`로 불러와 실제 Godot
워크플로우와 패키지 리소스를 확인했습니다. 공식 MCP SDK **2.3.0**은 로컬 stdio
initialize/discovery/Player/cancel을 완료했습니다. 다른 AI 시스템에는 연결하지 않았습니다.

[엔진 검증](engine-validation.md)·[Builder 후보 수정](builder-revisions.md)·
[실제 화면 검증](screen-validation.md)·[Reverse 검증](reverse-validation.md)에 재현 지침이 있습니다.
Godot 정답 브리지와 MSS 픽셀 정책은 별도 backend입니다. 픽셀 모드의 입력은 자체 파일
브리지이며 Windows SendInput은 미검증입니다. APK fixture는 정적 분석용이고 설치 가능한
Android 앱이 아닙니다. 분석 대상 네이티브 파일을 호스트 프로세스로 실행하지 않았습니다.

## 고정 조건 개선 실험

seeds = `[7,11,19,23,31]`, 160×112 CPU 픽셀 참조 게임, 적 3개, 장애물 켬, 속도 4,
공격 거리 14를 유지하고 목표 선택만 직선 거리에서 장애물 경로 거리로 바꿨습니다.

| 지표 | 기본 정책 | 후보 정책 |
|---|---:|---:|
| 목표 달성률 | 100% (5/5) | 100% (5/5) |
| fixture 인식 정확도 | 100% | 100% |
| 평균 행동 수 | 49.0 | 48.0 |
| E2E P50 | 5.95ms | 6.09ms |
| E2E P95 | 8.72ms | 9.30ms |
| E2E P99 | 10.26ms | 10.27ms |
| 프로세스 RSS | 32.38MB | 32.88MB |

행동 수는 약 2.04% 줄었고 P95는 약 6.65% 늘었습니다. 현재 25% 지연 gate에는 적합하지만,
5개 시드만으로 일반 성능 개선이나 통계적 유의성을 주장하지 않습니다. 실험 ID는
`838ce3a2-04c4-4710-a595-28060df9ba5b`, 상태는 **proposed, 미적용**입니다.
초기 공격 범위 8→14 비교 데모는 이 고정 조건 실험과 구분합니다.

## 장시간 실행 증거

| 실행 | 실제 시간 | 에피소드 | 실패 | 워밍업 후 RSS 변화 |
|---|---:|---:|---:|---:|
| CPU 기준선(핵심 코드 d3f21a8) | 1800.286초 | 6,326 | 0 | +0.535MB |
| Player 핵심 회귀 실행 | 60.264초 | 195 | 0 | +0.043MB |
| 연속 실행 30분 구간 | 1800.287초 | 5,727 | 0 | +0.570MB |
| 같은 실행 2시간 구간 | 7200.202초 | 24,899 | 0 | +0.582MB |
| 같은 실행 4시간 구간 | 14400.191초 | 51,144 | 0 | +1.242MB |
| 같은 실행 8시간 구간 | 28800.248초 | 103,636 | 0 | +1.242MB |

초기 30분 기준선은 이후 안전장치 보완 전의 코드입니다. 중단되어 완료 리포트가 없는
이전 실행은 통과에 포함하지 않습니다. 현재 연속 검사는 `0c62575` 소스에서 시작했고,
후속 분석 도구·화면 검증 작업에서 참조 Player 핵심 코드는 변경하지 않았습니다.
30분·2/4/8시간 기록은 **하나의 연속 실행을 누적 측정한 구간**이며 독립 반복 실험이 아닙니다.
8시간 peak RSS는 35.109MB였습니다. 16시간 전체 완료 결과는 아직 없으며 실행을 유지합니다.
시작은 2026-10-21 00:53:33 KST, 목표 종료는 같은 날 약 16:53:33 KST입니다.

```sh
.venv/bin/uga soak-service status --output .uga/validation/continuous-16h
```

`results/run.json`의 run ID·소스 해시, heartbeat, milestone, 최종 summary를 함께 확인합니다.
heartbeat나 PID만으로 전체 통과를 판정하지 않습니다. 이번 환경 재연결 후 같은 실행이
지속됨을 확인했지만 새 머신에서 복원을 검증한 것은 아닙니다.

## 남은 외부 조건

Godot와 추가 JADX/Ghidra/REA·Chromium/Xvfb는 실행 범위를 안내한 뒤 받은 사용자의
계속 진행 지시에 따라 실행했습니다. 대상은 자체 프로젝트와 fixture로 제한했습니다.
Laya 모델 카드 목적지 `huggingface.co`는 proxy 403으로 차단됐고 허용 도메인을 초안에
저장했습니다. 현재 런타임에는 custom 도메인이 반영되지 않았고 정책 적용 상태도 unknown입니다.
체크포인트 라이선스·무결성·실추론, 일반 OCR/VLM, Windows desktop, GPU/VRAM은 미검증입니다.

설치·시작 설정의 저장, 환경 게시, 새 작업 복원은 별도 절차입니다. 환경 게시와 새 작업
복원은 이번 구현 검증 범위에 포함하지 않았습니다.
소스와 커밋 기록은 [GitHub main](https://github.com/jhy0285/Universal-Game-Agent/tree/main)에
반영했습니다. 로컬 PC에서는 README의 clone·설치 절차로 소스를 받을 수 있습니다.
무시된 `.uga`의 도구·모델·로그·검증 원본 및 현재 실행 중인 프로세스는 clone에 포함되지 않습니다.
JSON의 `recorded_at`은 각 검증 당시의 상태이며 이후 GitHub 반영과 클라우드 설정 변경을 소급하지 않습니다.
