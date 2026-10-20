# 단계별 구현 및 검증 현황

검증 머신: **Linux / Python 3.12.14 / CPU**. 목표인 Windows 11 / Python 3.11 런타임은
실행하지 않았습니다. Python 3.11 문법 파싱과 Windows/Linux × Python 3.11/3.12 CI 정의는
준비했지만 실제 해당 런타임의 성공 증거로 간주하지 않습니다. 코드 검증 기준 커밋은
`7d010d1`입니다. 자세한 수치는 [validation/results.json](validation/results.json)에 있습니다.

| PHASE | 상태 | 실제 구현·검증 | 남은 범위 |
|---|---|---|---|
| 0 Repository & Architecture | **완료: 기반 구현** | 빈 저장소 분석, 설치 가능한 패키지, frozen lock, 7개 공통 계약, CLI/API, 아키텍처·ADR·CI, 첫 커밋 | 목표 Windows/3.11 런타임 및 원격 CI는 미실행 |
| 1 Local Test Game | **부분 완료** | 이동·충돌·적·HP·아이템·인증 정지·정답 상태가 있는 CPU 참조 게임, 원본 Godot 프로젝트와 smoke script 생성 | 실제 Godot 엔진 실행 승인 대기; Godot 테스트 통과로 표시하지 않음 |
| 2 Player MVP | **부분 완료** | 픽셀 캡처→상태 인식→규칙/A*→행동→효과 확인; 5개 고정 시드 모두 성공; 키/마우스/긴급 정지/포커스/시간 제한 검사 | MSS/SendInput 실제 Windows 화면·입력 미검증, 일반 게임 인식 미구현 |
| 3 Laya / VLM | **부분 완료** | 공식 Laya/배포 메타데이터·API 조사; Laya/VLM/LLM/Fallback 인터페이스, 별도 전략 프로세스와 fast 제어 분리 검증 | 가중치 라이선스·무결성·실제 추론·OCR/VLM 및 모델 비교 미실행 |
| 4 Supervisor | **부분 완료** | heartbeat, watchdog, PID 식별, 마감·RSS 제한, 1회 복구, 취소, SQLite/게임 체크포인트, 원자 저장, 로그 회전, 중단 진단 테스트 | 실제 PC 게임/모델의 12~16시간 운영 미검증 |
| 5 Reverse Agent | **부분 완료** | 권한 확인 후 소스/APK 자체 fixture 정적 분석, 출처/해시/클래스/함수/리소스/선언된 GameSpec 보존; 아카이브 제한 검사 | JADX/Ghidra/REA 설치·실호출·네이티브 역분석 미실행; 일반 게임 메커니즘 추론 미구현 |
| 6 Builder Agent | **부분 완료** | 제한된 요구사항/선언 GameSpec→원본 Godot 아레나, 기존 출력 보호, 실제 엔진 import/smoke/play/export 어댑터 | 엔진 빌드·내보내기 미실행, 일반 자연어 코드 생성·기존 프로젝트 수정·자동 오류 수정 및 Unity 미구현 |
| 7 Integrated Workflow | **부분 완료** | Builder→Reverse→CPU Player, Reverse→Builder→CPU Player, REST에서 GameSpec 전달/2-enemy 설정 보존, 작업/아티팩트 조회 | 생성 Godot 게임의 실제 엔진 플레이는 승인 대기; Windows 화면 기반 통합 미실행 |
| 8 Self-Improvement | **부분 완료** | 고정 조건·harness 해시 비교, 경로 거리 후보, 불변 결과 증거, 명시적 승인·원자 적용·회귀 시 롤백 테스트; 실제 후보 측정 | 임의 코드/모델 개선·배포 미구현; 현재 후보는 **제안 상태**, 적용 승인하지 않음 |
| 9 Long-run & Dashboard | **부분 완료** | 로컬 대시보드/REST 실제 HTTP 검사, 프로세스 재시작·반복 시작, CPU 참조 30분·최종 코드 60초 검증 | 2/4/8/16시간, 실제 게임 장시간 운영, GPU/VRAM·브라우저 렌더링 미검증 |

## 실제 실행한 명령과 결과

모든 명령의 작업 디렉터리는 저장소 루트입니다. 결과 파일은 이번 실행에 속하는 것을
확인했고 테스트의 종료 코드 0을 확인했습니다.

```sh
bash scripts/setup-cloud.sh   # 연속 2회 성공, frozen install
.venv/bin/ruff check .
.venv/bin/ruff format --check .
uv lock --check --python 3.12 --no-python-downloads
.venv/bin/python -m pytest --junitxml=.uga/validation/tests.xml --cov=uga --cov-report=json:.uga/validation/coverage.json
.venv/bin/uga player --seed 7 --output .uga/validation/player
.venv/bin/uga benchmark --output .uga/validation/benchmark
.venv/bin/uga improve --output .uga/validation/final-improvement
.venv/bin/uga service start   # 두 번째 호출은 같은 PID 재사용
.venv/bin/python scripts/smoke-http.py
.venv/bin/uga service stop
.venv/bin/uga service start
.venv/bin/python scripts/smoke-http.py
uv build --python 3.12 --no-python-downloads
```

최종 pytest: **57 passed / 0 failed / 0 errors / 0 skipped / 0 xfailed**, 12.67초.
라인 커버리지: 73%(플랫폼/외부 도구와 일부 자식 프로세스 경로는 포함 범위가 제한됨).
경고 1개: Starlette TestClient의 httpx 사용에 대한 deprecation; 테스트 실패가 아닙니다.
JavaScript는 Node v24.19.0의 `node --check`를 통과했습니다. 실제 브라우저 렌더링은 검사하지 않았습니다.
원격 CI는 실행하지 않았고 Godot/모델/외부 분석 검사는 이 57개에 포함되지 않습니다.

API 실제 네트워크 검사에서 health=ok, 생성→분석→CPU 참조 플레이 성공과 14개 아티팩트를
확인했습니다. 재시작 전·후 실제 Player 작업은 모두 seed 7, 48단계로 목표를 달성했습니다.
단순 PID/포트가 아닌 기능 요청으로 검증했습니다. wheel은 별도 가상환경에 설치하고 package
resource(대시보드·Godot 템플릿·Ghidra script)와 Builder 실행을 검사합니다.

## 고정 조건 개선 실험

seeds = `[7,11,19,23,31]`, 160×112 CPU 픽셀 참조 게임, 적 3개, 장애물 켬, 속도 4,
공격 거리 14를 그대로 유지했습니다. 목표 선택만 직선 거리→장애물 경로 거리로 바꿨습니다.

| 지표 | 기본 정책 | 후보 정책 |
|---|---:|---:|
| 목표 달성률 | 100% (5/5) | 100% (5/5) |
| fixture 인식 정확도 | 100% | 100% |
| 평균 행동 수 | 49.0 | 48.0 |
| E2E P50 | 5.95ms | 6.09ms |
| E2E P95 | 8.72ms | 9.30ms |
| E2E P99 | 10.26ms | 10.27ms |
| 프로세스 RSS | 32.38MB | 32.88MB |

행동 수는 약 2.04% 줄었고 P95 지연은 약 6.65% 늘었습니다. 25% 지연 허용 범위의
현재 gate에는 적합하지만, 5개 시드만으로 일반 성능 개선이나 통계적 유의성을 주장하지 않습니다.
현재 실험 ID: `838ce3a2-04c4-4710-a595-28060df9ba5b`. 상태는 proposed입니다.
이전의 공격 범위 8→14 실험은 파라미터 비교 데모이며 최종 기본 정책 개선 실험과 구분합니다.

## 장시간 실행 증거

| 실행 | 실제 시간 | 에피소드 | 실패 | 워밍업 후 RSS 변화 |
|---|---:|---:|---:|---:|
| CPU 참조 기준선(핵심 코드 d3f21a8) | 1800.286초 | 6,326 | 0 | +0.535MB |
| 최종 코드 회귀 실행 | 60.264초 | 195 | 0 | +0.043MB |

30분 실행은 이후 체크포인트·효과 검증·입력 안전장치 보완 전의 기준선입니다. 최종 코드의
30분 테스트로 표현하지 않습니다. 최종 소스는 57개 테스트와 별도 60초 반복 검증을 통과했습니다.
먼저 실행한 세션은 재연결 시 약 21분에서 종료되어 완료 리포트가 없습니다. 그 기록은
중단으로 남기고 새 30분 실행의 `summary.json`만 통과 근거로 사용했습니다.
2/4/8/16시간 결과는 **미실행**입니다. 가속 시간을 실제 경과 시간으로 계산하지 않았습니다.

## 남은 외부 조건

Godot 실행은 요청문 11.9에 따른 명시적 승인 질문이 대기 중입니다. Laya 모델 카드 요청은
현재 `huggingface.co`에서 proxy 403이 발생했고, 추가 도메인을 환경 설정 초안에 저장했습니다.
체크포인트 라이선스/무결성·실추론, Windows desktop과 외부 분석 도구는 별도 검증이 필요합니다.
설치·시작 설정은 저장됐지만 **환경 게시와 새 작업 복원은 수행·검증하지 않았습니다**.
환경 설정에서 변경을 검토·저장한 뒤 게시해야 합니다. 구현은 단계별 로컬 Git 커밋에 있습니다.
