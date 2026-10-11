# 오케스트레이터 재확인 (R7)

도구: Claude Code (`CLAUDE.md`)

## CLAUDE.md에 담는 것 (얇게)

| 항목 | 내용 | 출처 |
|---|---|---|
| 참조 문서 | `story-service.md`, `scope.md`, `pipeline.md`, `artifacts.md`, `gates.md`, `roles.md`, `rules.json` | R0~R6 |
| 실행 루프 | 단계 시작 전 `state.json` 읽기 → 해당 에이전트 실행 → `judge` 실행 → 결과를 `state.json`에 기록 → 통과면 다음 단계, 실패면 복귀 | R3, R5 |
| 트리거 | 자연어 5개 (`roles.md`) | R6 |
| 중단 조건 | 아래 4개 | R7 |
| 편집 범위 | 에이전트별 편집 폴더 (`roles.md`) | R6 |

## CLAUDE.md에 담지 않는 것
- 필수 필드, 게이트 조건, 상한 같은 규칙 본문
- 규칙은 `rules.json`과 `gates.md`에만 두고, `CLAUDE.md`는 참조만 한다. (R4 SSOT 결정)

## 상태 관리
- 단계 순서와 복귀는 오케스트레이터의 기억이 아니라 `state.json`으로만 판단한다.

## 중단하고 사용자에게 보고하는 조건
1. 같은 단계로 되돌아오는 횟수가 2회를 넘음
2. 저장된 경험 카드가 0건인데 S2를 시작하려 함
3. 승인 기록 없이 S5를 시작하려 함
4. 카드에 `확인 필요` 표시가 남은 채 `review.md`로 넘어가려 함

## 편집 범위 강제
- 지시문(`CLAUDE.md`와 에이전트 정의)으로만 막는다.
- 어긴 편집을 거절하는 훅(hook)은 R8에서 검토한다.

## 확인 필요
- `state.json`의 필드 구성은 R8 검증에서 정한다.
