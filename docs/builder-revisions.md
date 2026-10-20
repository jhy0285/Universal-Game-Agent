# Builder 프로젝트 수정과 오류 복구

`builder-edit`는 SHA-256으로 현재 파일을 확인한 뒤 별도 후보 프로젝트에 텍스트 수정을
적용합니다. 원본은 그대로 보존합니다. 경로 탈출, 심볼릭 링크, 중복 수정, 해시 불일치,
복사 크기 초과를 거부하며 모든 해시를 확인한 뒤 파일을 변경합니다.

패치 파일은 다음 계약을 사용합니다. expected_sha256은 수정할 원본 파일의 실제 해시입니다.

```json
{
  "summary": "수정 이유",
  "edits": [{
    "path": "main.gd",
    "expected_sha256": "원본 파일의 64자리 SHA-256",
    "content": "수정한 파일의 전체 UTF-8 내용"
  }]
}
```

```sh
.venv/bin/uga builder-edit SOURCE --patch patch.json --authorized --validate --allow-external-tools --output .uga/revision-new
.venv/bin/uga builder-repair SOURCE --authorized --allow-external-tools --output .uga/repair-new
```

출력의 `project/`가 후보이며 `revision.json`에 이전/이후 해시, 실제 검증 결과와 상태가 남습니다.
Godot 검증 실패 시 후보와 오류를 보존하고 실패를 반환합니다. 검증만으로 원본이나 활성 게임에
자동 적용하지 않습니다. 코드 수정 진입점은 CLI이며 REST의 임의 코드 실행 기능은 아닙니다.

현재 자동 repair 규칙은 실제로 재현한 UGA `Array[Rect2]` 할당 오류 **한 종류**입니다.
첫 실행 오류에 해당 타입과 정확한 기존 구문이 함께 있을 때만 수정하고 한 번 재검사합니다.
다른 오류는 failed로 남깁니다. 테스트에서는 고장 난 자체 프로젝트를 만든 뒤 실제 Godot의
실패를 수집했고, 후보 수정 후 6개 규칙 검사와 Player 승리를 확인했습니다. 원본의 고장 난
코드는 변경되지 않았습니다. 일반 게임의 임의 오류를 해결하는 생성 모델은 구현하지 않았습니다.

복사는 Godot 텍스트·PNG/SVG·오디오 리소스만 지원하며 최대 256개 파일 / 32MB입니다.
캐시·숨김 파일·빌드 산출물은 복사하지 않습니다. 비신뢰 프로젝트를 실행하는 OS 샌드박스는
아니므로 소유·실행 권한이 확인된 프로젝트에 사용해야 합니다.
