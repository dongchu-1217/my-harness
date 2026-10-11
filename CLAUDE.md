# 면접 카드 생성 하네스 (Claude Code)

JD 1건을 입력받아 면접 카드를 만들고, 사용자 승인 후 면접 인덱스 HTML에 반영한다.
이 파일은 진행 방법만 담는다. 규칙 본문은 아래 문서가 원본이고, 여기에 복사하지 않는다.

## 참조 문서 (원본)
- 판정 기준: harness/story-service.md (어기면 안 되는 것 2개)
- 범위: harness/scope.md
- 단계·입출력·복귀: harness/pipeline.md
- 파일·재개: harness/artifacts.md
- 게이트(통과 조건): harness/gates.md
- 역할·편집 범위·트리거: harness/roles.md
- 규칙 SSOT: harness/rules.json
- 판정 스크립트: harness/scripts/judge.py (읽기 전용), 테스트: harness/tests/run_tests.py
- 입력 문서: interview_harness_prd.md
- 카드→HTML 매핑: harness/mapping.md
- 반영 대상: 플랫폼 디자이너 면접 인덱스.html

## 실행 루프
1. 단계 시작 전 실행 폴더의 state.json을 읽는다. (기억에 의존하지 않는다.)
2. 해당 단계의 에이전트를 실행한다.
3. judge(읽기 전용)를 실행해 게이트를 판정한다.
4. 결과를 state.json과 04-check.json에 기록한다.
5. 통과하면 다음 단계, 실패하면 pipeline.md의 복귀 지점으로 간다.

## 자연어 트리거
- "경험 추가할게" → 경험 카드를 사용자가 입력한 그대로 harness/data/experiences.json에 저장
- "{기업명} 면접 카드 만들어줘" → 새 실행 폴더 생성, S1~S4 진행 후 review.md 제시
- "승인" → `judge HASH`로 해시를 얻어 state.json에 approved, approved_at, approved_cards_hash, approved_html_hash를 기록하고, `judge APPROVAL`이 통과하면 S5 실행
- "반려", "다시" → S3로 복귀
- "이어서" → state.json의 마지막 통과 단계 다음부터 재개

## 중단하고 사용자에게 보고
1. 같은 단계로 되돌아오는 횟수가 2회를 넘음
2. 저장된 경험 카드가 0건인데 S2를 시작하려 함
3. 승인 기록 없이 S5를 시작하려 함
4. 카드에 `확인 필요`가 남은 채 review.md로 넘어가려 함

## 편집 범위 (에이전트별)
- 오케스트레이터(나): 실행 폴더의 state.json, 04-check.json, review.md, harness/data/experiences.json
- card-writer(S1~S3): harness/runs/{실행 폴더}/의 01~03 파일만
- index-writer(S5): 인덱스 HTML 1개, harness/runs/{실행 폴더}/05-*
- judge: 읽기 전용 (파일을 수정하지 않는다.)

## 지킬 것
- 없는 성과·경험·수치를 만들지 않는다. 확인되지 않은 내용은 `확인 필요`로 표시한다.
- 사용자 승인 전에는 인덱스 HTML을 고치지 않는다. 반영 전에는 항상 백업한다.
- 범위 밖: 화면 디자인 흐름, 음성 분석, AI 자동 채점

## 구현 상태
- 완료: rules.json, judge.py, 게이트 테스트(V1), .claude/agents/ 정의(card-writer, index-writer, judge), mapping.md
- V2 드라이런 완료 (harness/tests/dryrun/, 기록은 harness/verification.md)
- 미완: 매핑표의 `확인 필요` 항목 확정(harness/mapping.md), 실제 JD·경험 카드로 첫 실행
- 에이전트 정의는 새 세션에서 인식된다.
