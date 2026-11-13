"""GRANTH-AI answer engine: textbook-only, extractive by default, independently verified, cache-backed.

Pipeline:  question -> Gujarati normalization -> scope (board/medium/standard/subject/book/edition/chapter)
           -> cache lookup -> hybrid retrieval -> evidence sufficiency check -> extractive answer (exam format)
           -> [optional constrained generation, discarded unless verified] -> citation/quote verification
           -> cache store (verified answers only) -> audit records.

Invariant: every sentence shown as an answer is a verbatim substring of a stored chunk of an AUTHORIZED,
approved edition inside the selected scope - or the system abstains.
"""
from __future__ import annotations

import json
import re
import time

from . import ENGINE_VERSION, cache, db, gujarati as g, retrieval, study

ABSTAIN_MESSAGE = "આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી."
MODES = ("auto", "one_line", "definition", "short", "detailed", "points", "difference", "formula")
MODE_LABELS = {"one_line": "એક વાક્યમાં ઉત્તર", "definition": "વ્યાખ્યા", "short": "ટૂંકો ઉત્તર", "detailed": "વિગતવાર ઉત્તર",
               "points": "મુદ્દાસર ઉત્તર", "difference": "તફાવત", "formula": "સૂત્ર આધારિત ઉત્તર"}
MARKS_TARGET = {1: 1, 2: 2, 3: 3, 4: 5, 5: 6}
MODE_TARGET = {"one_line": 1, "definition": 1, "short": 3, "detailed": 6, "points": 5}
MAX_QUESTION_CHARS = 500
MIN_TOP_COVERAGE = 0.6
MIN_UNION_COVERAGE = 0.8
REASONS = {
    "no_authorized_textbook_in_scope": "પસંદ કરેલી શ્રેણીમાં કોઈ અધિકૃત અને મંજૂર થયેલું પાઠ્યપુસ્તક ઉપલબ્ધ નથી.",
    "no_content_terms": "પ્રશ્નમાં શોધી શકાય તેવો કોઈ મુખ્ય શબ્દ મળ્યો નથી.",
    "no_evidence": "પ્રશ્નના મુખ્ય શબ્દો પસંદ કરેલા પાઠ્યપુસ્તકમાં મળ્યા નથી.",
    "premise_not_supported": "પ્રશ્નમાં માની લીધેલી વાત પસંદ કરેલા પાઠ્યપુસ્તકના કોઈ એક વાક્યમાં મળતી નથી, તેથી 'શા માટે' નો ઉત્તર આપી શકાતો નથી.",
    "low_coverage": "પ્રશ્નના કેટલાક મુખ્ય શબ્દો પસંદ કરેલા પાઠ્યપુસ્તકમાં મળ્યા નથી, તેથી ઉત્તર આપી શકાતો નથી.",
    "definition_not_found": "પસંદ કરેલા પાઠ્યપુસ્તકમાં આ શબ્દની વ્યાખ્યા મળી નથી.",
    "difference_not_supported": "પસંદ કરેલા પાઠ્યપુસ્તકમાં આ બે બાબતોની સરખામણી માટે પૂરતો આધાર મળ્યો નથી.",
    "formula_not_found": "પસંદ કરેલા પાઠ્યપુસ્તકમાં આ મુદ્દા માટે કોઈ સૂત્ર મળ્યું નથી.",
    "verification_failed": "ઉત્તર પાઠ્યપુસ્તકના પુરાવા સાથે ચકાસી શકાયો નથી, તેથી બતાવ્યો નથી.",
}
_DEF_INTENT = re.compile(r"(એટલે\s+શુ|કોને\s+કહે|વ્યાખ્યા|શું?\s+છે\s*\??$)")
_DIFF_INTENT = re.compile(r"(તફાવત|ભેદ)")
_FORMULA_INTENT = re.compile(r"(સૂત્ર|સમીકરણ)")
_DIFF_PARSE = re.compile(r"^(.*?)\s+અને\s+(.*?)\s+(?:વચ્ચે\S*|ન[ોા]\s+(?:તફાવત|ભેદ)|તફાવત|ભેદ)")
_EV_FIELDS = ("id", "edition_id", "chapter_id", "section_id", "page_number", "chunk_index", "kind", "text", "text_sha256",
              "extraction_confidence", "board", "medium", "standard", "subject", "book_title", "edition",
              "chapter_number", "chapter_title", "section_title", "source_url", "permission_status")


class QuestionError(ValueError):
    pass


# ----------------------------------------------------------------------------- scope
def resolve_scope(con, scope: dict) -> list[dict]:
    """Editions the question may be answered from. Never includes unauthorized or unapproved editions."""
    sql = ("SELECT e.id, e.textbook_id, e.edition_label, e.corpus_version, e.academic_year, t.title, t.board, t.medium,"
           " t.standard, s.name_gu AS subject FROM textbook_editions e JOIN textbooks t ON t.id=e.textbook_id"
           " JOIN subjects s ON s.id=t.subject_id WHERE e.permission_status='AUTHORIZED' AND e.review_status='approved'"
           " AND e.ingested_at IS NOT NULL")
    args: list = []
    if scope.get("chapter_id"):
        row = con.execute("SELECT edition_id FROM chapters WHERE id=?", (int(scope["chapter_id"]),)).fetchone()
        if row is None:
            return []
        if scope.get("edition_id") and int(scope["edition_id"]) != row["edition_id"]:
            return []
        scope = {**scope, "edition_id": row["edition_id"]}
    if scope.get("edition_id"):
        sql += " AND e.id=?"
        args.append(int(scope["edition_id"]))
    if scope.get("textbook_id"):
        sql += " AND t.id=?"
        args.append(int(scope["textbook_id"]))
    for col, key in (("t.board", "board"), ("t.medium", "medium"), ("s.name_gu", "subject")):
        if scope.get(key):
            sql += f" AND {col}=?"
            args.append(scope[key])
    if scope.get("standard"):
        sql += " AND t.standard=?"
        args.append(int(scope["standard"]))
    return [dict(r) for r in con.execute(sql + " ORDER BY e.id", args)]


# ----------------------------------------------------------------------------- evidence helpers
def _ev(row: dict) -> dict:
    d = {k: row[k] for k in _EV_FIELDS}
    d["chunk_id"] = d.pop("id")
    d["scores"] = row.get("scores")
    return d


def _citation(ev: dict) -> dict:
    return {"board": ev["board"], "medium": ev["medium"], "standard": ev["standard"], "subject": ev["subject"],
            "book_title": ev["book_title"], "edition": ev["edition"], "edition_id": ev["edition_id"],
            "chapter_number": ev["chapter_number"], "chapter_title": ev["chapter_title"],
            "section_title": ev["section_title"], "page_number": ev["page_number"], "source_url": ev["source_url"],
            "permission_status": ev["permission_status"]}


def check_sufficiency(res: dict) -> tuple[bool, str]:
    terms, results = res["terms"], res["results"]
    if not terms:
        return False, "no_content_terms"
    if not results:
        return False, "no_evidence"
    top = results[0]
    if top["scores"]["coverage"] >= MIN_TOP_COVERAGE:
        return True, "ok"
    total = sum(res["weights"].values()) or 1.0
    union = set()
    for r in results[:3]:
        if r["chapter_id"] == top["chapter_id"] and r["edition_id"] == top["edition_id"]:
            union.update(r["matched_terms"])
    if top["scores"]["coverage"] >= 0.34 and sum(res["weights"].get(t, 0) for t in union) / total >= MIN_UNION_COVERAGE:
        return True, "ok"
    return False, "low_coverage"


def _units(results: list[dict], res: dict) -> list[dict]:
    """Candidate answer units: sentences of prose chunks, whole tables / formulas / figures."""
    total = sum(res["weights"].values()) or 1.0
    matched = {t["term"] for t in res["terms"] if t["term"]}
    units = []
    for rank, row in enumerate(results):
        if row["kind"] == "paragraph":
            for pos, s in enumerate(g.split_sentences(row["text"])):
                st = set(g.content_terms(s))
                score = sum(res["weights"][t] for t in matched if t in st) / total
                units.append({"text": s, "row": row, "rank": rank, "pos": pos, "score": score, "kind": "sentence"})
        else:
            # tables, formulas, figures and worked examples are never split
            units.append({"text": row["text"], "row": row, "rank": rank, "pos": 0, "score": row["scores"]["coverage"],
                          "kind": row["kind"]})
    return units


_ANAPHORA = ("આ ", "તે ", "તેથી", "આમ ", "આથી")


def _with_antecedents(chosen: list[dict]) -> list[dict]:
    """A sentence starting with a demonstrative ('આ નિયમને ...') is unreadable alone: prepend the textbook
    sentence right before it (same chunk)."""
    out = []
    have = {(u["row"]["id"], u["pos"]) for u in chosen if u["kind"] == "sentence"}
    for u in chosen:
        if u["kind"] == "sentence" and u["pos"] > 0 and u["text"].startswith(_ANAPHORA) \
                and (u["row"]["id"], u["pos"] - 1) not in have:
            prev = g.split_sentences(u["row"]["text"])[u["pos"] - 1]
            out.append({**u, "text": prev, "pos": u["pos"] - 1})
            have.add((u["row"]["id"], u["pos"] - 1))
        out.append(u)
    return out


def _part(u: dict) -> dict:
    return {"text": u["text"], "kind": u["kind"], "chunk_id": u["row"]["id"], "page_number": u["row"]["page_number"]}


def _find_definition(results: list[dict], target_terms: set) -> dict | None:
    best, best_j = None, 0.0
    for rank, row in enumerate(results):
        if row["kind"] not in ("paragraph", "example"):
            continue
        for pos, s in enumerate(g.split_sentences(row["text"])):
            for term in study.find_definitions(s):
                x = set(g.content_terms(term))
                if not x or not (x & target_terms):
                    continue
                j = len(x & target_terms) / len(x | target_terms)
                if j > best_j + 1e-9:
                    best_j = j
                    best = {"text": s, "row": row, "rank": rank, "pos": pos, "score": j, "kind": "sentence", "term": term}
    return best if best and best_j >= 0.5 else None


def _target_terms(res: dict) -> set:
    return {t["term"] or t["query"] for t in res["terms"]}


# ----------------------------------------------------------------------------- extractive composition
def detect_mode(question: str) -> str:
    if _DIFF_INTENT.search(question):
        return "difference"
    if _FORMULA_INTENT.search(question):
        return "formula"
    if _DEF_INTENT.search(question):
        return "definition"
    return "short"


_PREMISE_Q = re.compile(r"શા\s*માટે|(?<!\S)કેમ(?!\S)|કારણ")


def _compose(con, question: str, mode: str, marks, res: dict, edition_ids, chapter_id) -> dict:
    """Returns {'parts': [...], 'note': str|None, 'length_supported': bool|None} or {'abstain': reason}."""
    results = res["results"]
    top_cov = results[0]["scores"]["coverage"]
    relevant = [r for r in results if r["scores"]["coverage"] >= max(0.5 * top_cov, 0.3)]
    units = [u for u in _units(relevant, res) if u["score"] > 0]

    if mode == "definition":
        d = _find_definition(results, _target_terms(res))
        if not d:
            return {"abstain": "definition_not_found"}
        return {"parts": [_part(u) for u in _with_antecedents([d])], "note": None, "length_supported": None}

    if mode == "difference":
        m = _DIFF_PARSE.search(question)
        if not m:
            return {"abstain": "difference_not_supported"}
        a_txt, b_txt = m.group(1), m.group(2)
        idx = retrieval.get_index(con)
        a = {t["term"] or t["query"] for t in idx.resolve_terms(a_txt)}
        b = {t["term"] or t["query"] for t in idx.resolve_terms(b_txt)}
        if not a or not b or a == b:
            return {"abstain": "difference_not_supported"}
        for r in results:
            if r["kind"] == "table":
                tt = set(g.content_terms(r["text"]))
                if a <= tt and b <= tt:
                    return {"parts": [{"text": r["text"], "kind": "table", "chunk_id": r["id"], "page_number": r["page_number"]}],
                            "note": None, "length_supported": None}
        parts = []
        for txt, terms in ((a_txt, a), (b_txt, b)):
            sub = retrieval.search(con, txt, edition_ids, chapter_id, k=8)
            d = _find_definition(sub["results"], terms)
            if not d or set(g.content_terms(d["term"])) != terms:
                return {"abstain": "difference_not_supported"}
            parts.append(_part(d))
        if parts[0]["text"] == parts[1]["text"]:
            return {"abstain": "difference_not_supported"}
        return {"parts": parts, "length_supported": None,
                "note": "પાઠ્યપુસ્તકમાં આ બે બાબતોના તફાવતનું કોષ્ટક મળ્યું નથી; તેથી પાઠ્યપુસ્તકમાં આપેલી બંનેની વ્યાખ્યા અલગ-અલગ બતાવી છે."}

    if mode == "formula":
        for r in relevant:
            if r["kind"] not in ("paragraph", "example"):
                continue
            run = con.execute("SELECT * FROM text_chunks WHERE edition_id=? AND chunk_index>? ORDER BY chunk_index LIMIT 4",
                              (r["edition_id"], r["chunk_index"])).fetchall()
            formulas = []
            for f in run:
                if f["kind"] != "formula" or f["section_id"] != r["section_id"]:
                    break
                formulas.append(f)
            if formulas:
                lead = max((u for u in units if u["row"]["id"] == r["id"]), key=lambda u: u["score"], default=None)
                parts = [_part(u) for u in _with_antecedents([lead])] if lead else []
                parts += [{"text": f["text"], "kind": "formula", "chunk_id": f["id"], "page_number": f["page_number"]}
                          for f in formulas]
                note = ("આ ફકરા પછી પાઠ્યપુસ્તકમાં એક કરતાં વધુ સૂત્ર આપેલાં છે; બધાં બતાવ્યાં છે." if len(formulas) > 1 else None)
                return {"parts": parts, "note": note, "length_supported": None}
        return {"abstain": "formula_not_found"}

    # one_line / short / detailed / points
    if not units:
        return {"abstain": "low_coverage"}
    if _PREMISE_Q.search(question):
        # A "why / for what reason" question asserts a premise. A lexical engine cannot judge whether the
        # textbook agrees with it, so it answers only when ONE textbook sentence carries every question term;
        # otherwise it would be stitching sentences around a statement the textbook may never make.
        need = {t["term"] or "?" + t["query"] for t in res["terms"]}
        if not any(need <= set(g.content_terms(u["text"])) for u in units if u["kind"] == "sentence"):
            return {"abstain": "premise_not_supported"}
    best = max(u["score"] for u in units)
    target = 1 if mode == "one_line" else (MARKS_TARGET.get(marks) if marks else MODE_TARGET[mode])
    floor = {"one_line": 1.0, "short": 0.5, "points": 0.34, "detailed": 0.34}[mode] * best
    lead = max(units, key=lambda u: (u["score"], -u["rank"], -u["pos"]))
    if mode != "one_line":
        # cohesion: the rest of the paragraph that holds the best sentence outranks stray sentences elsewhere
        for u in units:
            if u is not lead and u["row"]["id"] == lead["row"]["id"]:
                u["score"] += 0.4 * best
    pool = sorted((u for u in units if u["score"] >= floor - 1e-9), key=lambda u: (-u["score"], u["rank"], u["pos"]))
    chosen, seen = [], set()
    for u in pool:
        if u["text"] in seen:
            continue
        seen.add(u["text"])
        chosen.append(u)
        if len(chosen) >= target:
            break
    chosen.sort(key=lambda u: (u["rank"], u["pos"]))
    n_points = len(chosen)
    chosen = _with_antecedents(chosen)
    supported = None
    note = None
    if marks and mode != "one_line":
        supported = n_points >= target
        if not supported:
            note = (f"{marks} ગુણના ઉત્તર માટે પાઠ્યપુસ્તકમાં પૂરતા મુદ્દા મળ્યા નથી. "
                    f"જેટલો આધાર મળ્યો તેટલો જ ઉત્તર આપ્યો છે ({n_points} મુદ્દા); વધારાના મુદ્દા ઉમેર્યા નથી.")
    return {"parts": [_part(u) for u in chosen], "note": note, "length_supported": supported}


def _format(parts: list[dict], mode: str) -> str:
    if mode == "points" and len(parts) > 1:
        return "\n".join(f"{i}. {p['text']}" for i, p in enumerate(parts, 1))
    prose, out = [], []
    for p in parts:
        if p["kind"] == "sentence":
            prose.append(p["text"])
        else:
            if prose:
                out.append(" ".join(prose))
                prose = []
            out.append(p["text"])
    if prose:
        out.append(" ".join(prose))
    return "\n".join(out)


# ----------------------------------------------------------------------------- verification
def verify_extractive(con, parts: list[dict], citations: list[dict], edition_ids) -> dict:
    """Independent re-check against the database: quotes are verbatim, citations real, scope respected."""
    eds = {int(e) for e in edition_ids}
    checks, ok_parts = [], 0
    for p in parts:
        row = con.execute("SELECT c.*, e.permission_status AS ep, e.review_status AS er FROM text_chunks c"
                          " JOIN textbook_editions e ON e.id=c.edition_id WHERE c.id=?", (p["chunk_id"],)).fetchone()
        ok = bool(row) and " ".join(p["text"].split()) in " ".join(row["text"].split()) \
            and row["page_number"] == p["page_number"] and row["edition_id"] in eds \
            and row["ep"] == "AUTHORIZED" and row["er"] == "approved"
        ok_parts += ok
        checks.append({"chunk_id": p["chunk_id"], "verbatim_and_in_scope": bool(ok)})
    cit_ok = True
    for c in citations:
        row = con.execute("SELECT 1 FROM text_chunks WHERE edition_id=? AND page_number=? AND COALESCE(chapter_title,'')=?"
                          " AND COALESCE(section_title,'')=? LIMIT 1",
                          (c["edition_id"], c["page_number"], c["chapter_title"] or "", c["section_title"] or "")).fetchone()
        cit_ok = cit_ok and row is not None
    ratio = ok_parts / len(parts) if parts else 0.0
    return {"verified": bool(parts) and ratio == 1.0 and cit_ok, "support_ratio": round(ratio, 4),
            "citations_valid": bool(cit_ok), "method": "verbatim-substring + citation lookup", "checks": checks}


def verify_generated(text: str, evidence_texts: list[str]) -> dict:
    """Check model-written text against evidence: every content term and every number must occur in the evidence."""
    ev_terms = set()
    for t in evidence_texts:
        ev_terms.update(g.content_terms(t))
    sentences = g.split_sentences(text)
    bad = []
    for s in sentences:
        terms = g.content_terms(s)
        unsupported = [t for t in terms if t not in ev_terms]
        if terms and unsupported:
            bad.append({"sentence": s, "unsupported_terms": unsupported})
    ok = bool(sentences) and not bad
    return {"verified": ok, "support_ratio": round(1 - len(bad) / len(sentences), 4) if sentences else 0.0,
            "method": "term + number containment against evidence", "unsupported": bad}


# ----------------------------------------------------------------------------- pipeline
def _abstain(reason: str, res: dict | None = None) -> dict:
    out = {"status": "abstained", "message": ABSTAIN_MESSAGE, "reason": reason, "reason_gu": REASONS[reason],
           "answer": None, "evidence": [], "citations": [], "engine": "extractive", "engine_version": ENGINE_VERSION,
           "external_api_calls": 0, "cache": {"hit": False},
           "verification": {"verified": False, "support_ratio": 0.0, "citations_valid": False}}
    if res is not None:
        out["unmatched_terms"] = [t["query"] for t in res["terms"] if not t["term"]]
        out["retrieved"] = [{"chunk_id": r["id"], **r["scores"]} for r in res["results"]]
    return out


def _answer_variant(con, question, norm, editions, scope, mode, marks, use_cache, router) -> dict:
    edition_ids = [e["id"] for e in editions]
    chapter_id = int(scope["chapter_id"]) if scope.get("chapter_id") else None
    versions = {e["id"]: e["corpus_version"] for e in editions}
    eff_mode = detect_mode(question) if mode == "auto" else mode
    key_scope = {"board": scope.get("board"), "medium": scope.get("medium"), "standard": scope.get("standard"),
                 "subject": scope.get("subject"), "edition_ids": edition_ids, "chapter_id": chapter_id,
                 "mode": eff_mode, "marks": marks}
    key = cache.make_key(norm, key_scope, versions)
    if use_cache:
        hit = cache.get(con, key)
        if hit:
            con.execute("INSERT INTO usage_events(ts, kind) VALUES (?,?)", (db.now(), "cache_hit"))
            hit["external_api_calls"] = 0
            return hit
        con.execute("INSERT INTO usage_events(ts, kind) VALUES (?,?)", (db.now(), "cache_miss"))
    con.execute("INSERT INTO usage_events(ts, kind) VALUES (?,?)", (db.now(), "local_retrieval"))

    q_for_search = _FORMULA_INTENT.sub(" ", question) if eff_mode == "formula" else question
    res = retrieval.search(con, q_for_search, edition_ids, chapter_id, k=8)
    ok, reason = check_sufficiency(res)
    if not ok:
        return {**_abstain(reason, res), "mode": eff_mode}
    comp = _compose(con, question, eff_mode, marks, res, edition_ids, chapter_id)
    if "abstain" in comp:
        return {**_abstain(comp["abstain"], res), "mode": eff_mode}

    parts = comp["parts"]
    rows = {r["id"]: r for r in res["results"]}
    evidence = []
    for p in parts:
        if p["chunk_id"] not in rows:
            r = con.execute("SELECT * FROM text_chunks WHERE id=?", (p["chunk_id"],)).fetchone()
            rows[p["chunk_id"]] = {**dict(r), "scores": None}
        e = _ev(rows[p["chunk_id"]])
        if e["chunk_id"] not in [x["chunk_id"] for x in evidence]:
            evidence.append(e)
    citations = []
    for e in evidence:
        c = _citation(e)
        if c not in citations:
            citations.append(c)
    verification = verify_extractive(con, parts, citations, edition_ids)
    if not verification["verified"]:
        return {**_abstain("verification_failed", res), "mode": eff_mode}

    payload = {"status": "answered", "mode": eff_mode, "mode_label": MODE_LABELS[eff_mode], "marks": marks,
               "answer": {"text": _format(parts, eff_mode), "parts": parts, "generated": False},
               "note": comp.get("note"), "length_supported": comp.get("length_supported"),
               "evidence": evidence, "citations": citations, "verification": verification,
               "retrieved": [{"chunk_id": r["id"], **r["scores"]} for r in res["results"]],
               "query_terms": res["terms"], "engine": "extractive", "engine_version": ENGINE_VERSION,
               "external_api_calls": 0, "cache": {"hit": False}}

    # Optional constrained synthesis. Its text replaces the extractive wording only if independently verified.
    if router is not None and eff_mode in ("short", "detailed", "points"):
        gen = router.synthesize(con, question, [e["text"] for e in evidence], MODE_LABELS[eff_mode])
        if gen:
            payload["external_api_calls"] = gen["external_calls"]
            if gen["text"]:
                gv = verify_generated(gen["text"], [e["text"] for e in evidence])
                payload["generation"] = {"provider": gen["provider"], "accepted": gv["verified"], "check": gv}
                if gv["verified"]:
                    payload["answer"] = {"text": gen["text"], "parts": parts, "generated": True}
                    payload["engine"] = f"generative:{gen['provider']}+verified"
                    payload["verification"]["generated_text_check"] = gv
    if use_cache:
        cache.put(con, key, norm, key_scope, versions, payload)
    return payload


def ask(con, question: str, scope: dict | None = None, mode: str = "auto", marks: int | None = None,
        session_id: str = "anonymous", input_method: str = "typed", use_cache: bool = True, router=None) -> dict:
    t0 = time.perf_counter()
    scope = dict(scope or {})
    question = g.normalize_text(question or "")
    if not question:
        raise QuestionError("પ્રશ્ન ખાલી છે.")
    if len(question) > MAX_QUESTION_CHARS:
        raise QuestionError(f"પ્રશ્ન {MAX_QUESTION_CHARS} અક્ષરથી લાંબો છે.")
    if mode not in MODES:
        raise QuestionError("unknown answer mode")
    if marks is not None and marks not in MARKS_TARGET:
        raise QuestionError("marks must be 1-5")
    if input_method not in ("typed", "voice", "camera"):
        raise QuestionError("unknown input method")
    norm = g.search_key(question)
    editions = resolve_scope(con, scope)
    if not editions:
        payload = {**_abstain("no_authorized_textbook_in_scope"), "mode": mode}
    else:
        by_book: dict = {}
        for e in editions:
            by_book.setdefault(e["textbook_id"], []).append(e)
        multi = any(len(v) > 1 for v in by_book.values())
        variants = [[e] for e in editions] if multi else [editions]
        outs = [(v, _answer_variant(con, question, norm, v, scope, mode, marks, use_cache, router)) for v in variants]
        if len(outs) == 1:
            payload = outs[0][1]
        else:
            answered = [(v, o) for v, o in outs if o["status"] == "answered"]
            if not answered:
                payload = outs[0][1]
            elif len(answered) == 1 or len({g.search_key(o["answer"]["text"]) for _, o in answered}) == 1:
                payload = dict(answered[-1][1])
                payload["edition_note"] = ("એક કરતાં વધુ આવૃત્તિ પસંદ થયેલી છે. આ ઉત્તર આ આવૃત્તિમાંથી છે: "
                                           + answered[-1][0][0]["edition_label"]
                                           + (" (બીજી આવૃત્તિમાં પણ આ જ લખાણ છે)" if len(answered) > 1 else ""))
            else:
                payload = {"status": "edition_conflict", "mode": answered[0][1]["mode"],
                           "message": "પાઠ્યપુસ્તકની જુદી જુદી આવૃત્તિઓમાં આ પ્રશ્નનો ઉત્તર જુદો છે. દરેક આવૃત્તિનો ઉત્તર અલગ બતાવ્યો છે.",
                           "editions": [{"edition_id": v[0]["id"], "edition": v[0]["edition_label"], "book_title": v[0]["title"],
                                         "answer": o["answer"], "evidence": o["evidence"], "citations": o["citations"],
                                         "verification": o["verification"]} for v, o in answered],
                           "answer": None, "evidence": [], "citations": [], "engine": "extractive",
                           "engine_version": ENGINE_VERSION, "cache": {"hit": False},
                           "external_api_calls": sum(o.get("external_api_calls", 0) for _, o in answered),
                           "verification": {"verified": all(o["verification"]["verified"] for _, o in answered)}}
    payload["question"] = question
    payload["normalized_question"] = norm
    payload["scope"] = {**{k: scope.get(k) for k in ("board", "medium", "standard", "subject", "textbook_id", "edition_id",
                                                     "chapter_id")}, "edition_ids": [e["id"] for e in editions]}
    payload["latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    _persist(con, payload, session_id, input_method, mode, marks)
    return payload


def _persist(con, payload, session_id, input_method, mode, marks):
    qid = con.execute("INSERT INTO questions(session_id, text, normalized, input_method, scope_json, mode, marks, created_at)"
                      " VALUES (?,?,?,?,?,?,?,?)",
                      (session_id[:64], payload["question"], payload["normalized_question"], input_method,
                       json.dumps(payload["scope"], ensure_ascii=False), payload.get("mode", mode), marks, db.now())).lastrowid
    for rank, r in enumerate(payload.get("retrieved") or [], 1):
        con.execute("INSERT INTO retrieved_evidence(question_id, chunk_id, rank, score, keyword_score, semantic_score, coverage)"
                    " VALUES (?,?,?,?,?,?,?)", (qid, r["chunk_id"], rank, r["score"], r["keyword_bm25"], r["ngram_cosine"],
                                                r["coverage"]))
    aid = con.execute("INSERT INTO generated_answers(question_id, status, answer_json, engine, engine_version, from_cache,"
                      " external_api_calls, latency_ms, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      (qid, payload["status"], json.dumps(payload, ensure_ascii=False), payload["engine"],
                       payload["engine_version"], int(payload["cache"]["hit"]), payload.get("external_api_calls", 0),
                       payload["latency_ms"], db.now())).lastrowid
    v = payload.get("verification") or {}
    con.execute("INSERT INTO verification_results(answer_id, verified, support_ratio, citations_valid, details_json)"
                " VALUES (?,?,?,?,?)", (aid, int(bool(v.get("verified"))), v.get("support_ratio", 0.0),
                                        int(bool(v.get("citations_valid"))), json.dumps(v, ensure_ascii=False)))
    con.commit()
    payload["question_id"], payload["answer_id"] = qid, aid


def history(con, session_id: str, limit: int = 50) -> list[dict]:
    rows = con.execute(
        "SELECT q.id AS question_id, q.text, q.input_method, q.mode, q.marks, q.created_at, a.id AS answer_id, a.status,"
        " a.from_cache, a.answer_json FROM questions q JOIN generated_answers a ON a.question_id=q.id"
        " WHERE q.session_id=? ORDER BY q.id DESC LIMIT ?", (session_id[:64], limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["result"] = json.loads(d.pop("answer_json"))
        out.append(d)
    return out
