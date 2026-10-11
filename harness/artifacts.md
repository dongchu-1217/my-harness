# 산출물 (R4)

## 파일 구조

`harness/` 기준 (인덱스 HTML만 루트에 둔다.)
- `harness/rules.json`: 규칙 SSOT (1개)
- `harness/data/experiences.json`: 저장된 경험 카드 (공용, 실행 폴더 밖)
- `harness/scripts/judge.py`: 판정 스크립트
- `harness/tests/`: 테스트 전용 샘플 데이터
- `프로덕트 디자이너 면접 인덱스.html` (루트): S5가 제자리 수정
- `harness/runs/{날짜}-{기업 영문 슬러그}/`: 실행 1회(JD 1건)당 폴더 (슬러그는 하네스가 기업명에서 생성)

## 실행 폴더 파일

| 단계 | 파일 | 용도 |
|---|---|---|
| S1 | `01-jd-analysis.json` | JD 분석 카드 |
| S2 | `02-match.json` | 역량 매칭 카드 |
| S3 | `03-qa.json` | 예상 질문·답변 카드 |
| S4 | `04-check.json` | 점검 리포트 (중복·사실 불일치) |
| 승인 | `review.md` | 사람이 읽고 승인하는 카드 모음 |
| S5 | `05-index-before.html` | 반영 전 HTML 백업 |
| S5 | `05-changelog.md` | 변경 이력 |
| 상태 | `state.json` | 현재 단계, 되돌아가기 횟수 |

- 단계 출력은 JSON 하나로 둔다. 사람이 읽는 Markdown은 `review.md` 한 곳에만 둔다.
- `CLAUDE.md`는 `rules.json`을 참조만 하고 규칙을 복사하지 않는다.

## 규칙 SSOT (`rules.json`)
- 형식: JSON (스크립트가 직접 읽는다.)
- 담는 것: 카드별 필수 필드, 금지 규칙, 되돌아가기 상한(2회), 통과 조건
- 구체 내용은 R5에서 정한다.

## 재개
- 재개 가능: 예
- 시작 지점: `state.json`의 마지막 통과 단계의 다음 단계
- 필요한 출력 파일이 없으면 해당 단계부터 다시 한다.

## HTML 원본 보호
- S5 시작 전 항상 `05-index-before.html`에 백업한다.
- 백업이 없으면 S5를 진행하지 않는다.
- 백업은 승인 시점의 HTML과 해시가 같아야 한다. (`approved_html_hash`)

## state.json 필드
- 항상: `기업명`, `슬러그`, `단계`, `통과`, `복귀횟수`, `approved`, `approved_at`
- 승인 시 추가: `approved_cards_hash`, `approved_html_hash` (`judge HASH`가 계산한 값을 오케스트레이터가 기록)
- 승인 이후 01~03·review.md가 바뀌면 해시가 달라져 승인이 무효가 된다.

## 통과 조건 (파일 개수로 셀 수 있는 형태)

| 시점 | 실행 폴더에 있어야 할 파일 | 개수 |
|---|---|---|
| S1 통과 | `01-jd-analysis.json`, `state.json` | 2 |
| S2 통과 | + `02-match.json` | 3 |
| S3 통과 | + `03-qa.json` | 4 |
| S4 통과 | + `04-check.json` | 5 |
| 승인 후 | + `review.md` | 6 |
| S5 통과 | + `05-index-before.html`, `05-changelog.md` | 8 |
