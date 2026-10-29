# Universal Game Agent (UGA)

로컬 CPU 환경에서 허가된 게임을 플레이·분석·생성하고 결과를 측정하는 Python 플랫폼입니다.
Windows 11 / Python 3.11을 목표로 하며 Python 3.12와 Linux 개발도 지원합니다.
유료 API와 GPU는 필수가 아닙니다.

현재 구현은 CPU 참조 게임, 실제 Godot 생성·테스트·MSS 화면 자율 플레이·내보내기와
자체 샘플의 JADX/Ghidra/REA 분석을 검증한 플랫폼입니다.
임의의 상용 게임을 이해하는 완성된 AI는 아닙니다. 단계별 실제 실행 결과와
미완료 범위는 [검증 현황](docs/phase-status.md)에 기록합니다.

AI 코딩 에이전트로 이어서 작업하려면 저장소만 연결하고 [AGENTS.md](AGENTS.md)(규칙·시작 절차)와
[다음 작업](docs/next-steps.md)을 먼저 읽게 하세요.

로컬 PC에서 저장소 받기 (Git 필요):

```sh
git clone --branch main https://github.com/jhy0285/Universal-Game-Agent.git
cd Universal-Game-Agent
```

클라우드 / Linux (설치된 Python 3.11 또는 3.12와 uv 사용):

```sh
bash scripts/setup-cloud.sh
.venv/bin/uga player --seed 7
.venv/bin/uga service start
.venv/bin/python scripts/smoke-http.py
.venv/bin/uga service status
```

Windows에서 처음 실행하는 경우 [단계별 로컬 테스트](docs/windows-testing.md)를 먼저 보세요.

Windows 11 / PowerShell (Python 3.11과 uv가 설치된 경우):

```powershell
uv sync --frozen --python 3.11 --no-python-downloads
.\.venv\Scripts\uga.exe player --seed 7
.\.venv\Scripts\uga.exe service start
.\.venv\Scripts\python.exe -m pytest
```

대시보드는 로컬 포트 8765에서 작동합니다. `uga service stop`으로 이 도구가 시작한 서버만
종료합니다. API 토큰은 `.uga/api-token`에 생성됩니다. 대시보드는 `uga service start`·`status`가
출력하는 `dashboard_url`로 여세요. 토큰은 서버로 전송되지 않는 URL 조각(`#token=`)으로만
전달되고 페이지 HTML에는 들어가지 않습니다.
GPU/VRAM 미측정 값은 미상으로 표시합니다. 외부 유료 API와 다른 AI 시스템 연결은 없습니다.

```sh
# 독립 에이전트와 연결 흐름
.venv/bin/uga builder --requirements '적 3마리가 있는 2D 게임' --output .uga/new-game
.venv/bin/uga reverse test_games/godot --authorized --output .uga/analysis
.venv/bin/uga workflow --output .uga/workflow
.venv/bin/uga rebuild test_games/godot --authorized --output .uga/rebuilt
# Godot 설치 및 생성 게임의 엔진 실행을 허용한 경우
.venv/bin/uga workflow --backend godot --allow-external-tools --output .uga/godot-workflow
# 고정 시드 벤치마크와 개선 제안 (적용은 별도 승인)
.venv/bin/uga benchmark --output .uga/baseline
.venv/bin/uga improve --output .uga/experiment-1
.venv/bin/uga experiment list
```

공통 스키마: `uga schemas`. [설계](docs/architecture.md) · [운영](docs/operations.md) ·
[외부 도구/모델](docs/integrations.md) · [엔진 검증](docs/engine-validation.md) ·
[실제 화면](docs/screen-validation.md) · [Reverse 검증](docs/reverse-validation.md) ·
[공식 자료와 라이선스](docs/references.md).

자동 입력은 자체 테스트 게임이나 명시적으로 허가된 대상에만 사용합니다. 인증 요청,
오래된 관측, 잘못된 프레임, 포커스 상실에서는 입력을 멈춥니다. 불명확한 값은 `null`이며
픽셀 인식 프로파일은 UGA 아레나 전용입니다. CAPTCHA 해결·안티치트 우회·게임 메모리 변조는 없습니다.
