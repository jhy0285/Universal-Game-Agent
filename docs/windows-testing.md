# Windows 로컬 테스트

대상은 Windows 11 x64, Python 3.11 또는 3.12입니다. 처음에는 CPU 참조 게임으로 설치와
세 에이전트 연결을 확인한 뒤, 자체 Godot 창의 캡처와 실제 입력을 차례로 확인하세요.
현재 인식 프로파일은 UGA 아레나 전용입니다. 일반 게임·Laya·OCR/VLM은 별도 개발·설치 범위입니다.

## 1. 준비와 설치

Git for Windows, Python 3.11, uv가 필요합니다. 설치되어 있으면 아래 설치 명령은 생략합니다.
Windows의 winget을 사용하는 경우:

```powershell
winget install --id Git.Git --exact
winget install --id Python.Python.3.11 --exact
winget install --id astral-sh.uv --exact
```

설치 뒤 PowerShell을 새로 열고 실행합니다. 가상환경 활성화나 실행 정책 변경은 필요 없습니다.

```powershell
git clone --branch main https://github.com/jhy0285/Universal-Game-Agent.git
cd Universal-Game-Agent
uv sync --frozen --extra capture --python 3.11 --no-python-downloads
.\.venv\Scripts\uga.exe doctor
```

이미 clone한 저장소는 그 폴더에서 `git pull --ff-only origin main`으로 갱신하세요.
`--no-python-downloads`는 이미 설치된 Python을 사용합니다. 설치된 3.11을 찾지 못하면
`py -0p`로 경로를 확인하고 `--python`에 해당 python.exe의 전체 경로를 지정하세요.
`doctor`의 windows_input/capture 표시는 플랫폼과 설치 여부이며 실제 입력 성공 증거는 아닙니다.

## 2. 기본 동작 확인

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\uga.exe player --seed 7 --output .uga\local-player
$ugaStamp = Get-Date -Format "yyyyMMdd-HHmmss"
.\.venv\Scripts\uga.exe workflow --output ".uga\local-workflow-$ugaStamp"
```

확인할 결과:

- pytest: 실패 0개. 기본 검사는 외부 Godot/JADX/Ghidra 검사 7개를 skip합니다.
- player: `success: true`, `stop_reason: goal_complete`, `.uga/local-player/last-frame.png` 생성.
- workflow: 참조 Player의 `success: true`. 이 단계는 Godot 실행이나 실제 Windows 입력 검사가 아닙니다.

출력 폴더를 새로 요구하는 명령은 재실행 시 `$ugaStamp`를 다시 만들거나 다른 경로를 쓰세요.

## 3. 대시보드와 실제 HTTP 확인

```powershell
.\.venv\Scripts\uga.exe service start
.\.venv\Scripts\python.exe scripts\smoke-http.py
.\.venv\Scripts\uga.exe service status
```

`http_smoke: passed`, service의 `healthy: true`를 확인합니다. `service status`가 출력한
`dashboard_url`을 브라우저 주소창에 붙여 넣으면 대시보드가 열립니다. 토큰은 주소의 `#` 뒤에만
있고 페이지가 열리면 주소창에서 지워집니다. 서버를 다시 시작하면 토큰이 바뀌므로 새
`dashboard_url`로 다시 여세요. Player, Builder, 소스 Reverse를 차례로 실행해 결과와 미리보기를
확인하세요. 이 주소나 API token을 다른 사람과 공유하지 마세요.

종료:

```powershell
.\.venv\Scripts\uga.exe service stop
```

## 4. Godot 엔진 확인

Godot **4.6.3 Standard Windows x64**를 공식 배포에서 설치합니다(.NET판은 필요 없음).
GUI 실행 파일을 `godot.exe` 이름으로 두고 그 폴더를 사용자 PATH에 추가한 뒤 새 PowerShell을
열어 `Get-Command godot`으로 확인하세요. 첫 검사는 import/play이며 export templates는
실행 파일 내보내기를 할 때 같은 버전으로 추가 설치합니다.

```powershell
$ugaStamp = Get-Date -Format "yyyyMMdd-HHmmss"
.\.venv\Scripts\uga.exe godot-check test_games\godot --allow-external-tools --output ".uga\godot-check-$ugaStamp"
.\.venv\Scripts\uga.exe workflow --backend godot --allow-external-tools --output ".uga\godot-workflow-$ugaStamp"
```

7개 smoke 검사와 엔진 Player 성공을 확인합니다. 이 단계의 Player는 정답 브리지 backend이며,
실제 화면·키보드 입력 검증은 다음 단계입니다. JADX/Ghidra/REA나 모델은 이 검사에 필요 없습니다.
`pytest --allow-analyzers`는 Linux 온보딩 전용 도구 경로를 사용하므로 로컬 Windows에서
그대로 실행하지 마세요. Windows 분석 도구 설정은 [Reverse 검증](reverse-validation.md)을 참조합니다.

## 5. 입력 없이 실제 게임 화면 확인

Godot GUI 실행 파일을 사용하세요. 별도 프로세스를 만드는 `_console.exe` launcher는 사용하지
마세요. 다음 명령은 직접 시작한 게임의 PID를 `$ugaGame.Id`에 보존합니다.

```powershell
$ugaGame = Start-Process -FilePath (Get-Command godot).Source -WorkingDirectory (Resolve-Path test_games\godot).Path -ArgumentList @("--path", ".") -PassThru
$ugaStamp = Get-Date -Format "yyyyMMdd-HHmmss"
.\.venv\Scripts\uga.exe desktop-check --target-pid $ugaGame.Id --authorized --start-delay 8 --output ".uga\desktop-check-$ugaStamp"
```

**명령 실행 후 8초 안에 게임 창을 클릭**하세요. 이 검사는 키보드·마우스 입력을 보내지 않습니다.
창 테두리를 제외한 client 영역을 자동 감지하고, MSS 초기화 후 DPI 좌표를 계산합니다.
게임 창은 기본 640×448 크기로 유지하세요. 현재 프로파일은 160×112의 정수 배율(최대 8배)을
지원합니다. 창이 가려지거나 최소화되면 정상 관측을 얻을 수 없습니다.

`passed: true`, `input_sent: false`, `profile: uga-arena-v1`과 출력 폴더의
`preview.png`·`state.json`을 확인하세요. 실패하면 실제 입력 단계로 넘어가기 전에 프레임과
게임 PID·포커스·창 크기를 확인합니다. 이미 목표를 달성했으면 게임을 다시 시작합니다.

## 6. 실제 Windows 입력 확인

첫 입력 검사는 아래 게임 실행 명령으로 새 게임을 연 뒤 바로 진행하세요. 이전 게임 창은 직접
닫습니다. 수동 모드의 기본 step 예산은 대기 중에도 진행되므로 오래 열어둔 게임을 재사용하지 마세요.

```powershell
$ugaGame = Start-Process -FilePath (Get-Command godot).Source -WorkingDirectory (Resolve-Path test_games\godot).Path -ArgumentList @("--path", ".") -PassThru
$ugaStamp = Get-Date -Format "yyyyMMdd-HHmmss"
.\.venv\Scripts\uga.exe desktop-play --target-pid $ugaGame.Id --authorized --start-delay 8 --seconds 30 --output ".uga\desktop-play-$ugaStamp"
```

8초 안에 게임 창을 클릭하고 조작을 관찰합니다. 입력 직전과 키를 누르는 동안 대상 PID의
포커스를 검사합니다. 자동 캡처 영역은 매 프레임 다시 확인하며 수동 `--region`은 해당 client
영역 안에서만 허용합니다. 다른 창으로 전환하면 입력을 해제하고 정지합니다. 게임 안에서
Escape를 누르면 인증 정지 상태로 전환되며 다음 관측에서 사람에게 인계합니다.

키 입력은 가상 키와 함께 하드웨어 scan code·확장 키 플래그를 보냅니다. 테스트 게임은
물리 키를 읽으므로 scan code가 없으면 입력이 무시됩니다. 게임은 0.1초마다 한 번 행동을
적용하며 그 사이의 짧은 키 누름도 한 번 반영합니다.

`result.json`의 success/stop_reason/verified_effects와 `trace.jsonl`을 확인하세요.
Windows 입력 성공은 이 결과로 판정해야 합니다. Linux fixture 검사나 GitHub CI의 통과가
실제 Windows GUI 입력 검증을 대신하지 않습니다. 이 단계는 사용자 PC에서 아직 미검증입니다.

## 7. 장시간 검사와 후속 고도화

짧은 검사를 통과한 뒤 참조 CPU backend의 30분 검사부터 시작합니다.

```powershell
$ugaStamp = Get-Date -Format "yyyyMMdd-HHmmss"
.\.venv\Scripts\uga.exe soak-service start --seconds 1800 --output ".uga\local-soak-$ugaStamp"
.\.venv\Scripts\uga.exe soak-service status --output ".uga\local-soak-$ugaStamp"
# 필요 시 같은 경로로 중지
.\.venv\Scripts\uga.exe soak-service stop --output ".uga\local-soak-$ugaStamp"
```

완료는 results/summary.json의 passed와 실제 elapsed_s로 확인합니다. 이 명령은 참조 CPU
반복 검사이며 Windows 게임 창이나 모델의 장시간 운영 검사는 별도로 구성해야 합니다.

우선순위는 (1) Windows 실제 입력·화면·DPI 로그 확인, (2) 로컬 하드웨어에 맞는 모델과
라이선스 확인 후 Laya/OCR/VLM 연동, (3) 게임별 인식·입력 프로파일, (4) 생성·수정 후보의
회귀 검사와 승인·롤백 확장입니다. 범용 게임 생성이나 모델 자기개선은 추가 구현이 필요합니다.
