# Universal Game Agent (UGA)

로컬 CPU 환경에서 허가된 게임을 플레이·분석·생성하고 결과를 측정하는 Python 플랫폼입니다.
Windows 11 / Python 3.11을 목표로 하며 Python 3.12와 Linux 개발도 지원합니다.
유료 API와 GPU는 필수가 아닙니다.

```sh
uv sync --frozen
uv run uga doctor
uv run pytest
uv run uga serve
```

이미 Python 3.12가 설치된 개발 머신에서는 `uv sync --frozen --python 3.12`를 사용합니다.
현재 기능·실제 검증·제한 사항은 `docs/phase-status.md`에 기록합니다.
대시보드는 기본적으로 로컬 컴퓨터에만 바인딩됩니다.

공통 스키마: `uv run uga schemas`. 설계: [architecture](docs/architecture.md).
자동 조작은 자체 테스트 게임이나 명시적으로 허가된 대상에만 사용합니다.
인증 요청이 감지되거나 상태를 신뢰할 수 없으면 입력을 멈춥니다.
