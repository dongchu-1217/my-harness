#!/usr/bin/env python3
"""읽기 전용 판정 스크립트.

harness/gates.md의 게이트를 스크립트가 셀 수 있는 조건으로 판정한다.
규칙은 harness/rules.json에서 읽고, 어떤 파일도 수정하지 않는다.
결과는 JSON으로 출력만 한다. 기록은 오케스트레이터가 한다.

사용법:
  python3 harness/scripts/judge.py <게이트> <실행 폴더> [--experiences 경로] [--html 경로]
  게이트: G1 G2 G3 G4 APPROVAL G5 pre-S2 pre-review STATE HASH
종료 코드: 0 통과, 1 실패, 2 입력 형식 오류
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "harness" / "rules.json"


# ---------------------------------------------------------------- 공통
def load_rules():
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def read_json(path):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "파일 없음: %s" % path.name
    except ValueError as e:
        return None, "JSON 오류: %s (%s)" % (path.name, e)


def empty(v):
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, list):
        return len(v) == 0 or all(empty(x) for x in v)
    if isinstance(v, dict):
        return len(v) == 0 or all(empty(x) for x in v.values())
    return False


def rf(rules, key):
    return rules["실행 폴더 파일"][key]


def list_of(data, key):
    items = data.get(key) if isinstance(data, dict) else None
    return items if isinstance(items, list) else None


def load_experiences(rules, override):
    path = Path(override) if override else ROOT / rules["경로"]["경험 카드"]
    data, err = read_json(path)
    if err:
        return [], err
    items = list_of(data, rules["경험 카드"]["목록 키"])
    if items is None:
        return [], "경험 카드 목록('%s')이 없음" % rules["경험 카드"]["목록 키"]
    return items, None


def exp_by_id(items, rules):
    key = rules["경험 카드"]["id 키"]
    return dict((i[key], i) for i in items
                if isinstance(i, dict) and isinstance(i.get(key), str) and not empty(i.get(key)))


def key_failures(obj, allowed, label):
    return ["%s: 스키마 밖 키 '%s'" % (label, k) for k in obj if k not in allowed]


def id_ok(v, rules):
    return isinstance(v, str) and re.match(rules["id 형식"], v) is not None


def check_refs(it, key, ids, label, f):
    """근거 목록이 경험 id 문자열의 목록이고, 모두 실제로 존재하는지 확인한다."""
    refs = it.get(key, [])
    if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
        f.append("%s: '%s'는 경험 id 문자열의 목록이어야 함" % (label, key))
        return []
    for ref in refs:
        if ref not in ids:
            f.append("%s: 존재하지 않는 경험 id '%s' 참조" % (label, ref))
    return refs


def missing_files(run, rules, gate):
    names = rules["통과 시 있어야 할 파일"].get(gate, [])
    return ["필수 파일 없음: %s" % rf(rules, n) for n in names if not (run / rf(rules, n)).is_file()]


# ---------------------------------------------------------------- 해시
def cards_digest(parts):
    """parts: [(파일 이름, 바이트 또는 None)]"""
    h = hashlib.sha256()
    for name, data in parts:
        h.update(name.encode("utf-8"))
        h.update(b"\0" + (data if data is not None else b"<missing>") + b"\0")
    return h.hexdigest()


def compute_hashes(run, rules, html_path):
    parts = []
    for key in ("S1", "S2", "S3", "승인"):
        p = run / rf(rules, key)
        parts.append((rf(rules, key), p.read_bytes() if p.is_file() else None))
    html = Path(html_path) if html_path else ROOT / rules["경로"]["인덱스 HTML"]
    html_hash = hashlib.sha256(html.read_bytes()).hexdigest() if html.is_file() else None
    return {"cards_hash": cards_digest(parts), "html_hash": html_hash}


# ---------------------------------------------------------------- G1
def g1(run, rules, exp_path, html_path):
    cfg = rules["카드"]["JD 분석 카드"]
    f = missing_files(run, rules, "G1")
    data, err = read_json(run / rf(rules, "S1"))
    if err:
        return f + [err], {}
    if not isinstance(data, dict):
        return f + ["01 파일이 객체가 아님"], {}
    f += key_failures(data, cfg["허용 키"]["최상위"], "최상위")
    for k in cfg["최상위 필수"]:
        if empty(data.get(k)):
            f.append("최상위: '%s' 비어 있음" % k)
    items = list_of(data, cfg["목록 키"])
    if not items:
        return f + ["'%s'가 1개 이상 필요" % cfg["목록 키"]], {}
    seen = set()
    for i, it in enumerate(items):
        label = "%s[%d]" % (cfg["목록 키"], i)
        if not isinstance(it, dict):
            f.append("%s: 객체가 아님" % label)
            continue
        f += key_failures(it, cfg["허용 키"]["항목"], label)
        iid = it.get(cfg["id 키"])
        if not id_ok(iid, rules):
            f.append("%s: id가 없거나 형식이 맞지 않음" % label)
        elif iid in seen:
            f.append("%s: id 중복 (%s)" % (label, iid))
        else:
            seen.add(iid)
        for k in cfg["필수 필드"]:
            if empty(it.get(k)):
                f.append("%s: '%s' 비어 있음" % (label, k))
        pr = it.get("우선순위")
        if not empty(pr) and pr not in cfg["허용 값"]["우선순위"]:
            f.append("%s: 우선순위 '%s'는 허용 값이 아님" % (label, pr))
    return f, {}


# ---------------------------------------------------------------- G2
def g2(run, rules, exp_path, html_path):
    cfg = rules["카드"]["역량 매칭 카드"]
    jd_cfg = rules["카드"]["JD 분석 카드"]
    f = missing_files(run, rules, "G2")
    extra = {}
    experiences, err = load_experiences(rules, exp_path)
    ids = exp_by_id(experiences, rules)
    if err or not ids:
        f.append(err or "저장된 경험 카드가 0건")
        extra["중단"] = True
    jd, err = read_json(run / rf(rules, "S1"))
    jd_items = list_of(jd, jd_cfg["목록 키"]) if not err else None
    jd_items = jd_items or []
    data, err = read_json(run / rf(rules, "S2"))
    if err:
        return f + [err], extra
    if not isinstance(data, dict):
        return f + ["02 파일이 객체가 아님"], extra
    f += key_failures(data, cfg["허용 키"]["최상위"], "최상위")
    items = list_of(data, cfg["목록 키"])
    if items is None:
        return f + ["'%s'가 없음" % cfg["목록 키"]], extra
    status = cfg["상태 값"]
    allowed = [status["매칭"], status["부족"]]
    covered = set()
    for i, it in enumerate(items):
        label = "%s[%d]" % (cfg["목록 키"], i)
        if not isinstance(it, dict):
            f.append("%s: 객체가 아님" % label)
            continue
        f += key_failures(it, cfg["허용 키"]["항목"], label)
        rid = it.get(cfg["요구사항 id 키"])
        if not id_ok(rid, rules):
            f.append("%s: '%s'가 없거나 형식이 맞지 않음" % (label, cfg["요구사항 id 키"]))
        else:
            covered.add(rid)
        for k in cfg["필수 필드"]:
            if empty(it.get(k)):
                f.append("%s: '%s' 비어 있음" % (label, k))
        st = it.get("상태")
        if not empty(st) and st not in allowed:
            f.append("%s: 분류 안 됨 (상태 '%s')" % (label, st))
        if st == status["매칭"]:
            for k in cfg["매칭일 때 필수"]:
                if empty(it.get(k)):
                    f.append("%s: 상태가 '매칭'인데 '%s'가 비어 있음" % (label, k))
        if st == status["부족"]:
            for k in cfg["부족일 때 비어 있어야 함"]:
                if not empty(it.get(k)):
                    f.append("%s: 상태가 '%s'인데 '%s'가 채워져 있음" % (label, status["부족"], k))
        check_refs(it, cfg["근거 키"], ids, label, f)
    jd_ids = set(i.get(jd_cfg["id 키"]) for i in jd_items if isinstance(i, dict))
    for rid in sorted(x for x in jd_ids if isinstance(x, str) and x not in covered):
        f.append("미분류 요구사항: %s" % rid)
    return f, extra


# ---------------------------------------------------------------- G3
def g3(run, rules, exp_path, html_path):
    cfg = rules["카드"]["예상 질문·답변 카드"]
    f = missing_files(run, rules, "G3")
    data, err = read_json(run / rf(rules, "S3"))
    if err:
        return f + [err], {}
    if not isinstance(data, dict):
        return f + ["03 파일이 객체가 아님"], {}
    f += key_failures(data, cfg["허용 키"]["최상위"], "최상위")
    items = list_of(data, cfg["목록 키"])
    if not items:
        return f + ["'%s'가 1개 이상 필요" % cfg["목록 키"]], {}
    experiences, err = load_experiences(rules, exp_path)
    ids = exp_by_id(experiences, rules)
    if err or not ids:
        f.append(err or "저장된 경험 카드가 0건")
    seen = set()
    for i, it in enumerate(items):
        label = "%s[%d]" % (cfg["목록 키"], i)
        if not isinstance(it, dict):
            f.append("%s: 객체가 아님" % label)
            continue
        f += key_failures(it, cfg["허용 키"]["항목"], label)
        qid = it.get(cfg["id 키"])
        if not id_ok(qid, rules):
            f.append("%s: id가 없거나 형식이 맞지 않음" % label)
        elif qid in seen:
            f.append("%s: id 중복 (%s)" % (label, qid))
        else:
            seen.add(qid)
        for k in cfg["필수 필드"]:
            if empty(it.get(k)):
                f.append("%s: '%s' 비어 있음" % (label, k))
        check_refs(it, cfg["근거 키"], ids, label, f)
    return f, {}


# ---------------------------------------------------------------- G4
def walk_strings(obj, skip_keys, path="", top=True):
    """문자열 값을 (경로, 문자열)로 훑는다. skip_keys는 최상위 키에만 적용한다."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if top and k in skip_keys:
                continue
            sub = "%s.%s" % (path, k) if path else k
            for x in walk_strings(v, skip_keys, sub, False):
                yield x
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            for x in walk_strings(v, skip_keys, "%s[%d]" % (path, i), False):
                yield x
    elif isinstance(obj, str):
        yield path, obj


def unit_alternatives(rules):
    units = sorted(rules["수치 검증"]["단위"], key=len, reverse=True)
    return "|".join(re.escape(u) for u in units)


def collapse_spaces(text, unit_alt):
    return re.sub(r"(\d)\s+(?=%%|(?:%s))" % unit_alt, r"\1", text)


def number_tokens(text, unit_alt):
    pat = re.compile(r"(?<![0-9])(\d+(?:[.,]\d+)*)(%s)?" % unit_alt)
    tokens = []
    for m in pat.finditer(text):
        num, unit = m.group(1), m.group(2)
        if unit:
            tokens.append(num + unit)
            continue
        nxt = re.match(r"[A-Za-z가-힣]{1,2}", text[m.end():m.end() + 2])
        tokens.append(num + nxt.group(0) if nxt else num)
    return tokens


def token_in(tok, corpus):
    pat = r"(?<![0-9])" + re.escape(tok) + r"(?![0-9]|[.,][0-9])"
    return re.search(pat, corpus) is not None


def norm_question(s):
    return re.sub(r"[\s\W_]+", "", s).lower()


def g4(run, rules, exp_path, html_path):
    f = missing_files(run, rules, "G4")
    experiences, err = load_experiences(rules, exp_path)
    if err:
        return f + [err], {"return_to": "S2"}
    by_id = exp_by_id(experiences, rules)
    unit_alt = unit_alternatives(rules)
    vcfg = rules["수치 검증"]
    skip = set(vcfg["검사 제외 키"])
    mism = {"S2": [], "S3": []}
    dup = []
    for stage, card in vcfg["대상"].items():
        ccfg = rules["카드"][card]
        fname = rf(rules, stage)
        data, err = read_json(run / fname)
        if err:
            f.append(err)
            continue
        for i, it in enumerate(list_of(data, ccfg["목록 키"]) or []):
            if not isinstance(it, dict):
                continue
            refs = it.get(ccfg["근거 키"])
            refs = [r for r in refs if isinstance(r, str)] if isinstance(refs, list) else []
            raw = "\n".join(s for r in refs if r in by_id for _, s in walk_strings(by_id[r], set()))
            collapsed = collapse_spaces(raw, unit_alt)
            for path, text in walk_strings(it, skip):
                where = "%s %s[%d].%s" % (fname, ccfg["목록 키"], i, path)
                for tok in number_tokens(text, unit_alt):
                    if not (token_in(tok, raw) or token_in(tok, collapsed)):
                        mism[stage].append("%s: '%s'가 근거로 인용한 경험 카드 원문에 없음" % (where, tok))
                for term in vcfg["원문 대조 용어"]:
                    if term in text and term not in raw:
                        mism[stage].append("%s: '%s'가 근거로 인용한 경험 카드 원문에 없음" % (where, term))
    qcfg = rules["카드"]["예상 질문·답변 카드"]
    data, err = read_json(run / rf(rules, "S3"))
    if not err:
        seen = {}
        for i, it in enumerate(list_of(data, qcfg["목록 키"]) or []):
            q = it.get("질문") if isinstance(it, dict) else None
            if isinstance(q, str) and q.strip():
                key = norm_question(q)
                if key in seen:
                    dup.append("%s[%d]가 %s[%d]와 같은 질문" % (qcfg["목록 키"], i, qcfg["목록 키"], seen[key]))
                else:
                    seen[key] = i
    all_m = mism["S2"] + mism["S3"]
    f = f + ["사실 불일치: " + m for m in all_m] + ["중복: " + d for d in dup]
    return_to = "S2" if mism["S2"] else ("S3" if (mism["S3"] or dup) else None)
    extra = {"원문에 없는 수치": all_m, "중복 질문": dup}
    if return_to:
        extra["return_to"] = return_to
    return f, extra


# ---------------------------------------------------------------- 승인
def approval(run, rules, exp_path, html_path):
    f = missing_files(run, rules, "승인")
    state, err = read_json(run / rf(rules, "상태"))
    if err or not isinstance(state, dict):
        return f + [err or "state.json이 객체가 아님"], {"중단": True}
    passed = state.get("통과")
    for st in ("S1", "S2", "S3", "S4"):
        if not (isinstance(passed, list) and st in passed):
            f.append("state.json의 통과에 %s가 없음" % st)
    if state.get("approved") is not True:
        f.append("승인 기록 없음 (approved가 true가 아님)")
    at = state.get("approved_at")
    if not (isinstance(at, str) and re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", at)):
        f.append("승인 시각(approved_at)이 없거나 형식이 맞지 않음")
    review = run / rf(rules, "승인")
    if review.is_file() and not review.read_text(encoding="utf-8").strip():
        f.append("review.md가 비어 있음")
    cur = compute_hashes(run, rules, html_path)
    if state.get("approved_cards_hash") != cur["cards_hash"]:
        f.append("승인 이후 카드나 review.md가 바뀌었거나 승인 시 해시가 기록되지 않음")
    chk, err = read_json(run / rf(rules, "S4"))
    if err:
        f.append(err)
    elif not (isinstance(chk, dict) and chk.get("pass") is True):
        f.append("S4 점검 결과가 통과가 아님")
    # 04-check.json은 자기보고 파일이므로 G1~G4를 승인 시점에 다시 판정한다.
    for name, fn in (("G1", g1), ("G2", g2), ("G3", g3), ("G4", g4)):
        sub, _ = fn(run, rules, exp_path, html_path)
        f += ["%s 재판정: %s" % (name, x) for x in sub]
    return f, ({"중단": True} if f else {})


# ---------------------------------------------------------------- G5
def skip_string(src, i):
    q = src[i]
    i += 1
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if q == "`" and c == "$" and src[i + 1:i + 2] == "{":
            i = skip_braces(src, i + 1)
            continue
        if c == q:
            return i + 1
        i += 1
    return n


def skip_braces(src, i):
    depth, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"`":
            i = skip_string(src, i)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def strip_comments(src):
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"`":
            j = skip_string(src, i)
            out.append(src[i:j])
            i = j
            continue
        if src.startswith("//", i) and src[i - 1:i] != ":":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def extract_const(src, name):
    m = re.search(r"(?m)^\s*const\s+%s\s*=\s*" % re.escape(name), src)
    if not m:
        return None
    i, start, depth, n = m.end(), m.end(), 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"`":
            i = skip_string(src, i)
            continue
        if c in "[{(":
            depth += 1
        elif c in "]})":
            depth -= 1
        elif c == ";" and depth == 0:
            return src[start:i]
        i += 1
    return src[start:]


EVAL_JS = (
    "const vm=require('vm');let d='';"
    "process.stdin.on('data',c=>d+=c).on('end',()=>{const b=JSON.parse(d);const o={};"
    "for(const [k,v] of Object.entries(b)){try{o[k]={ok:true,v:vm.runInNewContext('('+v+')',{},{timeout:1000})}}"
    "catch(e){o[k]={ok:false,e:String(e)}}}console.log(JSON.stringify(o))})"
)


def eval_blocks(blocks):
    node = shutil.which("node")
    if not node:
        return None, "node가 없어 상수를 평가할 수 없음"
    r = subprocess.run([node, "-e", EVAL_JS], input=json.dumps(blocks), text=True, capture_output=True)
    if r.returncode != 0:
        return None, "상수 평가 실패: %s" % r.stderr.strip()[:200]
    return json.loads(r.stdout), None


def contains(b, a, path=""):
    """before(b)의 내용이 after(a)에 그대로 남아 있으면 (True, None), 아니면 (False, 경로)."""
    if isinstance(b, dict):
        if not isinstance(a, dict):
            return False, path or "."
        for k, v in b.items():
            if k not in a:
                return False, "%s.%s" % (path, k)
            ok, p = contains(v, a[k], "%s.%s" % (path, k))
            if not ok:
                return False, p
        return True, None
    if isinstance(b, list):
        if not isinstance(a, list):
            return False, path or "."
        j = 0
        for i, v in enumerate(b):
            while j < len(a):
                ok, _ = contains(v, a[j])
                j += 1
                if ok:
                    break
            else:
                return False, "%s[%d]" % (path, i)
        return True, None
    return (True, None) if b == a else (False, path or ".")


def leaf_strings(val, counter, top=True):
    if isinstance(val, dict):
        for k, v in val.items():
            if top:
                counter[k] += 1
            leaf_strings(v, counter, False)
    elif isinstance(val, list):
        for v in val:
            leaf_strings(v, counter, False)
    elif isinstance(val, str):
        counter[val] += 1


def mutation_count(src, name):
    n = re.escape(name)
    pats = [r"\b%s\s*\[[^\]]*\]\s*=(?!=)" % n,
            r"\b%s\s*\.\s*\w+\s*=(?!=)" % n,
            r"\b%s\s*\.\s*(?:push|splice|pop|shift|unshift|sort|reverse|fill|copyWithin)\s*\(" % n,
            r"Object\s*\.\s*assign\s*\(\s*%s\b" % n,
            r"\bdelete\s+%s\b" % n,
            r"\b%s\s*=(?!=)" % n]
    return sum(len(re.findall(p, src)) for p in pats)


def js_scripts(src):
    out = []
    for attrs, code in re.findall(r"<script([^>]*)>(.*?)</script>", src, re.S | re.I):
        if re.search(r"\bsrc\s*=", attrs, re.I):
            continue
        t = re.search(r"\btype\s*=\s*[\"']([^\"']*)[\"']", attrs, re.I)
        if t and t.group(1).strip().lower() not in ("", "text/javascript", "application/javascript"):
            continue
        out.append(code)
    return out


def syntax_failures(src):
    node = shutil.which("node")
    if not node:
        return ["node가 없어 구문 검사를 할 수 없음"]
    scripts = js_scripts(src)
    if not scripts:
        return ["인라인 script를 찾지 못함"]
    f = []
    for i, code in enumerate(scripts):
        r = subprocess.run([node, "--check", "-"], input=code, text=True, capture_output=True)
        if r.returncode != 0:
            msg = r.stderr.strip().splitlines() or ["구문 오류"]
            f.append("script[%d] 구문 오류: %s" % (i, " / ".join(msg[:4])))
    return f


def allowed_card_strings(run, rules):
    out = set()
    for key in ("S1", "S3"):
        data, err = read_json(run / rf(rules, key))
        if not err:
            out |= set(s for _, s in walk_strings(data, set()))
    return out


def html_failures(before, after, run, rules):
    cfg = rules["인덱스 HTML 보존"]
    names = cfg["추적 상수"]
    b_src = strip_comments("\n".join(js_scripts(before)))
    a_src = strip_comments("\n".join(js_scripts(after)))
    b_blocks = dict((n, extract_const(b_src, n)) for n in names)
    a_blocks = dict((n, extract_const(a_src, n)) for n in names)
    f = []
    for n in names:
        if b_blocks[n] is not None and a_blocks[n] is None:
            f.append("상수 %s가 사라짐 (주석 처리 포함)" % n)
        if mutation_count(a_src, n) > mutation_count(b_src, n):
            f.append("상수 %s를 선언 밖에서 고침 (선언 안에서만 추가해야 함)" % n)
    if f:
        return f
    b_val, err = eval_blocks(dict((n, v) for n, v in b_blocks.items() if v is not None))
    if err:
        return [err]
    a_val, err = eval_blocks(dict((n, v) for n, v in a_blocks.items() if v is not None))
    if err:
        return [err]
    allowed = allowed_card_strings(run, rules)
    for n in names:
        if n not in b_val:
            continue
        if not b_val[n]["ok"]:
            f.append("반영 전 %s를 평가하지 못함: %s" % (n, b_val[n]["e"][:80]))
            continue
        if not a_val[n]["ok"]:
            f.append("반영 후 %s를 평가하지 못함: %s" % (n, a_val[n]["e"][:80]))
            continue
        ok, where = contains(b_val[n]["v"], a_val[n]["v"], n)
        if not ok:
            f.append("기존 내용이 바뀌거나 사라짐: %s" % where)
        cb, ca = Counter(), Counter()
        leaf_strings(b_val[n]["v"], cb)
        leaf_strings(a_val[n]["v"], ca)
        for s in sorted((ca - cb).keys()):
            if s not in allowed:
                f.append("승인된 카드에 없는 항목이 추가됨: %s '%s'" % (n, s[:50]))
    return f


def g5(run, rules, exp_path, html_path):
    f = missing_files(run, rules, "G5")
    sub, _ = approval(run, rules, exp_path, html_path)
    f += ["승인 재확인: " + x for x in sub]
    extra = {"중단": True} if sub else {}
    html = Path(html_path) if html_path else ROOT / rules["경로"]["인덱스 HTML"]
    if not html.is_file():
        return f + ["파일 없음: %s" % html.name], extra
    after = html.read_text(encoding="utf-8")
    f += syntax_failures(after)
    backup = run / rf(rules, "S5 백업")
    if backup.is_file():
        state, _ = read_json(run / rf(rules, "상태"))
        want = state.get("approved_html_hash") if isinstance(state, dict) else None
        if hashlib.sha256(backup.read_bytes()).hexdigest() != want:
            f.append("백업이 승인 시점의 HTML과 다름 (approved_html_hash 불일치)")
        else:
            f += html_failures(backup.read_text(encoding="utf-8"), after, run, rules)
    return f, extra


# ---------------------------------------------------------------- 보조 점검
def hash_gate(run, rules, exp_path, html_path):
    f = missing_files(run, rules, "승인")
    f = [x for x in f if "04-check" not in x and "state.json" not in x]
    h = compute_hashes(run, rules, html_path)
    if h["html_hash"] is None:
        f.append("인덱스 HTML 파일 없음")
    return f, {"approved_cards_hash": h["cards_hash"], "approved_html_hash": h["html_hash"]}


def pre_s2(run, rules, exp_path, html_path):
    items, err = load_experiences(rules, exp_path)
    ids = exp_by_id(items, rules)
    if err or not ids:
        return [err or "저장된 경험 카드가 0건: 경험 추가를 요청"], {"중단": True}
    f, seen = [], set()
    key = rules["경험 카드"]["id 키"]
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            f.append("경험[%d]: 객체가 아님" % i)
            continue
        iid = it.get(key)
        if not id_ok(iid, rules):
            f.append("경험[%d]: id가 없거나 형식이 맞지 않음" % i)
        elif iid in seen:
            f.append("경험[%d]: id 중복 (%s)" % (i, iid))
        else:
            seen.add(iid)
        for k in rules["경험 카드"]["필수 필드"]:
            if empty(it.get(k)):
                f.append("경험[%d]: '%s'가 없거나 비어 있음 (불확실하면 '%s'로 표시)" % (i, k, rules["확인 필요 표시"]))
    return f, ({"중단": True} if f else {})


def pre_review(run, rules, exp_path, html_path):
    mark = rules["확인 필요 표시"]
    f, shortage = [], []
    for stage in ("S1", "S2", "S3"):
        fname = rf(rules, stage)
        data, err = read_json(run / fname)
        if err:
            f.append(err)
            continue
        for path, text in walk_strings(data, set()):
            if path.split(".")[-1] == "상태":
                continue  # '경험 부족/확인 필요' 상태 값은 정상 분류이므로 제외한다.
            if mark in text:
                f.append("%s %s: '%s' 표시가 남아 있음" % (fname, path, mark))
    data, _ = read_json(run / rf(rules, "S2"))
    cfg = rules["카드"]["역량 매칭 카드"]
    for it in list_of(data, cfg["목록 키"]) or []:
        if isinstance(it, dict) and it.get("상태") == cfg["상태 값"]["부족"]:
            shortage.append(it.get(cfg["요구사항 id 키"]))
    extra = {"경험 부족 요구사항": shortage}
    if f:
        extra["중단"] = True
        extra["조치"] = "사용자에게 목록을 보고하고 review.md 진행 여부를 확인"
    return f, extra


def state_check(run, rules, exp_path, html_path):
    state, err = read_json(run / rf(rules, "상태"))
    if err or not isinstance(state, dict):
        return [err or "state.json이 객체가 아님"], {"중단": True}
    f = []
    for k in rules["상태 파일 필드"]:
        if k not in state:
            f.append("state.json에 '%s' 없음" % k)
    if state.get("approved") is True:
        for k in rules["승인 시 추가 필드"]:
            if empty(state.get(k)):
                f.append("승인 기록에 '%s' 없음" % k)
    limit = rules["되돌아가기 상한"]
    counts = state.get("복귀횟수", {})
    if isinstance(counts, dict):
        for stage, n in counts.items():
            if not isinstance(n, int) or isinstance(n, bool):
                f.append("%s 되돌아가기 횟수가 정수가 아님 (%r)" % (stage, n))
            elif n > limit:
                f.append("%s 되돌아가기 %d회 (상한 %d회 초과)" % (stage, n, limit))
    else:
        f.append("복귀횟수는 단계별 횟수 객체여야 함")
    return f, ({"중단": True} if f else {})


GATES = {
    "G1": g1, "G2": g2, "G3": g3, "G4": g4, "APPROVAL": approval, "G5": g5,
    "pre-S2": pre_s2, "pre-review": pre_review, "STATE": state_check, "HASH": hash_gate,
}
DEFAULT_RETURN = {"G1": "S1", "G2": "S2", "G3": "S3", "G5": "S5"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="읽기 전용 판정 스크립트")
    ap.add_argument("gate", choices=sorted(GATES))
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--experiences")
    ap.add_argument("--html")
    args = ap.parse_args(argv)
    if args.run_dir is None and args.gate != "pre-S2":
        ap.error("실행 폴더가 필요함")
    try:
        rules = load_rules()
        run = Path(args.run_dir) if args.run_dir else Path(".")
        failures, extra = GATES[args.gate](run, rules, args.experiences, args.html)
    except Exception as e:  # 입력 형식이 깨진 경우에도 JSON으로 답한다.
        print(json.dumps({"gate": args.gate, "pass": False, "오류": True,
                          "failures": ["입력 형식 오류: %s: %s" % (type(e).__name__, e)]},
                         ensure_ascii=False, indent=2))
        return 2
    passed = not failures
    out = {"gate": args.gate, "pass": passed, "failures": failures}
    out.update(extra)
    if not passed and "return_to" not in out and args.gate in DEFAULT_RETURN:
        out["return_to"] = DEFAULT_RETURN[args.gate]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
