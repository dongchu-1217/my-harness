#!/usr/bin/env python3
"""V1 게이트 테스트.

게이트 6개(G1~G5, 승인)마다 통과 1건·실패 1건(핵심 12건)과, 독립 리뷰가 지적한 우회 경로를 막는 추가 케이스를
판정 스크립트로 돌린다. 이 파일의 샘플 데이터는 전부 테스트용이다. 실제 harness/data/에는 쓰지 않는다.

사용법: python3 harness/tests/run_tests.py
"""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
JUDGE = HERE.parent / "scripts" / "judge.py"
sys.path.insert(0, str(JUDGE.parent))
import judge as J  # noqa: E402

RULES = J.load_rules()

# ------------------------------------------------------------ 테스트용 샘플
EXP = {"_테스트용": True, "경험": [
    {"id": "e1", "프로젝트명": "테스트 프로젝트 A", "문제": "테스트 문제 설명", "행동": "테스트 행동 설명",
     "결과": "처리 시간이 6시간에서 1시간으로 줄었다", "회고": "테스트 회고"},
    {"id": "e2", "프로젝트명": "테스트 프로젝트 B", "문제": "테스트 문제 설명 B", "행동": "테스트 행동 설명 B",
     "결과": "전환율이 12% 상승했다", "회고": "테스트 회고 B"}]}
S1 = {"기업명": "테스트기업", "직무명": "테스트 직무", "항목": [
    {"id": "r1", "핵심 역량": "테스트 역량 A", "요구 경험": "테스트 요구 경험 A", "우선순위": "상"},
    {"id": "r2", "핵심 역량": "테스트 역량 B", "요구 경험": "테스트 요구 경험 B", "우선순위": "중"}]}
S2 = {"매칭": [
    {"요구사항 id": "r1", "JD 요구사항": "테스트 요구사항 A (경력 5년 이상)", "상태": "매칭",
     "내 강점": "처리 시간을 6시간에서 1시간으로 줄인 경험", "근거": ["e1"]},
    {"요구사항 id": "r2", "JD 요구사항": "테스트 요구사항 B", "상태": "경험 부족/확인 필요",
     "내 강점": "", "근거": []}]}
S3 = {"카드": [
    {"id": "q1", "질문": "처리 시간을 줄인 경험을 설명해 주세요.", "핵심 키워드": ["문제", "행동", "결과"],
     "근거 사례": ["e1"], "꼬리 질문": ["수치는 어떻게 측정했나요?"]}]}
S4 = {"gate": "G4", "pass": True, "failures": []}
STATE = {"기업명": "테스트기업", "슬러그": "test", "단계": "S4", "통과": ["S1", "S2", "S3", "S4"],
         "복귀횟수": {"S1": 0, "S2": 0, "S3": 0, "S4": 0, "S5": 0},
         "approved": True, "approved_at": "2026-01-01T00:00:00"}
BEFORE_HTML = """<html><body><p>It's a test page</p><script>
const CARDS = [{id:'a',title:'A'},{id:'b',title:'B'}];
const QGROUPS = [['핵심',[['질문1',0,1],'질문2']]];
const GEN = [['x','질문1']];
const FOLLOW = ['q1','q2'];
const FOLLOW_CAT = {'c':['q']};
const PRESS = ['p1'];
// 주석: const COMPANY 는 아래에 있다
const COMPANY = {'기업A':{kw:['k'],qs:['질문1']}};
const LVS = [['🟢','기본']];
</script></body></html>"""
Q1 = "처리 시간을 줄인 경험을 설명해 주세요."
Q2 = "수치는 어떻게 측정했나요?"
AFTER_HTML = (BEFORE_HTML
              .replace("'질문2']]];", "'질문2']],['테스트기업',[['%s',0,0],['%s',1,0]]]];" % (Q1, Q2))
              .replace("{'기업A':{kw:['k'],qs:['질문1']}}",
                       "{'기업A':{kw:['k'],qs:['질문1']},'테스트기업':{kw:['테스트 역량 A','테스트 역량 B'],qs:['%s']}}" % Q1))


def ser(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def apply_hashes(f):
    parts = [(RULES["실행 폴더 파일"]["S1"], ser(f["01"])), (RULES["실행 폴더 파일"]["S2"], ser(f["02"])),
             (RULES["실행 폴더 파일"]["S3"], ser(f["03"])),
             (RULES["실행 폴더 파일"]["승인"], f["review"].encode("utf-8") if f["review"] is not None else None)]
    if isinstance(f["state"], dict):
        f["state"]["approved_cards_hash"] = J.cards_digest(parts)
        f["state"]["approved_html_hash"] = hashlib.sha256(BEFORE_HTML.encode("utf-8")).hexdigest()


def base():
    f = {"exp": copy.deepcopy(EXP), "01": copy.deepcopy(S1), "02": copy.deepcopy(S2),
         "03": copy.deepcopy(S3), "04": copy.deepcopy(S4), "state": copy.deepcopy(STATE),
         "review": "# 테스트 review\n", "backup": BEFORE_HTML, "changelog": "# 테스트 변경 이력\n",
         "html": AFTER_HTML}
    apply_hashes(f)
    return f


def write(tmp, f):
    run = tmp / "run"
    run.mkdir()
    for key, name in [("01", "01-jd-analysis.json"), ("02", "02-match.json"), ("03", "03-qa.json"),
                      ("04", "04-check.json"), ("state", "state.json")]:
        if f.get(key) is not None:
            (run / name).write_bytes(ser(f[key]))
    for key, name in [("review", "review.md"), ("backup", "05-index-before.html"),
                      ("changelog", "05-changelog.md")]:
        if f.get(key) is not None:
            (run / name).write_text(f[key], encoding="utf-8")
    (tmp / "experiences.json").write_bytes(ser(f["exp"]))
    (tmp / "index.html").write_text(f["html"], encoding="utf-8")
    return run


# ------------------------------------------------------------ 케이스
CASES = []


def case(name, gate, expect_pass, mutate=None, contains=None, star=False, core=False, return_to=None,
         exit_code=None):
    CASES.append(dict(name=name, gate=gate, expect_pass=expect_pass, mutate=mutate, contains=contains,
                      star=star, core=core, return_to=return_to, exit_code=exit_code))


def s2_strength(text):
    def m(f): f["02"]["매칭"][0]["내 강점"] = text
    return m


def s3_keyword(text):
    def m(f): f["03"]["카드"][0]["핵심 키워드"] = [text]
    return m


def html_replace(old, new):
    def m(f):
        assert old in f["html"], "테스트 설정 오류: %r" % old
        f["html"] = f["html"].replace(old, new)
    return m


def m_drop_priority(f): del f["01"]["항목"][0]["우선순위"]
def m_no_state(f): f["state"] = None
def m_bad_ref(f): f["02"]["매칭"][0]["근거"] = ["e999"]
def m_ref_nested(f): f["02"]["매칭"][0]["근거"] = [["e1"]]
def m_no_exp(f): f["exp"]["경험"] = []
def m_uncovered(f): f["02"]["매칭"] = f["02"]["매칭"][:1]
def m_shortage_filled(f): f["02"]["매칭"][1]["내 강점"] = "전사 A 주도"
def m_no_tail(f): f["03"]["카드"][0]["꼬리 질문"] = []
def m_blank_keyword(f): f["03"]["카드"][0]["핵심 키워드"] = [""]
def m_extra_key(f): f["03"]["카드"][0]["근거"] = "매출 300% 증가"
def m_bad_id(f): f["03"]["카드"][0]["id"] = "q1 매출 300%"
def m_dup_q(f): f["03"]["카드"].append(dict(f["03"]["카드"][0], id="q2"))
def m_other_exp_number(f): f["03"]["카드"][0]["핵심 키워드"] = ["전환율 12% 상승"]
def m_no_approval(f): f["state"]["approved"] = False
def m_state_list(f): f["state"] = []
def m_no_s4(f): f["state"]["통과"] = ["S1", "S2", "S3"]
def m_bad_at(f): f["state"]["approved_at"] = "x"
def m_empty_review(f): f["review"] = "  \n"; apply_hashes(f)
def m_edit_after_approval(f): f["03"]["카드"][0]["꼬리 질문"] = ["수정된 꼬리 질문"]
def m_forged_check(f):
    f["03"]["카드"][0]["질문"] = "매출 300% 올린 경험을 설명해 주세요."
    apply_hashes(f)
def m_no_backup(f): f["backup"] = None
def m_backup_swap(f): f["backup"] = AFTER_HTML.replace("'q1','q2'", "'q1'")
def m_json_script(f): f["html"] = f["html"].replace("</body>", '<script type="application/json">{"a":1}</script></body>')
def m_state_count_str(f): f["state"]["복귀횟수"]["S2"] = "9"
def m_state_limit(f): f["state"]["복귀횟수"]["S2"] = 3
def m_mark(f): f["02"]["매칭"][0]["내 강점"] = "확인 필요: 수치 미확인"
def m_exp_missing(f): del f["exp"]["경험"][0]["회고"]
def m_exp_blank(f): f["exp"]["경험"][0]["결과"] = ""
def m_exp_dup(f): f["exp"]["경험"][1]["id"] = "e1"

# --- 핵심 12케이스 (게이트별 통과 1 + 실패 1)
case("G1 통과", "G1", True, core=True)
case("G1 실패: 우선순위 없음", "G1", False, m_drop_priority, "우선순위", core=True)
case("G2 통과", "G2", True, core=True)
case("G2 실패: 없는 경험 id 참조 ★", "G2", False, m_bad_ref, "존재하지 않는 경험 id", star=True, core=True,
     return_to="S2")
case("G3 통과", "G3", True, core=True)
case("G3 실패: 꼬리 질문 없음", "G3", False, m_no_tail, "꼬리 질문", core=True)
case("G4 통과 (JD 요구사항의 '5년'은 제외)", "G4", True, core=True)
case("G4 실패: 원문에 없는 수치 ★", "G4", False, s2_strength("처리 시간을 50% 줄인 경험"), "50%", star=True,
     core=True, return_to="S2")
case("승인 통과", "APPROVAL", True, core=True)
case("승인 실패: 승인 기록 없음 ★", "APPROVAL", False, m_no_approval, "승인 기록 없음", star=True, core=True)
case("G5 통과", "G5", True, core=True)
case("G5 실패: 기존 항목이 사라짐", "G5", False, html_replace("['q1','q2']", "['q1']"), "기존 내용", core=True,
     return_to="S5")

# --- G1~G3 추가
case("G1 실패: state.json 없음", "G1", False, m_no_state, "필수 파일 없음")
case("G2 실패: 경험 0건", "G2", False, m_no_exp, "0건")
case("G2 실패: 미분류 요구사항", "G2", False, m_uncovered, "미분류")
case("G2 실패: 경험 부족인데 내 강점이 채워짐", "G2", False, m_shortage_filled, "채워져 있음")
case("G2 실패: 근거가 중첩 목록 (크래시 없이 실패)", "G2", False, m_ref_nested, "문자열의 목록", exit_code=1)
case("G3 실패: 핵심 키워드가 빈 문자열", "G3", False, m_blank_keyword, "핵심 키워드")
case("G3 실패: 스키마 밖 키에 허위 수치", "G3", False, m_extra_key, "스키마 밖 키")
case("G3 실패: id에 허위 수치", "G3", False, m_bad_id, "id가 없거나 형식")

# --- G4 추가 (수치 추출 우회, 인용 경험 기준, 용어 대조)
case("G4 실패: 03의 원문에 없는 수치는 S3로 복귀", "G4", False, s3_keyword("30건 처리"), "30건", return_to="S3")
case("G4 실패: 중복 질문", "G4", False, m_dup_q, "중복", return_to="S3")
case("G4 실패: 영문 뒤 숫자 (MAU500만)", "G4", False, s2_strength("MAU500만 달성"), "500만")
case("G4 실패: 쉼표 뒤 공백 없는 숫자", "G4", False, s2_strength("6시간,99% 단축"), "99%")
case("G4 실패: 미등록 단위 (1달러)", "G4", False, s2_strength("비용 1달러 절감"), "1달러")
case("G4 실패: 인용하지 않은 다른 경험의 수치", "G4", False, m_other_exp_number, "12%", return_to="S3")
case("G4 실패: 원문에 없는 A/B 테스트", "G4", False, s2_strength("A/B 테스트를 주도한 경험"), "A/B")
case("G4 실패: 공백 뒤 단어를 단위로 합치지 않음", "G4", False, s2_strength("상위 3 주요 지표"), "'3'")
case("G4 통과: 원문의 '6시간'을 '6 시간'으로 띄어 씀", "G4", True, s2_strength("처리 시간을 6 시간에서 1 시간으로 줄인 경험"))

# --- 승인 추가
case("승인 실패: 04를 손으로 통과시키고 03에 허위 수치 ★", "APPROVAL", False, m_forged_check, "G4 재판정", star=True)
case("승인 실패: 승인 이후 카드가 바뀜 ★", "APPROVAL", False, m_edit_after_approval, "승인 이후", star=True)
case("승인 실패: state.json의 통과에 S4 없음", "APPROVAL", False, m_no_s4, "S4")
case("승인 실패: 승인 시각 형식 오류", "APPROVAL", False, m_bad_at, "approved_at")
case("승인 실패: review.md가 비어 있음", "APPROVAL", False, m_empty_review, "비어 있음")
case("승인 실패: state.json이 목록 (크래시 없이 실패)", "APPROVAL", False, m_state_list, "객체가 아님", exit_code=1)

# --- G5 추가
case("G5 통과: application/json script 블록이 있어도", "G5", True, m_json_script)
case("G5 실패: 승인 없이 반영 ★", "G5", False, m_no_approval, "승인 재확인", star=True)
case("G5 실패: 승인된 카드에 없는 항목 추가 ★", "G5", False,
     html_replace("['" + Q2 + "',1,0]", "['" + Q2 + "',1,0],['매출 300% 올린 경험',0,0]"), "승인된 카드에 없는 항목",
     star=True)
case("G5 실패: 기존 카드 내용 변조 (id 유지)", "G5", False, html_replace("{id:'a',title:'A'}", "{id:'a',title:'변조됨'}"),
     "기존 내용")
case("G5 실패: 기존 질문의 레벨·자주 나옴 변경", "G5", False, html_replace("['질문1',0,1]", "['질문1',2,0]"), "기존 내용")
case("G5 실패: 선언 밖 대입으로 기존 키 덮어쓰기", "G5", False,
     html_replace("const LVS", "COMPANY['기업A']={kw:['덮어씀'],qs:[]};\nconst LVS"), "선언 밖")
case("G5 실패: 선언 안에서 기존 키 덮어쓰기", "G5", False,
     html_replace("'기업A':{kw:['k'],qs:['질문1']}", "'기업A':{kw:['덮어씀'],qs:[]}"), "기존 내용")
case("G5 실패: 기존 상수를 주석 처리", "G5", False, html_replace("const PRESS = ['p1'];", "/* const PRESS = ['p1']; */"),
     "PRESS")
case("G5 실패: CARDS 기존 id가 사라짐", "G5", False, html_replace("{id:'a',title:'A'},", ""), "기존 내용")
case("G5 실패: 구문 오류", "G5", False, html_replace("const PRESS = ['p1'];", "const PRESS = ['p1';"), "구문 오류")
case("G5 실패: 백업 없음", "G5", False, m_no_backup, "05-index-before.html")
case("G5 실패: 백업을 변경 후 HTML로 교체", "G5", False, m_backup_swap, "백업이 승인 시점의 HTML과 다름")

# --- 보조 점검
case("pre-S2 통과", "pre-S2", True)
case("pre-S2 실패: 경험 0건", "pre-S2", False, m_no_exp, "0건")
case("pre-S2 실패: 경험 카드 필드 누락", "pre-S2", False, m_exp_missing, "회고")
case("pre-S2 실패: 경험 카드 값이 비어 있음", "pre-S2", False, m_exp_blank, "결과")
case("pre-S2 실패: 경험 id 중복", "pre-S2", False, m_exp_dup, "id 중복")
case("pre-review 통과 (경험 부족 상태는 허용)", "pre-review", True)
case("pre-review 실패: '확인 필요' 표시", "pre-review", False, m_mark, "확인 필요")
case("STATE 통과", "STATE", True)
case("STATE 실패: 되돌아가기 상한 초과", "STATE", False, m_state_limit, "상한")
case("STATE 실패: 횟수가 문자열", "STATE", False, m_state_count_str, "정수")


def run_case(c):
    f = base()
    if c["mutate"]:
        c["mutate"](f)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        run = write(tmp, f)
        cmd = [sys.executable, str(JUDGE), c["gate"]]
        if c["gate"] != "pre-S2":
            cmd.append(str(run))
        cmd += ["--experiences", str(tmp / "experiences.json"), "--html", str(tmp / "index.html")]
        r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        out = json.loads(r.stdout)
    except ValueError:
        return False, "JSON이 아닌 출력 (종료 코드 %s): %s" % (r.returncode, (r.stdout + r.stderr)[:200])
    want_exit = c["exit_code"] if c["exit_code"] is not None else (0 if c["expect_pass"] else 1)
    if out["pass"] != c["expect_pass"] or r.returncode != want_exit:
        return False, "기대 pass=%s exit=%s, 실제 pass=%s exit=%s %s" % (
            c["expect_pass"], want_exit, out["pass"], r.returncode, out["failures"][:2])
    if c["contains"] and not any(c["contains"] in x for x in out["failures"]):
        return False, "실패 사유에 '%s'가 없음: %s" % (c["contains"], out["failures"][:3])
    if c["return_to"] and out.get("return_to") != c["return_to"]:
        return False, "return_to 기대 %s, 실제 %s" % (c["return_to"], out.get("return_to"))
    return True, ""


def main():
    results = [(c, run_case(c)) for c in CASES]
    for c, (ok, why) in results:
        print("%s %s%s" % ("PASS" if ok else "FAIL", c["name"], "" if ok else "  → " + why))
    core = [ok for c, (ok, _) in results if c["core"]]
    star = [ok for c, (ok, _) in results if c["star"]]
    allok = [ok for _, (ok, _) in results]
    print("\n핵심 케이스: %d/%d 통과" % (sum(core), len(core)))
    print("★ 위반 조건 케이스: %d/%d 걸림" % (sum(star), len(star)))
    print("전체: %d/%d 통과" % (sum(allok), len(allok)))
    return 0 if all(allok) else 1


if __name__ == "__main__":
    sys.exit(main())
