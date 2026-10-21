# 클라우드 환경 설정

현재 인스턴스에서 frozen 설치, CPU Player, 실제 HTTP 작업, 서비스 재사용·재시작을
검증했습니다. 설치 스크립트는 연속 두 번 성공했습니다. Python 3.11.17은
`.uga/toolchains/python`에 별도로 설치했고, `.uga/python311-venv`와 기본 Python 3.12.14
`.venv`에서 각각 **77개 테스트**가 통과했습니다. 실제 Godot·JADX·Ghidra 검사를 포함하며
건너뜀은 0개입니다. 시스템 기본 Python은 변경하지 않았습니다.

환경 설정 초안에 저장한 필드:

- `install_script`: 기존 체크아웃에서 설치된 Python 3.11/3.12를 골라 uv frozen 설치·doctor 실행.
- `start_skill`: 서비스 시작/재사용·실제 HTTP Player readiness, 중지·재시작, 상태/로그 위치,
  실제 Godot·JADX/Ghidra/REA·MSS·Chromium 검증, 후보 수정, 공식 MCP SDK,
  백그라운드 장시간 실행 조회 및 검증 범위. heartbeat는 완료 결과로 계산하지 않습니다.
- `network.allowed_domains`: 기존 package_managers preset을 유지하고 custom 도메인에
  `huggingface.co` 추가. 모델 카드 요청의 실제 proxy 403을 근거로 저장했습니다.

저장 결과는 `status: saved`, `requires_publish: true`입니다. 저장만으로 스크립트 실행,
현재 네트워크 적용, 환경 게시 또는 새 머신 복원이 이루어지지 않습니다. 환경 설정에서
변경을 검토·저장하고 게시해야 합니다. 현재 런타임의 custom allowed_hosts는 비어 있고
정책 state는 unknown입니다. 차단된 모델 카드·가중치 라이선스·실추론은 미검증입니다.
리다이렉트되는 모델 파일이 있다면 실제 오류와 목적지를 확인한 뒤 필요한 도메인만 추가합니다.

선택적 도구는 `.uga/tools`에, 서버의 분석 도구 경로는 `.uga/analysis-tools.json`에 있습니다.
MSS 10.2.0은 capture extra이며 REA/MCP 검증 의존성은 별도 가상환경에 설치했습니다.
기본 설치 스크립트는 도구·모델을 자동 다운로드하지 않습니다. 복원 후에는 경로·버전·무결성부터
확인해야 합니다. 실제 화면 검사는 Linux Xvfb/Mesa와 자체 파일 입력 브리지를 사용했으며
Windows desktop 입력·GPU 추론 검증을 의미하지 않습니다.

CPU 연속 검사의 30분·2/4/8시간 누적 구간이 통과했고 16시간 전체 검사는 진행 중입니다.
환경 재연결 후 같은 run ID·프로세스 식별·heartbeat를 확인했습니다. 새 머신에서 설치와
서비스를 복원한 결과는 아닙니다. 프로세스는 스냅샷에서 복원되지 않으므로 기존 PID를 재사용하거나
미완료 검사를 자동 재시작하지 말고 결과의 run/summary를 먼저 확인해야 합니다.

CPU 흐름에는 외부 API key가 필요하지 않습니다. 로컬 API token은 서버가 생성하고 Git에서
제외합니다. 체크아웃은 `/workspace/Universal-Game-Agent`입니다. 클라우드 작업은 이미
격리되어 있으므로 별도 worktree를 만들지 않습니다. 소스와 커밋 기록은 GitHub의 `main`에
반영했습니다. clone으로 소스를 받은 뒤 의존성을 설치할 수 있지만, 무시된 `.uga`의 도구·모델·
로그와 실행 중인 프로세스는 별도로 준비해야 합니다. GitHub 소스 반영은 클라우드 환경 게시나
새 머신에서의 설치·실행 복원 검증을 뜻하지 않습니다.
