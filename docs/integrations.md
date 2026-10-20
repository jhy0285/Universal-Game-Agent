# 외부 도구 및 모델

외부 실행 파일은 요청문 11.9에 따라 사용자의 승인이 필요합니다. 도구 설치·라이선스·플랫폼
조건과 실행 대상은 별도 요건입니다. 아래 명령은 실행 진입점이며 실제 실행 결과는 phase-status에
구분해 기록합니다. 유료 AI나 다른 AI 시스템에 직접 연결하지 않습니다.

## Godot

`test_games/godot`는 원본 자산 없이 작성한 Godot 4 프로젝트입니다. 방향키 이동, Z 공격,
X 아이템, Space 점프, Escape 입력 정지를 지원합니다. 현재 설치 후보는
`/opt/godot/4.6.3/Godot_v4.6.3-stable_linux.x86_64`이고 파일 SHA-256은
`f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3`입니다.
경로의 버전명은 실제 버전 명령 실행 결과를 대신하지 않습니다.

승인 후 사용할 준비된 명령:

```sh
.venv/bin/uga godot-check test_games/godot --allow-external-tools
.venv/bin/uga godot-play test_games/godot --allow-external-tools
.venv/bin/uga godot-export test_games/godot --preset Linux --output .uga/export/uga.x86_64 --allow-external-tools
```

check는 실제 import/parse와 이번 실행 nonce를 가진 6개 smoke 검사를 요구합니다.
play는 별도 Godot 프로세스와 opt-in 파일 브리지를 통해 실제 엔진의 정답 상태를 읽고
Python 정책이 조작합니다. **이 검사는 화면 인식 테스트가 아닙니다.** CPU 참조 픽셀 검증과
Godot 정답 브리지 검증은 서로 다른 결과로 표시합니다. export에는 해당 엔진 버전의 export
templates가 추가로 필요합니다. 이전 결과 파일, PID 또는 생성된 프로젝트만으로 빌드 성공을
판정하지 않습니다. Unity는 라이선스가 있는 Editor가 필요한 확장 경계로 남겨 두었습니다.

## Windows 데스크톱

실제 데스크톱 검증은 Windows 11에서 수행해야 합니다. 직접 실행한 허가된 테스트 게임의
client 영역 좌표와 PID를 지정합니다. `capture` extra는 MSS를 설치합니다.

```powershell
uv sync --frozen --extra capture --python 3.11 --no-python-downloads
.\.venv\Scripts\uga.exe desktop-play --target-pid 12345 --region 100 100 640 448 --authorized --seconds 60
```

위 PID/좌표는 사용자가 자신의 환경에 맞게 입력해야 하는 예입니다. 입력은 foreground PID에
묶이며 키/마우스 hold를 최대 250ms로 제한합니다. 포커스·프레임·인식 상태를 확인하고
마지막에 모든 입력을 해제합니다. 마우스는 승인한 창의 client 영역만 허용합니다.
프로파일은 정수 배율(최대 8배)의 UGA 아레나 화면만 인식합니다. 임의 게임의 OCR·VLM,
캐릭터/인벤토리 인식이 동작한다고 주장하지 않습니다.

## Reverse

기본 분석은 소스 선언/문법상 호출 위치, APK/ZIP 멤버·리소스 이름, DEX 존재와 바이너리 헤더를
제한된 크기로 읽습니다. 파일을 실행하거나 APK를 설치하지 않습니다. 압축 경로 탈출·과도한
확장·암호화·심볼릭 링크를 거부합니다. 정적 구조와 실행 의미, 확인 사실과 가설을 구분합니다.
`game_spec.json`을 읽은 경우에도 그 내용은 소스 선언이며 실제 동작을 입증하지 않습니다.
지원하는 GameSpec이 없으면 원본 게임의 동작을 추측하여 rebuild하지 않습니다.

JADX 어댑터는 공식 `-d OUTPUT INPUT` 인터페이스를 사용하고 Java >=11이 필요합니다.
Windows의 shell/batch 인자 위험을 피하기 위해 직접 Java classpath 런처를 지정할 수 있습니다.
Ghidra는 analyzeHeadless와 제공된 `UGAExport.java`로 함수/호출 근거를 JSON으로 내보냅니다.
Windows batch 런처의 직접 실행은 현재 지원하지 않습니다. 두 도구 모두 실행 승인, 분석 권한,
신뢰된 입력이 필요합니다. 비신뢰 입력은 별도 VM/OS 샌드박스를 먼저 준비해야 합니다.

REA는 공식 MCP discovery가 반환한 tool/schema만 호출하는 주입형 어댑터입니다. npm 패키지
`rea-agents@6.7.0`과 공식 stdio MCP 계약을 확인했습니다. 설치·연결·실제 도구 호출은 수행하지
않았습니다. 원문 evidence를 보존하며 결과가 없거나 부분적이면 게임 메커니즘을 만들어 내지 않습니다.

## Laya / VLM / LLM

Laya 공식 저장소는 `NandhaKishorM/laya`, PyPI에서 확인한 버전은 **0.4.12**, Python 요구는
>=3.10입니다. 배포 메타데이터는 torch>=2.0, transformers>=4.48, safetensors,
huggingface_hub, numpy를 요구합니다. upstream 설치 문서의 최신 툴체인 언급과 실제 배포
요구사항은 같다고 가정하지 않습니다. 저장소 라이선스는 Apache-2.0이며 모델 카드 라이선스는
별도 확인이 필요합니다. 현재 모델 카드 목적지 `huggingface.co`가 proxy 정책에서 403으로
차단되어 체크포인트 공개 상태·라이선스·무결성을 직접 검증하지 못했습니다.

영어/typed 모델은 upstream이 421M, multilingual은 322M으로 설명합니다. FP32 가중치만으로
약 1.7GB/1.3GB이며 실제 CPU RAM/지연은 설치 후 측정해야 합니다. GPU는 선택 사항입니다.
공식 `Router.predict(text, questions)` 응답을 어댑트하며 이미지 입력으로 취급하지 않습니다.
Router는 외부에서 명시적으로 주입하고 자동 다운로드하지 않습니다. 게임 판단에 보정되지 않은
결과를 높은 신뢰도로 바꾸지 않으며 controller는 낮은 신뢰도 결과를 실행하지 않습니다.

StrategyWorker는 느린 전략 계산을 별도 spawn 프로세스에 두고 fast RuleBasedPolicy를
블로킹하지 않습니다. 지연·취소·결과 계약은 자체 Python fixture로 검증했습니다. 이는 실제
Laya 추론이나 VLM 정확도 검증을 의미하지 않습니다. 실모델 비교는 아직 수행하지 않았습니다.

## 외부 AI 인터페이스

REST v1, versioned schemas, AgentRegistry, job/event interface와 로컬 MCP stdio가 있습니다.

```sh
.venv/bin/uga mcp --state-dir .uga/mcp
```

MCP는 2025-06-18 initialize/ping/tools/list/tools/call을 구현합니다. 도구는
uga_submit_task, uga_job_status, uga_cancel_task입니다. 이 명령을 외부 시스템에 등록하는
작업은 하지 않았습니다. `python` fixture/직접 JSON-RPC 검증과 실제 외부 클라이언트 상호운용
검증을 구분합니다. 미래 호출자는 기존 에이전트를 REST/MCP로 사용할 수 있습니다.
