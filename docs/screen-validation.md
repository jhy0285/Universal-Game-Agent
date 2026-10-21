# 실제 화면과 대시보드 검증

2026-10-21(한국시간), Godot 4.6.3의 실제 X11 창을 **MSS 10.2.0**으로 캡처했습니다.
Xvfb에서 Mesa software rendering을 사용했고, 640×448 화면을 160×112 게임 좌표로 정규화했습니다.
정답 상태는 평가에 사용하며, 픽셀 모드의 정책에는 화면에서 인식한 GameState만 전달합니다.

| 시드 | 실제 행동 수 | HP·위치·적 수 인식 정확도 | 확인한 행동 효과 | 목표 |
|---|---:|---:|---:|---|
| 7 | 61 | 100% | 61 | 달성 |
| 11 | 50 | 100% | 50 | 달성 |
| 19 | 56 | 100% | 56 | 달성 |
| 23 | 53 | 100% | 53 | 달성 |
| 31 | 58 | 100% | 58 | 달성 |

capture/perception/decision/control/end-to-end의 P50/P95/P99, Python과 엔진의 자원 측정을
각 실행에 기록했습니다. CPU soak와 다른 검증이 함께 실행된 머신의 측정이며 일반 게임 성능이나
독립적으로 통제한 모델 비교로 간주하지 않습니다. 원시 결과는
`.uga/validation/godot-screen-final/results.json`입니다.

입력은 자체 게임의 opt-in 파일 브리지입니다. 실제 Windows 키보드·마우스 입력을 검증한
것으로 표시하지 않습니다. MSS 인식은 UGA 색상 프로파일만 지원하며 일반 OCR/VLM은 미구현입니다.

## 화면 동기화

렌더 모드에서는 draw가 끝난 뒤 상태 프레임을 공개하고, 마지막 승리 화면도 Player가 확인한
뒤 게임을 종료합니다. 프레임 run ID를 확인하고, 오래된 행동·알 수 없는 화면·인증 요청에서
정지합니다. trace에는 픽셀에서 추출한 상태와 결정이 남고, 마지막 실제 화면을 PNG로 보존합니다.
headless 정답 브리지와 MSS 픽셀 모드는 서로 다른 backend 이름으로 기록합니다.

```sh
uv sync --frozen --extra capture --python 3.12 --no-python-downloads
.venv/bin/python scripts/validate-godot-screen.py --allow-external-tools --xvfb .uga/tools/xvfb/usr/bin/Xvfb --output .uga/screen-new
```

Xvfb는 Debian의 서명을 검증한 InRelease와 Packages.xz, 개별 DEB의 SHA-256을 순서대로
확인한 뒤 사용자 폴더에 풀었습니다. 시스템 패키지나 권한은 변경하지 않았고 TCP listener는
사용하지 않습니다. 검사 종료 시 직접 시작한 Xvfb/Godot 프로세스만 정리합니다.

## 브라우저

Chromium **154.0.8037.57**, sandbox 활성화, 한국어/Asia-Seoul context에서 검사했습니다.
대시보드의 Builder → 실제 Godot 검사, Reverse → 실제 JADX 디컴파일, Player → 목표 달성·
160×112 미리보기를 확인했습니다. uncaught JavaScript 오류는 0개입니다. 데스크톱과 모바일
크기의 스크린샷을 보존했습니다. 다른 AI 시스템에는 연결하지 않았습니다.

```sh
node scripts/validate-dashboard.cjs --playwright /absolute/path/to/playwright-core --browser /usr/bin/chromium --allow-external-tools --exercise-agents --analysis-fixture .uga/validation/reverse-real/inputs/CombatRules.class --output .uga/dashboard-new
```

브라우저 요청은 소유한 loopback 서버로 제한했습니다. 주기적 polling이 있는 화면이므로
network-idle 대신 실제 연결 상태와 이번에 제출한 작업의 완료를 readiness 조건으로 사용합니다.
