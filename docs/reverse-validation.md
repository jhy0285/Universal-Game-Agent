# 실제 Reverse 도구 검증

2026-10-21(한국시간), Linux에서 공식 JADX **1.5.6**, Ghidra **12.1.4**, REA **6.7.0**을
실행했습니다. 대상은 저장소의 [자체 Java/C 코드](../test_games/reverse_fixture)에서 만든 파일입니다.
네이티브 샘플을 호스트 프로세스로 실행하지 않았습니다.

| 검사 | 실제 결과 |
|---|---|
| JADX / Java class | clampHp, applyDamage, usePotion 복구 |
| JADX / DEX 포함 APK fixture | 실제 DEX 035를 디컴파일해 같은 3개 메서드 복구 |
| Ghidra / ELF | 함수 18개, 자체 함수 3개와 apply_damage → clamp_hp 호출 확인 |
| REA / MCP | 도구 207개 discovery, 자체 ELF의 read-only layout 호출 및 SHA-256 확인 |
| REST 작업 큐 | JADX·Ghidra 실제 작업 성공, 각각 아티팩트 5개·3개 해시 확인 |
| 브라우저 | Reverse에서 JADX 작업 제출·완료 확인 |

APK fixture는 정적 분석을 위해 만든 ZIP/DEX 조합이며, plaintext manifest를 사용하므로
**설치 가능한 Android 앱이 아닙니다**. APK 설치·Android 실행을 검사한 것으로 표시하지 않습니다.
함수 근거는 사실로 저장하지만 장르·게임 메커니즘은 unknown입니다. REA의 207개 도구를
모두 실행하거나 모든 provider가 설치된 것으로 표시하지 않습니다.

## 설치와 무결성

모든 도구는 `.uga/tools/`에 설치했습니다. 시스템 기본 Java/Python이나 권한 설정은 바꾸지
않았습니다. JADX/Ghidra 배포 ZIP은 공식 GitHub release의 SHA-256과 대조했습니다.

| 배포 파일 | 확인한 SHA-256 |
|---|---|
| jadx-1.5.6.zip | 545ea2be9c242511bc145755cf4bda2485ade42966e096f8b4d3da2a230e8974 |
| ghidra_12.1.4_PUBLIC_20260921.zip | ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db |
| Temurin JDK 21.0.12.1+1 archive | ce79869e1307ed8ee1e2baa86a412b1eb5b75d10a01006d788a6f968bcfaee94 |

REA는 npm integrity가 있는 6.7.0을 `--ignore-scripts`로 설치했습니다. ELF provider에는 공식
설정 키 REA_PWNTOOLS_PYTHON으로 별도 Python을 지정했습니다. 정확한 의존성은 pwntools
4.15.0, pyelftools 0.33, Unicorn 2.1.2입니다. upstream의 offline wrapper를 확인했고,
libs/maps/libc를 통한 호스트 실행을 사용하지 않습니다. PLT 추론에는 Unicorn의 명령 에뮬레이션이
사용될 수 있으며, 그 결과를 실제 런타임 관측으로 간주하지 않습니다.

자체 DEX를 만든 R8 9.5.28은 공식 Google Maven의 게시 SHA-1을 확인했고, 별도로 계산한
SHA-256은 `38a9ffaaebbd17d1514e3ecbff5a85b989bb13c551b9e224c7409514eea84ff5`입니다.
R8의 자체 BSD-3-Clause 및 포함된 라이브러리 고지는 원본 배포에 보존합니다.

## 발견하고 수정한 문제

Ghidra는 프로젝트 경로 요소가 점으로 시작하면 거부했습니다. `.uga/...`의 결과 폴더와
분리한 `uga-ghidra-*` 임시 프로젝트를 사용하도록 고쳤고, 결과 JSON은 지정한 폴더에 보존합니다.
해당 오류를 재현하는 회귀 검사와 실제 함수·호출 검사를 추가했습니다.

자원 측정도 shell launcher와 Java 자식을 합산하도록 수정했습니다. 원본 자체 ELF 검사에서
관측한 프로세스 트리의 RSS peak는 약 416MB였습니다. 메모리 예산은 JADX 2GB, Ghidra 4GB이며,
동시 자식 32개·실행 전체 256개 상한, 시간·출력 제한을 적용합니다. JADX 처리 thread와 Ghidra
분석 CPU는 각각 1로 제한합니다. 이는 비신뢰 코드용 OS 보안 샌드박스가 아닙니다.

정적 분석(`analyze`, JADX 결과 재분석 포함)은 작업 워커의 512MB 한도 안에서 입력 예산
전체(파일당 32MiB·합계 64MiB)를 처리하도록 기록량을 제한합니다. 클래스·함수 항목 20,000개,
호출 위치 50,000개, 함수 선언 finding 2,000개까지만 남기고 개수는 끝까지 셉니다. 넘치면
`structure.json`의 `truncated`가 true가 되고 `analysis limits` finding이 남습니다. 생략된 항목은
존재하지 않는다는 근거가 아닙니다. 분석 중에도 heartbeat를 보내 10초 감시에 걸리지 않습니다.

## 작업 큐와 API

서버 상태 폴더의 `analysis-tools.json`에 설치된 절대 경로를 지정합니다. 현재 인스턴스는
`.uga/analysis-tools.json`에 설정했습니다. API 요청은 실행 파일 경로를 받지 않습니다.

```json
{
  "java": "/absolute/path/to/jdk/bin/java",
  "jadx_installation": "/absolute/path/to/jadx",
  "ghidra": "/absolute/path/to/ghidra/support/analyzeHeadless"
}
```

```json
{
  "agent": "reverse",
  "operation": "decompile",
  "authorized": true,
  "parameters": {
    "path": "PATH_WITHIN_ANALYSIS_ROOT",
    "tool": "ghidra",
    "trusted_input": true
  }
}
```

권한·신뢰 확인, 허용한 분석 root, heartbeat, timeout, 취소 및 아티팩트 해시 검사를 적용합니다.
디컴파일은 자동 재시도하지 않습니다. 비신뢰 입력에는 별도 VM/OS 샌드박스가 필요합니다.

```sh
.venv/bin/python -m pytest --allow-analyzers tests/test_analyzers_external.py
.venv/bin/python scripts/smoke-analysis-http.py --allow-external-tools --input-dir .uga/validation/reverse-real/inputs --output .uga/analysis-http-new.json
.uga/mcp-client-venv/bin/python scripts/validate-rea.py --rea-script .uga/tools/rea/node_modules/rea-agents/scripts/rea.mjs --pwntools-python .uga/tools/rea-python/bin/python --sample .uga/validation/reverse-real/inputs/combat --output .uga/rea-new.json --authorized --allow-external-tools
```

MCP 검증 환경에는 mcp 2.3.0과 psutil 7.2.2가 필요합니다. 도구와 provider는 선택적이며 기본
CPU 설치에 포함하지 않습니다. Windows의 외부 도구 실행은 아직 검증하지 않았습니다.
