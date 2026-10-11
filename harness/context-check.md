# 준비물 확인 (R0)

도구: Claude Code (CLAUDE.md 사용)

## 준비물

| 준비물 | 경로 | 역할 | 비고 |
|---|---|---|---|
| PRD | interview_harness_prd.md | 요구사항 원본 | |
| 서비스 스토리 | harness/story-service.md | 판정 기준 (R1-A) | 사용자 관점 |
| 작업 스토리 | harness/story-work.md | 작업 재료 (R1-B) | 둘을 섞지 않는다 |
| 면접 인덱스 | 프로덕트 디자이너 면접 인덱스.html | 반영 대상 | 단일 HTML, 데이터는 JS 상수 |

## 면접 인덱스 HTML 현황 (확인된 사실만)

- 단일 HTML 파일, title: "프로덕트 디자이너 면접 인덱스" (파일 이름은 그대로)
- 이 저장소의 파일은 **샘플 더미 데이터 버전**이다. 구조(카드 15개, 카테고리 8개 등)는 원본과 같고 문구만 샘플로 바꿨다. 원본은 저장소 밖에 보관한다.
- 데이터 상수: CARDS, QGROUPS, GEN, FOLLOW, FOLLOW_CAT, PRESS, COMPANY, LVS
- 산출물과의 대응, 연동 방식: 미정 (PRD: "HTML 구조 확인 후 결정")

## 통과 조건 (스크립트가 셀 수 있는 형태)

- 필수 문서 4개 존재 = 4/4 (PRD, story-service, story-work, 면접 인덱스 HTML)

## 제외한 것

- `DESIGN-apple.md`: 이 하네스는 면접 카드 데이터를 만들고, 화면 스타일은 기존 HTML이 정한다. 하네스 어디에서도 참조하지 않는다. (화면 작업용 하네스를 따로 만들 때 다시 검토)

## 아직 없는 것

- CLAUDE.md / AGENTS.md: R7·R8 이후 초안 작성

## 메모

- 파일명에 한글·공백이 있어 스크립트에서는 따옴표로 감싼다.
