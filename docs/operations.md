# 운영 및 재현

작업 디렉터리는 저장소 루트입니다. 클라우드 작업은 이미 격리되어 있으므로 기존 체크아웃을
사용하고 별도 Git worktree를 만들지 않습니다. Python 도구 실행은 `.venv/bin/`(Linux) 또는
`.venv\Scripts\`(Windows) 아래의 실행 파일을 사용합니다.

```sh
bash scripts/setup-cloud.sh
bash scripts/validate.sh
.venv/bin/uga service start
.venv/bin/python scripts/smoke-http.py
.venv/bin/uga service status
.venv/bin/uga service stop
```

설치는 frozen lock을 사용하며 인터프리터를 자동 다운로드하지 않습니다. 현재 클라우드에서
설치 스크립트를 연속 두 번 실행했습니다. 서비스 시작을 두 번 호출하면 같은 소유 프로세스를
재사용합니다. 메타데이터의 PID와 생성 시각, 명령과 작업 디렉터리를 확인한 뒤 종료합니다.
다른 프로세스를 종료하지 않습니다. 프로세스는 환경 스냅샷에 유지된다고 가정하지 않습니다.

`.uga/uga.sqlite3`는 작업·이벤트·체크포인트·개선 제안을 저장합니다. SQLite WAL과 트랜잭션을
사용합니다. `.uga/artifacts/`의 파일은 SHA-256으로 검증합니다. `.uga/jobs/<id>/`에 작업별
화면, 로그, JSON 결과와 생성 프로젝트가 보존됩니다. `.uga/server.log`에서 서버 오류를 확인합니다.
비밀 값은 설정이나 로그에 넣지 않으며 로컬 API 토큰은 Git에서 제외됩니다.

작업 상태는 queued → running → succeeded/failed/cancelled/timed_out입니다. API는
`/api/v1/jobs`, `/events`, `/system`, `/experiments`, `/artifacts`를 제공합니다.
읽기·쓰기 작업에는 `X-UGA-Token` 또는 Bearer 토큰이 필요합니다. `/health`, 계약과 capability
조회는 로컬 공개입니다. 교차 출처 요청과 임의 Host를 거부하며 서버는 loopback에만 바인딩됩니다.
OpenAPI는 `/openapi.json`, 네트워크 없이 읽을 수 있는 API 설명은 `/docs`입니다.

기본 동시 작업 수는 2, 대기열은 32입니다. 작업은 spawn 프로세스로 격리하고 마감 시각,
heartbeat와 RSS 예산(기본 512MB)을 확인합니다. 참조 플레이의 프로세스 종료/heartbeat 실패만
최대 1회 재시도합니다. 분석이나 빌드의 외부 효과는 자동 재시도하지 않습니다. 비정상 종료 후
남은 running/queued 레코드는 중단 원인과 함께 failed로 기록하고 명시적 재제출을 요구합니다.
게임과 추론 프로세스는 Watchdog에 별도 역할로 등록할 수 있습니다. 프로세스 격리는 OS 보안
샌드박스가 아니며 비신뢰 바이너리 실행을 허용하는 근거가 되지 않습니다.

Player는 프레임별 관측/행동을 trace에 기록하며 체크포인트를 주기적으로 원자 저장합니다.

```sh
.venv/bin/uga player --resume .uga/player/checkpoint.json --output .uga/resumed
.venv/bin/uga soak --seconds 1800 --output .uga/soak-1800
# 이후 검증할 실제 시간: 7200 / 14400 / 28800 / 57600초
# Windows: scripts/soak.ps1 -Seconds 7200
```

Soak은 실제 벽시계 시간을 사용하고 반복 에피소드 수, 실패, RSS와 CPU 시간을 기록합니다.
에피소드 로그는 10MB × 최대 4개로 회전합니다. `heartbeat.json`은 진행 상태이고 완료 증거는
이번 실행의 `summary.json`입니다. 미완료 heartbeat를 성공 결과로 간주하지 않습니다.
16시간 테스트를 지원하는 옵션이 있다는 사실은 16시간 검증 통과를 뜻하지 않습니다.

백그라운드 실행은 다음 명령으로 관리합니다. 같은 경로에서 다시 시작하면 현재 소유한
프로세스를 재사용합니다. 종료된 실행의 결과는 덮어쓰지 않으므로 새 검사는 새 경로를 씁니다.

```sh
.venv/bin/uga soak-service start --seconds 57600 --output .uga/long-run-new
.venv/bin/uga soak-service status --output .uga/long-run-new
.venv/bin/uga soak-service stop --output .uga/long-run-new
```

`results/run.json`에는 run ID, PID·생성 시각, 소스 SHA-256과 실제 런타임이 남습니다.
`milestone-1800s.json` 등은 같은 연속 실행에서 해당 실제 시간이 경과한 후에만 생성됩니다.
전체 16시간 성공은 16시간 경과와 최종 summary를 요구합니다. RSS 샘플을 무제한으로 보관하지
않고 peak/워밍업 후 증가량을 누적하며 기본 RSS 512MB·증가량 64MB를 넘으면 실패 처리합니다.
정상 중지는 취소 파일로 요청하여 취소 summary를 남깁니다. 프로세스가 사라지고 summary가
없으면 interrupted이며 성공으로 계산하지 않습니다. 백그라운드 프로세스의 새 환경 복원은
보장되지 않습니다.

실제 Godot 엔진 생성·분석·플레이와 내보내기는 [엔진 검증](engine-validation.md)을 참조하세요.

개선 흐름은 baseline 실행 → 후보 실행 → 동일 조건 비교 → 제안 → 명시적 승인 → 활성 정책
변경입니다. 기본 후보는 목표 선택을 직선 거리에서 장애물 경로 거리로 바꿉니다. 시드, 게임
설정, 실행 환경과 harness 해시가 다르면 비교를 거부합니다. 성공률·인식 정확도 하락, 행동 수
증가, P95 지연 25% 초과 악화, 개선 부재를 거부합니다. 5개 시드의 작은 실험이며 다른 게임의
일반화 성능을 입증하지 않습니다. 원본 결과를 내용 해시로 보관하고 변조된 제안은 승인하지 않습니다.

```sh
.venv/bin/uga improve --output .uga/experiment-new
# 결과를 검토한 사용자가 실행하거나 대시보드의 승인 버튼을 누릅니다.
.venv/bin/uga experiment approve --id EXPERIMENT_ID --approve
.venv/bin/uga experiment monitor --report SAME_CONDITIONS_REPORT.json
.venv/bin/uga experiment rollback
```

활성 정책은 새 참조 Player CLI/API 작업에 적용됩니다. 실행 중 작업이나 다른 게임 백엔드를
묵시적으로 변경하지 않습니다. 관찰 리포트가 악화되면 monitor가 이전 정책으로 복원합니다.
자동 코드/모델 배포는 구현하지 않았습니다. 현재 저장된 후보는 제안 상태이며 승인하지 않았습니다.
