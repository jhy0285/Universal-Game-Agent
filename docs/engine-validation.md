# 실제 Godot 엔진 검증

2026-10-21 Linux / Python 3.12.14 / Godot **4.6.3.stable.official.7d41c59c4**에서
생성 프로젝트의 import, 6개 게임 규칙 검사, 5개 고정 시드 자율 플레이를 실행했습니다.
시드 7/11/19/23/31에서 각각 61/50/56/53/58단계로 모두 승리했고 HP는 100이었습니다.
원시 결과에서 정리한 기록은 [validation/godot.json](validation/godot.json)입니다.

실행하면서 발견한 typed Array 할당 오류, smoke 실행 시점, export 설정 누락을 수정했습니다.
`arena.json`과 `game_spec.json`을 내보내기에 포함하고, 종료 코드가 0이어도 Godot 오류 로그가
있으면 import/export를 실패로 판정합니다. 실행마다 다른 nonce의 결과를 확인합니다.

## 재현

Godot 설치와 자신의 UGA 프로젝트 실행 허용이 필요합니다. 기본 테스트는 외부 실행 검사를
건너뛰며, 다음 명령은 해당 실행을 명시적으로 허용합니다.

```sh
.venv/bin/python -m pytest --allow-godot
.venv/bin/python scripts/validate-godot.py --allow-external-tools --export --output .uga/validation/engine-new
.venv/bin/uga workflow --backend godot --allow-external-tools --export-preset Linux --output .uga/workflow-engine-new
.venv/bin/uga rebuild test_games/godot --authorized --backend godot --allow-external-tools --output .uga/rebuild-engine-new
```

실제 엔진과 Python 정책의 opt-in 정답 브리지를 검증합니다. 화면 인식이나 Windows 입력
검증 결과로 간주하지 않습니다. 별도 [MSS 화면 검사](screen-validation.md)에서는 실제 픽셀
관측만 정책에 전달해 같은 5개 시드를 완료했습니다. 입력은 자체 브리지입니다.
엔진이 행동을 5초 동안 확인하지 않으면 정지하고, 각 외부
프로세스에는 시간·출력·RSS 제한을 적용합니다. Python과 엔진의 자원 측정은 따로 표시합니다.

## 실행 파일

공식 4.6.3 export templates를 HTTPS로 받아 공식 `SHA512-SUMS.txt`와 일치하는지 확인했습니다.
아카이브에서 Linux/Windows release 템플릿과 version.txt만 사용자 디렉터리에 설치했습니다.

| 대상 | 결과 | 파일 크기 | 실행 검증 |
|---|---|---:|---|
| Linux x86_64 | 내보내기 성공 | 71,087,176 bytes | 별도 실행 파일을 직접 실행해 목표 달성 |
| Windows Desktop x86_64 | 교차 내보내기 성공 | 104,529,976 bytes | 미실행: 이 머신은 Linux |

산출물은 `.uga/validation/engine-release-final/export/`에 있습니다. 실행 파일과 일시적인 로그는
Git에서 제외하며 해시는 JSON 기록에 남겼습니다. Windows 파일 생성 성공을 Windows 런타임
성공으로 표현하지 않습니다.

## API와 대시보드

- Builder `build`: 생성한 UGA 프로젝트를 import → smoke → Player 순서로 검증합니다.
- Workflow `build-play`: 생성 → Reverse 분석 → 선택한 Player backend로 검증합니다.
- Workflow `reverse-build-play`: 허가된 경로의 선언 GameSpec을 Builder에 전달합니다.
- Godot backend와 Builder build는 `TaskSpec.authorized=true`가 필요합니다.
- `export_preset`은 `Linux` 또는 `Windows Desktop`입니다. 실제 export 후에만 built=true입니다.

대시보드에서 생성한 게임의 Godot 실행 허용과 내보내기 대상을 선택할 수 있습니다.
원격 파일이나 임의 shell 명령을 API로 실행하는 기능은 없습니다.
