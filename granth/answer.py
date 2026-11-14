"""GRANTH-AI answer engine: textbook-only, extractive by default, independently verified, cache-backed.

Pipeline:  question -> Gujarati normalization -> scope (board/medium/standard/subject/book/edition/chapter)
           -> cache lookup -> hybrid retrieval -> evidence sufficiency check -> extractive answer (exam format)
           -> [optional constrained generation, discarded unless verified] -> citation/quote verification
           -> cache store (verified answers only) -> audit records.

Invariant: every sentence shown as an answer is a verbatim substring of a stored chunk of an APPROVED,
approved edition inside the selected scope - or the system abstains.
"""
from __future__ import annotations

import json
import re
import time

from . import ENGINE_VERSION, cache, concepts, db, explain, gujarati as g, intent as intent_mod, lang, retrieval, study, validate

ABSTAIN_MESSAGE = "આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી."
MODES = ("auto", "one_line", "definition", "short", "detailed", "points", "difference", "formula", "steps")
MODE_LABELS = {"one_line": "એક વાક્યમાં ઉત્તર", "definition": "વ્યાખ્યા", "short": "ટૂંકો ઉત્તર", "detailed": "વિગતવાર ઉત્તર",
               "points": "મુદ્દાસર ઉત્તર", "difference": "તફાવત", "formula": "સૂત્ર આધારિત ઉત્તર", "steps": "પગલાંવાર ઉદાહરણ"}
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
    "example_not_found": "પસંદ કરેલા પાઠ્યપુસ્તકમાં આ મુદ્દાનું ઉકેલેલું ઉદાહરણ મળ્યું નથી. GRANTH-AI નવા દાખલાની ગણતરી જાતે કરતું નથી.",
    "ambiguous_question": "પ્રશ્ન અસ્પષ્ટ છે: આ શબ્દ પાઠ્યપુસ્તકમાં એક કરતાં વધુ પ્રકરણમાં જુદા જુદા અર્થમાં આવે છે. નીચેમાંથી મુદ્દો પસંદ કરીને પ્રશ્ન ફરી પૂછો.",
    "language_not_supported": "આ પ્રશ્નની ભાષા (હિન્દી/અન્ય) માટે હજી કોઈ સ્રોત ઉમેરાયો નથી. હાલમાં ગુજરાતી અને અંગ્રેજી પ્રશ્નો ગુજરાતી પુસ્તકમાંથી શોધાય છે.",
    "concept_not_supported": "પ્રશ્નમાં જે બાબત પૂછી છે તેની વ્યાખ્યા પસંદ કરેલા પાઠ્યપુસ્તકમાં મળી નથી. સંબંધિત શબ્દોવાળાં વાક્યો મળ્યાં છે, પણ તે આ પ્રશ્નનો ઉત્તર નથી, તેથી બતાવ્યાં નથી.",
    "aspect_not_found": "પૂછેલી બાબત (જેમ કે એકમ, ઉપયોગ, પ્રકાર, કાર્ય) વિશે પસંદ કરેલા પાઠ્યપુસ્તકમાં સીધું વાક્ય મળ્યું નથી.",
    "numbers_not_in_source": "પ્રશ્નમાં આપેલી સંખ્યાઓ પાઠ્યપુસ્તકના મળેલા લખાણમાં નથી. GRANTH-AI નવી ગણતરી જાતે કરતું નથી.",
    "evidence_not_specific": "પ્રશ્નના શબ્દો પાઠ્યપુસ્તકમાં મળે છે, પણ પૂછેલી બાબતનો સીધો ઉત્તર આપતું કોઈ વાક્ય મળ્યું નથી. ફક્ત મળતા શબ્દોવાળું લખાણ ઉત્તર તરીકે બતાવ્યું નથી.",
    "verification_failed": "ઉત્તર પાઠ્યપુસ્તકના પુરાવા સાથે ચકાસી શકાયો નથી, તેથી બતાવ્યો નથી.",
}
_DEF_INTENT = re.compile(r"(એટલે\s+શુ|કોને\s+કહે|વ્યાખ્યા|શું?\s+છે\s*\??$)")
# "difference" intent needs a compare cue; a bare "તફાવત" is also part of the term "વિદ્યુતસ્થિતિમાનનો તફાવત"
_DEF_STRICT = re.compile(r"(એટલે\s+શુ|કોને\s+કહે|વ્યાખ્યા)")
_DIFF_INTENT = re.compile(r"(વચ્ચે\S*\s+(?:\S+\s+)?(?:તફાવત|ભેદ)|(?:તફાવત|ભેદ)\s+(?:લખો|આપો|જણાવો|સમજાવો|દર્શાવો|સ્પષ્ટ|કયો|શો|શું))")
_FORMULA_INTENT = re.compile(r"(સૂત્ર|સમીકરણ)")
_STEPS_INTENT = re.compile(r"(પગલાંવાર|પગલાવાર|પગલાં\s*વાર|પગથિયાં|ઉદાહરણ|દાખલો|દાખલા)")
_DIFF_PARSE = re.compile(r"^(.*?)\s+અને\s+(.*?)\s+(?:વચ્ચે\S*|ન[ોા]\s+(?:તફાવત|ભેદ)|તફાવત|ભેદ)")
_EV_FIELDS = ("id", "edition_id", "chapter_id", "section_id", "page_number", "chunk_index", "kind", "text", "text_sha256",
              "extraction_confidence", "board", "medium", "standard", "subject", "book_title", "edition",
              "chapter_number", "chapter_title", "section_title", "source_url", "permission_status")


class QuestionError(ValueError):
    pass


# ----------------------------------------------------------------------------- scope
def resolve_scope(con, scope: dict, roles: tuple = ("textbook",)) -> list[dict]:
    """Editions the question may be answered from. Never includes unauthorized or unapproved editions.

    Supplementary sources are only returned when asked for by role. A student's personal notes are returned only
    when that edition is selected explicitly by the session that owns it."""
    sql = ("SELECT e.id, e.textbook_id, e.edition_label, e.corpus_version, e.academic_year, e.role, e.license, e.attribution,"
           " e.source_url, t.title, t.board, t.medium,"
           " t.standard, s.name_gu AS subject FROM textbook_editions e JOIN textbooks t ON t.id=e.textbook_id"
           " JOIN subjects s ON s.id=t.subject_id WHERE e.ingested_at IS NOT NULL AND ("
           "(e.permission_status='APPROVED' AND e.review_status='approved' AND e.role IN (%s))"
           " OR (e.role='personal' AND e.owner_session=? AND e.id=?))" % ",".join("?" * len(roles)))
    args: list = [*roles, str(scope.get("session") or "\x00none"), int(scope.get("edition_id") or 0)]
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
    order = [t["term"] for t in res["terms"]]
    pairs = [(x, y) for x, y in zip(order, order[1:]) if x and y]
    units = []
    for rank, row in enumerate(results):
        if row["kind"] == "paragraph":
            for pos, s in enumerate(g.split_sentences(row["text"])):
                seq = g.content_terms(s)
                st = set(seq)
                score = sum(res["weights"][t] for t in matched if t in st) / total
                if pairs:
                    # words the student wrote side by side ("ચૂનાનું પાણી") should also stand side by side in the source
                    adj = set(zip(seq, seq[1:]))
                    score += 0.25 * sum(1 for pr in pairs if pr in adj) / len(pairs)
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


_DEF_TAIL = re.compile(r"\s*(?:એટલે\s+શુ\S*|એટલે\s*\??$|કોને\s+કહે\S*|ન[ીોું]\s+વ્યાખ્યા|વ્યાખ્યા|ન[ોું]\s+અર્થ|શું?\s+છે\s*\??$).*$")


def requested_concept(con, question: str, edition_ids) -> dict:
    """Which concept does the question ask about? -> {'asked': [...], 'head': [...], 'mods': [...], 'head_facet', ...}
    All terms are resolved against the vocabulary of the editions in scope."""
    phrase = _DEF_TAIL.sub("", question).strip(" ?.:,")
    if not g.content_terms(phrase):
        phrase = _DEF_INTENT.sub(" ", question)
    an = concepts.analyse(phrase)
    idx = retrieval.get_index(con)

    def res(words):
        return [t["term"] or t["query"] for t in idx.resolve_terms(words, edition_ids)] if words else []
    mods, head = res(an["mod_words"]), res(an["head_words"])
    return {"asked": mods + head, "head": head, "mods": mods, "head_facet": an["head_facet"], "facet": an["facet"],
            "head_words": an["head_words"],
            "phrase": phrase}


def _find_definition(results: list[dict], asked: list, mods: list | None = None) -> dict | None:
    """The sentence that defines the REQUESTED concept. A sentence that defines a different concept is never
    returned, however many question words it shares (see concepts.match_definition)."""
    best, best_key = None, None
    for rank, row in enumerate(results):
        if row["kind"] not in ("paragraph", "example"):
            continue
        for pos, s in enumerate(g.split_sentences(row["text"])):
            for term in study.find_definitions(s):
                m = concepts.match_definition(asked, mods or [], term, s)
                if not m:
                    continue
                if m["kind"] == "head_only":
                    quals = [t for t in asked if t not in set(concepts.analyse(term)["terms"])]
                    if quals and len(m["missing"]) == len(quals):
                        continue                     # nothing in the sentence links it to what the student named
                    level = 2 if not m["missing"] else 1
                else:
                    level = 4 if m["kind"] == "exact" else 3
                key = (level, -rank, -pos)
                if best is None or key > best_key:
                    best_key = key
                    best = {"text": s, "row": row, "rank": rank, "pos": pos, "score": level / 4, "kind": "sentence",
                            "term": term, "match": m}
    return best


# ----------------------------------------------------------------------------- extractive composition
def detect_mode(question: str) -> str:
    if _DIFF_INTENT.search(question):
        return "difference"
    if _STEPS_INTENT.search(question):
        return "steps"
    if _FORMULA_INTENT.search(question):
        return "formula"
    if _DEF_INTENT.search(question):
        return "definition"
    return "short"


_CLAIM_WORDS = ("ખોટ", "નથી", "સાચ", "ક્યારેય", "હંમેશ")
_PREMISE_Q = re.compile(r"શા\s*માટે|(?<!\S)કેમ(?!\S)|કારણ")


def _compose(con, question: str, mode: str, marks, res: dict, edition_ids, chapter_id) -> dict:
    """Returns {'parts': [...], 'note': str|None, 'length_supported': bool|None} or {'abstain': reason}."""
    results = res["results"]
    top_cov = results[0]["scores"]["coverage"]
    relevant = [r for r in results if r["scores"]["coverage"] >= max(0.5 * top_cov, 0.3)]
    units = [u for u in _units(relevant, res) if u["score"] > 0]

    if mode == "definition":
        c = res.get("concept") or requested_concept(con, question, edition_ids)
        if not c["asked"]:
            return {"abstain": "definition_not_found"}
        rows = list(results)
        if c["mods"] and c["head_words"]:
            # look for the head concept on its own too: its definition may not mention the student's qualifiers
            have = {r["id"] for r in rows}
            rows += [r for r in retrieval.search(con, c["head_words"], edition_ids, chapter_id, k=8)["results"] if r["id"] not in have]
        d = _find_definition(rows, c["asked"], c["mods"])
        if not d:
            return {"abstain": "concept_not_supported" if c["mods"] else "definition_not_found"}
        gaps, note = [], None
        if d["match"]["kind"] == "head_only" and d["match"]["missing"]:
            note = (f"પાઠ્યપુસ્તકમાં ‘{d['term']}’ ની સામાન્ય વ્યાખ્યા મળી છે, તે બતાવી છે. "
                    f"પ્રશ્નમાં પૂછેલા ‘{' '.join(d['match']['missing'])}’ માટે અલગ વ્યાખ્યા પાઠ્યપુસ્તકમાં મળી નથી.")
            gaps.append(f"આ ‘{d['term']}’ ની સામાન્ય વ્યાખ્યા છે; ‘{' '.join(d['match']['missing'])}’ માટેની અલગ વ્યાખ્યા પુસ્તકમાં મળી નથી.")
        return {"parts": [_part(u) for u in _with_antecedents([d])], "note": note, "length_supported": None, "gaps": gaps}

    if mode == "difference":
        m = _DIFF_PARSE.search(question)
        if not m:
            return {"abstain": "difference_not_supported"}
        a_txt, b_txt = m.group(1), m.group(2)
        idx = retrieval.get_index(con)
        a_l = [t["term"] or t["query"] for t in idx.resolve_terms(a_txt, edition_ids)]
        b_l = [t["term"] or t["query"] for t in idx.resolve_terms(b_txt, edition_ids)]
        if b_l and a_l and b_l[-1] not in a_l and len(b_l) > len(a_l):
            # shared head noun written once: "અંતર્ગોળ અને બહિર્ગોળ અરીસા" = "અંતર્ગોળ અરીસા" and "બહિર્ગોળ અરીસા"
            a_txt = a_txt + " " + b_txt.split()[-1]
            a_l = [t["term"] or t["query"] for t in idx.resolve_terms(a_txt, edition_ids)]
        a, b = set(a_l), set(b_l)
        if not a or not b or a == b:
            return {"abstain": "difference_not_supported"}
        for r in results:
            if r["kind"] == "table":
                tt = set(g.content_terms(r["text"]))
                if a <= tt and b <= tt:
                    return {"parts": [{"text": r["text"], "kind": "table", "chunk_id": r["id"], "page_number": r["page_number"]}],
                            "note": None, "length_supported": None}
        parts = []
        for txt, terms in ((a_txt, a_l), (b_txt, b_l)):
            sub = retrieval.search(con, txt, edition_ids, chapter_id, k=8)
            d = _find_definition(sub["results"], terms)
            if not d or d["match"]["kind"] != "exact":
                return {"abstain": "difference_not_supported"}
            parts.append(_part(d))
        if parts[0]["text"] == parts[1]["text"]:
            return {"abstain": "difference_not_supported"}
        return {"parts": parts, "length_supported": None,
                "note": "પાઠ્યપુસ્તકમાં આ બે બાબતોના તફાવતનું કોષ્ટક મળ્યું નથી; તેથી પાઠ્યપુસ્તકમાં આપેલી બંનેની વ્યાખ્યા અલગ-અલગ બતાવી છે."}

    if mode == "steps":
        # A worked example printed in the book, shown step by step. The engine never computes a new sum itself.
        cands = [r for r in results if r["kind"] == "example"]
        if not cands:
            secs = [r["section_id"] for r in relevant if r["section_id"]]
            if secs:
                q = "SELECT * FROM text_chunks WHERE kind='example' AND section_id IN (%s) ORDER BY chunk_index" % ",".join("?" * len(secs))
                cands = [{**dict(x), "scores": None} for x in con.execute(q, secs)]
        if not cands:
            return {"abstain": "example_not_found"}
        ex = cands[0]
        parts = [{"text": st, "kind": "sentence", "chunk_id": ex["id"], "page_number": ex["page_number"]}
                 for st in g.split_sentences(ex["text"])]
        for f in con.execute("SELECT * FROM text_chunks WHERE kind='formula' AND edition_id=? AND section_id IS ? AND chunk_index IN (?,?)"
                             " ORDER BY chunk_index", (ex["edition_id"], ex["section_id"], ex["chunk_index"] - 1, ex["chunk_index"] + 1)):
            parts.append({"text": f["text"], "kind": "formula", "chunk_id": f["id"], "page_number": f["page_number"]})
        return {"parts": parts, "length_supported": None,
                "note": "આ પાઠ્યપુસ્તકમાં આપેલું ઉકેલેલું ઉદાહરણ છે. GRANTH-AI નવા દાખલાની ગણતરી જાતે કરતું નથી."}

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
                c = requested_concept(con, question, edition_ids)
                named = _find_definition([r], c["asked"], c["mods"]) if c["asked"] else None
                lead = named if named and named["match"]["kind"] == "exact" else \
                    max((u for u in units if u["row"]["id"] == r["id"]), key=lambda u: u["score"], default=None)
                parts = [_part(u) for u in _with_antecedents([lead])] if lead else []
                parts += [{"text": f["text"], "kind": "formula", "chunk_id": f["id"], "page_number": f["page_number"]}
                          for f in formulas]
                note = ("આ ફકરા પછી પાઠ્યપુસ્તકમાં એક કરતાં વધુ સૂત્ર આપેલાં છે; બધાં બતાવ્યાં છે." if len(formulas) > 1 else None)
                return {"parts": parts, "note": note, "length_supported": None}
        return {"abstain": "formula_not_found"}

    # one_line / short / detailed / points
    fac = res.get("facet")
    if fac:
        # "X નો એકમ / ઉપયોગ / પ્રકાર ..." asks for one ASPECT of X. Only a passage that names both X and that aspect
        # can answer it; the definition of X, or the same aspect of something else, cannot.
        fst, need = concepts.facet_stems(fac["name"]), set(fac["mods"])

        def fits(u):
            st = set(g.content_terms(u["text"]))
            return bool(st & fst) and need <= st
        units = [u for u in units if fits(u)]
        if not units:
            return {"abstain": "aspect_not_found"}
    if not units:
        return {"abstain": "low_coverage"}
    asked_all = {t["term"] for t in res["terms"] if t["term"]}

    def only_defines_subject(u):
        # "X ક્યાં વપરાય છે?" is not answered by the sentence that defines X: that sentence covers the subject of the
        # question and nothing of what is asked about it.
        if u["kind"] != "sentence":
            return False
        st = set(g.content_terms(u["text"]))
        for term in study.find_definitions(u["text"]):
            d = set(concepts.analyse(term)["terms"])
            if d and d < asked_all and not ((asked_all - d) & st):
                return True
        return False
    kept = [u for u in units if not only_defines_subject(u)]
    if not kept:
        return {"abstain": "aspect_not_found"}
    units = kept
    if _PREMISE_Q.search(question):
        # A "why / for what reason" question asserts a premise. A lexical engine cannot judge whether the
        # textbook agrees with it, so it answers only when ONE textbook sentence carries every question term;
        # otherwise it would be stitching sentences around a statement the textbook may never make.
        need = {t["term"] or "?" + t["query"] for t in res["terms"]}
        # judgement / negation words are stop-words for retrieval but they carry the premise ("... is wrong, why?")
        claims = [w for w in _CLAIM_WORDS if w in question]
        if not any(need <= set(g.content_terms(u["text"])) and all(w in u["text"] for w in claims)
                   for u in units if u["kind"] == "sentence"):
            return {"abstain": "premise_not_supported"}
    best = max(u["score"] for u in units)
    target = 1 if mode == "one_line" else (MARKS_TARGET.get(marks) if marks else MODE_TARGET[mode])
    floor = {"one_line": 1.0, "short": 0.5, "points": 0.34, "detailed": 0.34}[mode] * best
    lead = max(units, key=lambda u: (u["score"], -u["rank"], -u["pos"]))
    if lead["kind"] != "example":
        # a worked example is about one particular sum; it must not pad a general answer
        units = [u for u in units if u["kind"] != "example"]
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
    gaps = []
    if any(u["kind"] == "example" for u in chosen):
        gaps.append("આ લખાણ પાઠ્યપુસ્તકના એક ઉકેલેલા ઉદાહરણમાંથી છે; તે ફક્ત તે દાખલા પૂરતું છે, સામાન્ય નિયમ નથી.")
    return {"parts": [{**_part(u), "lead": u is lead} for u in chosen], "note": note, "length_supported": supported, "gaps": gaps}


def _format(parts: list[dict], mode: str) -> str:
    if mode == "points" and len(parts) > 1:
        return "\n".join(f"{i}. {p['text']}" for i, p in enumerate(parts, 1))
    if mode == "steps":
        n, out = 0, []
        for p in parts:
            if p["kind"] == "sentence":
                n += 1
                out.append(f"પગલું {n}: {p['text']}")
            else:
                out.append(p["text"])
        return "\n".join(out)
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
        row = con.execute("SELECT c.*, e.permission_status AS ep, e.review_status AS er, e.role AS erole FROM text_chunks c"
                          " JOIN textbook_editions e ON e.id=c.edition_id WHERE c.id=?", (p["chunk_id"],)).fetchone()
        ok = bool(row) and " ".join(p["text"].split()) in " ".join(row["text"].split()) \
            and row["page_number"] == p["page_number"] and row["edition_id"] in eds \
            and ((row["ep"] == "APPROVED" and row["er"] == "approved") or row["erole"] == "personal")
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


# ----------------------------------------------------------------------------- student-facing structure
WEAK_MATCHES = ("synonym", "fuzzy", "fuzzy_context", "prefix", "root")
TRUST_LABELS = {"verified": "સ્રોત સાથે ચકાસેલું", "partial": "આંશિક આધાર", "insufficient": "પૂરતો આધાર નથી"}
TRUST_LABELS_EN = {"verified": "Verified against source", "partial": "Partially supported", "insufficient": "Insufficient source evidence"}
SOURCE_TYPE_LABELS = {"quotation": "પાઠ્યપુસ્તકના શબ્દોમાં (સીધું અવતરણ)",
                      "simplified": "સરળ સમજૂતી (પુરાવા પરથી બનાવેલી, અવતરણ નથી)",
                      "supplementary": "પૂરક સ્રોતમાંથી (પાઠ્યપુસ્તકનો ભાગ નથી)",
                      "personal": "તમારી પોતાની નોંધમાંથી"}
_GENERIC_EN = {"law", "laws", "unit", "definition", "example", "direction", "directions", "water", "plants", "plant", "light", "energy"}
_ANAPHORA_START = ("આ ", "તે ", "તેથી", "આમ ", "આથી")


def _trust(status: str, reasons: list | None = None) -> dict:
    return {"status": status, "label_gu": TRUST_LABELS[status], "label_en": TRUST_LABELS_EN[status], "reasons": reasons or []}


def _structure(con, payload: dict, question: str, res: dict | None, source_type: str = "quotation") -> dict:
    """પ્રશ્ન / સરળ જવાબ / મુખ્ય મુદ્દા / પુસ્તકનો આધાર / વિશ્વસનીયતા સ્થિતિ. No percentages, no invented text."""
    parts = payload["answer"]["parts"]
    mode = payload["mode"]
    for p in parts:
        p["source_type"] = source_type
    if mode in ("definition", "one_line") or len(parts) == 1:
        lead_idx = set(range(len(parts)))
    elif mode in ("formula", "difference"):
        lead_idx = {i for i, p in enumerate(parts) if p["kind"] in ("sentence", "table")} or {0}
        if mode == "difference" and not any(p["kind"] == "table" for p in parts):
            lead_idx = set(range(len(parts)))
    else:
        li = next((i for i, p in enumerate(parts) if p.get("lead")), 0)
        lead_idx = {li}
        if li > 0 and parts[li]["text"].startswith(_ANAPHORA_START) and parts[li - 1]["chunk_id"] == parts[li]["chunk_id"]:
            lead_idx.add(li - 1)                      # keep the sentence that "આ ..." refers back to
        if li + 1 < len(parts) and parts[li + 1]["text"].startswith(_ANAPHORA_START) and parts[li + 1]["chunk_id"] == parts[li]["chunk_id"]:
            lead_idx.add(li + 1)
    simple = [parts[i] for i in sorted(lead_idx)]
    points = [p for i, p in enumerate(parts) if i not in lead_idx]

    reasons, notes = [], []
    if res is not None:
        ev_terms = set()
        for e in payload["evidence"]:
            ev_terms.update(g.content_terms(e["text"] + " " + (e.get("section_title") or "")))
        checked = bool(payload.get("validation"))       # granth.validate already judged every question word
        missing = [] if checked else [t["query"] for t in res["terms"] if not t["term"] or t["term"] not in ev_terms]
        if missing:
            reasons.append("પ્રશ્નના આ શબ્દો બતાવેલા આધારમાં નથી: " + ", ".join(missing))
        spell = [f"{t['query']} → {t['term']}" for t in res["terms"] if t["match"] in ("spelling", "compound") and t["query"] != t["term"]]
        if spell:
            notes.append("જોડણીના નાના ફેરથી શોધ્યું: " + ", ".join(spell))
        weak = [f"{t['query']} → {t.get('via') or t['term']}" for t in res["terms"] if t["match"] in WEAK_MATCHES]
        if weak:
            # the student's own word is not in the source: an assumed word found the passage, so this is never "Verified"
            reasons.append("પ્રશ્નના આ શબ્દો પુસ્તકમાં નથી; નજીકનો / સમાન અર્થનો શબ્દ ધારીને શોધ્યું છે: " + ", ".join(dict.fromkeys(weak))
                           + ". તમારો પ્રશ્ન આ જ બાબતનો છે કે નહીં તે જાતે ચકાસો.")
        if mode in ("short", "one_line", "detailed", "points") and not checked:
            # "Verified" needs ONE passage that carries every word of the question. Sentences that each match only
            # part of the question may be relevant, but nothing proves that together they answer it.
            need = {t["term"] for t in res["terms"] if t["term"]}
            if need and not any(need <= set(g.content_terms(p["text"])) for p in parts):
                reasons.append("પ્રશ્નના બધા મુખ્ય શબ્દો પુસ્તકના કોઈ એક વાક્યમાં સાથે મળ્યા નથી; જુદાં જુદાં વાક્યો બતાવ્યાં છે. "
                               "તે તમારા પ્રશ્નનો ઉત્તર છે કે નહીં તે પુરાવો વાંચીને ચકાસો.")
    reasons.extend(payload.get("support_gaps") or [])
    if payload.get("length_supported") is False:
        reasons.append("માગેલા ગુણ જેટલા મુદ્દા પાઠ્યપુસ્તકમાં મળ્યા નથી.")
    if mode == "difference" and payload.get("note"):
        reasons.append("પાઠ્યપુસ્તકમાં સીધો તફાવત આપેલો નથી; બંનેની વ્યાખ્યા અલગ બતાવી છે.")
    status = "verified" if payload["verification"]["verified"] and not reasons else "partial"

    answer_text = payload["answer"]["text"]
    ed_ids = sorted({e["edition_id"] for e in payload["evidence"]})
    word_help = []
    if ed_ids:
        q = ("SELECT word, explanation, page_number FROM vocabulary WHERE kind='textbook_glossary' AND edition_id IN (%s) ORDER BY id"
             % ",".join("?" * len(ed_ids)))
        for w in con.execute(q, ed_ids):
            if w["word"] in answer_text and w["explanation"] and w["explanation"] not in answer_text:
                word_help.append({"word": w["word"], "meaning": w["explanation"], "page_number": w["page_number"],
                                  "source_type": "textbook_glossary"})
            if len(word_help) >= 4:
                break
    rev = lang.reverse_glossary()
    found = [gu for gu, en in rev.items() if en not in _GENERIC_EN and (gu in question or gu in answer_text)]
    found = [gu for gu in found if not any(gu != o and gu in o for o in found)]          # keep the fullest term only
    english_terms = [{"gu": gu, "en": rev[gu]} for gu in sorted(found, key=lambda t: (t not in question, -len(t)))][:5]
    return {"question": question,
            "simple_answer": simple, "key_points": points,
            "answer_source_type": "simplified" if payload["answer"].get("generated") else source_type,
            "answer_source_label": SOURCE_TYPE_LABELS["simplified" if payload["answer"].get("generated") else source_type],
            "word_help": word_help, "word_help_label": "પાઠ્યપુસ્તકના શબ્દાર્થમાંથી",
            "english_terms": english_terms, "english_terms_label": "અંગ્રેજી પારિભાષિક શબ્દ (શોધ-સહાય સૂચિમાંથી; પાઠ્યપુસ્તકનું લખાણ નથી)",
            "basis": payload["citations"], "notes": notes, "trust": _trust(status, reasons)}


def _ambiguity(res: dict, question: str = "") -> list | None:
    """A bare topic ("પાણી", "કાર્બન ડાયૉક્સાઇડ") with no question in it, found in several chapters, cannot be
    answered responsibly: ask which topic. A bare topic that the book itself defines is answered by that definition."""
    words = [w.strip("?.,!;:") for w in question.split()]
    bare = len(res["terms"]) == 1 or (len(words) <= 3 and all(g.content_terms(w) for w in words if w))
    if not bare or not all(t["term"] for t in res["terms"]):
        return None
    asked = [t["term"] for t in res["terms"]]
    if len(asked) > 1 and _find_definition(res["results"], asked):
        return None
    seen, out = set(), []
    for r in res["results"]:
        if len(asked) > 1 and not set(asked) <= set(r["matched_terms"]):
            continue
        key = (r["edition_id"], r["section_id"])
        if key in seen or not r["section_title"]:
            continue
        seen.add(key)
        out.append({"chapter_number": r["chapter_number"], "chapter_title": r["chapter_title"], "section_title": r["section_title"],
                    "page_number": r["page_number"], "chapter_id": r["chapter_id"], "edition_id": r["edition_id"]})
    if len(out) >= 3 and len({(o["edition_id"], o["chapter_id"]) for o in out}) >= 2:
        return out
    return None


_EXPR = re.compile(r"[A-Za-z0-9(][A-Za-z0-9 ()/+\-−×*^²³.]*=[A-Za-z0-9 ()/+\-−×*^²³.=]*[A-Za-z0-9)²³]")


def _expr_key(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("*", "×").replace("-", "−")


def _formula_lookup(con, question: str, res: dict, edition_ids, chapter_id) -> dict | None:
    """'V = I × R કયો નિયમ છે?' - find the formula exactly as printed and return the statement it belongs to."""
    m = _EXPR.search(question)
    if not m:
        return None
    key = _expr_key(m.group(0))
    q = "SELECT * FROM text_chunks WHERE kind='formula' AND edition_id IN (%s)" % ",".join("?" * len(edition_ids))
    args = list(edition_ids)
    if chapter_id:
        q += " AND chapter_id=?"
        args.append(chapter_id)
    hit = next((r for r in con.execute(q + " ORDER BY id", args) if key in _expr_key(r["text"])), None)
    if hit is None:
        return None
    # the statement a formula belongs to is the text printed directly before it
    prev_chunk = con.execute("SELECT * FROM text_chunks WHERE edition_id=? AND section_id IS ? AND chunk_index<? AND kind IN"
                             " ('paragraph','example') ORDER BY chunk_index DESC LIMIT 1",
                             (hit["edition_id"], hit["section_id"], hit["chunk_index"])).fetchone()
    parts = []
    if prev_chunk:
        ss = g.split_sentences(prev_chunk["text"])
        idx = max((i for i, x in enumerate(ss) if study.find_definitions(x)), default=len(ss) - 1)
        if idx > 0 and ss[idx].startswith(_ANAPHORA_START):
            parts.append({"text": ss[idx - 1], "kind": "sentence", "chunk_id": prev_chunk["id"], "page_number": prev_chunk["page_number"]})
        parts.append({"text": ss[idx], "kind": "sentence", "chunk_id": prev_chunk["id"], "page_number": prev_chunk["page_number"]})
    parts.append({"text": hit["text"], "kind": "formula", "chunk_id": hit["id"], "page_number": hit["page_number"]})
    return {"parts": parts, "length_supported": None, "note": "પ્રશ્નમાં આપેલું સૂત્ર પાઠ્યપુસ્તકમાં મળ્યું છે; તેની બરાબર પહેલાં છપાયેલું લખાણ બતાવ્યું છે."}


# ----------------------------------------------------------------------------- pipeline
def _abstain(reason: str, res: dict | None = None) -> dict:
    out = {"status": "abstained", "message": ABSTAIN_MESSAGE, "reason": reason, "reason_gu": REASONS[reason],
           "answer": None, "evidence": [], "citations": [], "engine": "extractive", "engine_version": ENGINE_VERSION,
           "external_api_calls": 0, "cache": {"hit": False},
           "verification": {"verified": False, "support_ratio": 0.0, "citations_valid": False},
           "structured": {"simple_answer": [], "key_points": [], "basis": [], "word_help": [], "english_terms": [], "notes": [],
                          "trust": _trust("insufficient", [REASONS[reason]])}}
    if res is not None:
        out["unmatched_terms"] = [t["query"] for t in res["terms"] if not t["term"]]
        out["retrieved"] = [{"chunk_id": r["id"], **r["scores"]} for r in res["results"]]
    return out


_NUM = re.compile(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?(?![A-Za-z0-9])")
_EXPANDABLE = ("low_coverage", "no_evidence", "evidence_not_specific", "definition_not_found", "concept_not_supported", "premise_not_supported")


def _attempt(con, question, mode, eff_mode, marks, edition_ids, chapter_id):
    """One evidence search + composition. -> (comp, res, effective mode); comp is {'abstain': reason} on refusal."""
    concept = None
    if eff_mode in ("definition", "short", "one_line", "detailed", "points"):
        concept = requested_concept(con, question, edition_ids)
        if eff_mode == "definition" and (concept["head_facet"] or (
                not _DEF_STRICT.search(question) and intent_mod.analyse(question)["intent"] not in ("fact", "process", "example"))):
            eff_mode = "short"               # "અવરોધનો એકમ શું છે?" asks for a unit, not for the definition of અવરોધ
    q_for_search = question
    if eff_mode == "formula":
        q_for_search = _FORMULA_INTENT.sub(" ", question)
    elif eff_mode == "steps":
        q_for_search = _STEPS_INTENT.sub(" ", question)
    res = retrieval.search(con, q_for_search, edition_ids, chapter_id, k=8)
    comp = _formula_lookup(con, question, res, edition_ids, chapter_id) if mode == "auto" else None
    if comp:
        return comp, res, "formula"
    if concept:
        if eff_mode == "definition":
            res["concept"] = concept
        elif concept["head_facet"]:
            res["facet"] = {"name": concept["head_facet"], "mods": concept["mods"]}
        elif concept["facet"] == "application":
            # "X ક્યાં વપરાય છે?" - only a sentence that speaks of the USE of exactly that X can answer
            others = [t["term"] for t in res["terms"] if t["term"] and t["term"] not in concepts.all_facet_stems()]
            if others:
                res["facet"] = {"name": "application", "mods": others}
    ok, reason = check_sufficiency(res)
    if eff_mode in ("short", "detailed", "points", "one_line"):
        if ok and not chapter_id:
            options = _ambiguity(res, question)
            if options:
                return {"abstain": "ambiguous_question", "suggestions": options}, res, eff_mode
        comp = _validated(con, question, eff_mode, marks, res, edition_ids, chapter_id)
    elif not ok:
        return {"abstain": reason}, res, eff_mode
    else:
        comp = _compose(con, question, eff_mode, marks, res, edition_ids, chapter_id)
    if "parts" in comp and eff_mode != "steps":
        # GRANTH-AI never calculates. Every number the student wrote must be printed in the passage shown;
        # otherwise the passage is about a different sum, however similar its words are.
        shown = set(_NUM.findall(g.normalize_text(" ".join(p["text"] for p in comp["parts"]))))
        if any(n not in shown for n in _NUM.findall(question)):
            return {"abstain": "numbers_not_in_source"}, res, eff_mode
    return comp, res, eff_mode


def _validated(con, question, mode, marks, res, edition_ids, chapter_id) -> dict:
    """one_line / short / detailed / points: only sentences that pass granth.validate are shown (Phase 4)."""
    if not res["terms"]:
        return {"abstain": "no_content_terms"}
    if not res["results"]:
        return {"abstain": "no_evidence"}
    target = 1 if mode == "one_line" else (MARKS_TARGET.get(marks) if marks else MODE_TARGET[mode])
    nums = _NUM.findall(question)
    if nums and not any(all(n in set(_NUM.findall(g.normalize_text(r["text"]))) for n in nums) for r in res["results"]):
        return {"abstain": "numbers_not_in_source"}      # GRANTH-AI never calculates a new sum
    claims = [w for w in _CLAIM_WORDS if w in question] if _PREMISE_Q.search(question) else []
    sel = validate.select(con, question, res, edition_ids, chapter_id, target, claims)
    if "abstain" in sel:
        why = sel["abstain"] == "evidence_not_specific" and sel["analysis"]["intent"] == "reason"
        return {"abstain": "premise_not_supported" if why else sel["abstain"], "validation": sel["analysis"]}
    units = sel["units"]
    n_points = sel["n_found"]
    if mode in ("detailed", "points") or (marks and marks >= 3):
        # a longer answer may continue with the sentences that refer back to an accepted one ("આ પ્રક્રિયામાં ...")
        out = []
        for u in units:
            out.append(u)
            if u["kind"] != "sentence":
                continue
            sents = g.split_sentences(u["row"]["text"])
            j = u["pos"] + 1
            while j < len(sents) and sents[j].startswith(_ANAPHORA) and n_points < target \
                    and not any(x["row"]["id"] == u["row"]["id"] and x["pos"] == j for x in units + out):
                out.append({"text": sents[j], "row": u["row"], "pos": j, "kind": "sentence", "lead": None})
                n_points += 1
                j += 1
        units = out
    supported, note = None, None
    if marks and mode != "one_line":
        supported = n_points >= target
        if not supported:
            note = (f"{marks} ગુણના ઉત્તર માટે પાઠ્યપુસ્તકમાં પૂરતા મુદ્દા મળ્યા નથી. "
                    f"જેટલો આધાર મળ્યો તેટલો જ ઉત્તર આપ્યો છે ({n_points} મુદ્દા); વધારાના મુદ્દા ઉમેર્યા નથી.")
    parts = [{**_part(u), "lead": bool(u.get("lead"))} for u in units]
    if not any(p["lead"] for p in parts):
        parts[0]["lead"] = True
    return {"parts": parts, "note": note, "length_supported": supported, "gaps": sel["gaps"], "validation": sel["analysis"]}


def _concept_fallback(con, question, res, edition_ids, chapter_id) -> dict | None:
    """The student described a topic in everyday words ("છોડ ખોરાક કેવી રીતે બનાવે છે"). If the description matches
    a named concept AND the source defines that concept in a passage that itself carries most of the student's words,
    show that definition - marked as an assumed match, never as Verified. Otherwise: no answer."""
    term = concepts.concept_for(question)
    stems = g.content_terms(term) if term else []
    vocab = retrieval.get_index(con).scope(edition_ids)["vocab"]
    if not stems or any(x not in vocab for x in stems):
        return None
    d = _find_definition(retrieval.search(con, term, edition_ids, chapter_id, k=8)["results"], stems)
    if not d or d["match"]["kind"] != "exact":
        return None
    known = [t["term"] for t in res["terms"] if t["term"]]
    here = set(g.content_terms(d["row"]["text"] + " " + (d["row"].get("section_title") or "")))
    hits = sum(1 for t in known if t in here)
    if hits < 2 or hits < 0.6 * len(res["terms"]):
        return None
    return {"parts": [_part(u) for u in _with_antecedents([d])], "length_supported": None,
            "note": f"તમારા પ્રશ્નના વર્ણન પરથી પાઠ્યપુસ્તકનો મુદ્દો ‘{d['term']}’ ઓળખ્યો છે અને પુસ્તકમાં આપેલી તેની વ્યાખ્યા બતાવી છે.",
            "gaps": [f"પ્રશ્ન આ શબ્દોમાં પુસ્તકમાં નથી; વર્ણન પરથી મુદ્દો ‘{d['term']}’ ધારીને શોધ્યું છે. આ તમારા પ્રશ્નનો જ મુદ્દો છે કે નહીં તે જાતે ચકાસો."]}


def _answer_variant(con, question, norm, editions, scope, mode, marks, use_cache, router) -> dict:
    edition_ids = [e["id"] for e in editions]
    chapter_id = int(scope["chapter_id"]) if scope.get("chapter_id") else None
    versions = {e["id"]: e["corpus_version"] for e in editions}
    eff_mode = detect_mode(question) if mode == "auto" else mode
    key_scope = {"board": scope.get("board"), "medium": scope.get("medium"), "standard": scope.get("standard"),
                 "subject": scope.get("subject"), "edition_ids": edition_ids, "chapter_id": chapter_id,
                 "mode": eff_mode, "marks": marks}
    key = cache.make_key(norm, key_scope, versions)
    if any(e.get("role") == "personal" for e in editions):
        use_cache = False                      # a student's own notes never enter the shared cache
    if use_cache:
        hit = cache.get(con, key)
        if hit:
            con.execute("INSERT INTO usage_events(ts, kind) VALUES (?,?)", (db.now(), "cache_hit"))
            hit["external_api_calls"] = 0
            return hit
        con.execute("INSERT INTO usage_events(ts, kind) VALUES (?,?)", (db.now(), "cache_miss"))
    con.execute("INSERT INTO usage_events(ts, kind) VALUES (?,?)", (db.now(), "local_retrieval"))

    comp, res, eff_mode = _attempt(con, question, mode, eff_mode, marks, edition_ids, chapter_id)
    if comp.get("abstain") in _EXPANDABLE and mode in ("auto", "short", "detailed", "points", "one_line", "definition"):
        alt = _concept_fallback(con, question, res, edition_ids, chapter_id)
        if alt:
            comp, eff_mode = alt, "definition"
    elif "parts" in comp and (comp.get("validation") or {}).get("intent") == "process" and mode in ("auto", "short"):
        # "કેવી રીતે ...?" asks for the process. If the description names a process that the source defines, that
        # definition is the answer; a sentence that merely repeats the question's words is not.
        alt = _concept_fallback(con, question, res, edition_ids, chapter_id)
        if alt:
            comp, eff_mode = {**alt, "validation": comp.get("validation")}, "definition"
    if comp.get("abstain") in ("definition_not_found", "concept_not_supported") and scope.get("_soft_definition"):
        # English "What is ...?" may ask for a fact, not a definition ("What is the pH value of a neutral solution?").
        # Accept a factual answer only when ONE source sentence carries every word of the question.
        q2 = _DEF_TAIL.sub("", question).strip(" ?.:,") + " જણાવો"
        c2, r2, m2 = _attempt(con, q2, "short", "short", marks, edition_ids, chapter_id)
        if "parts" in c2 and len(r2["terms"]) >= 3 and all(t["term"] for t in r2["terms"]):
            need = {t["term"] for t in r2["terms"]}
            full = [p for p in c2["parts"] if p["kind"] == "sentence" and need <= set(g.content_terms(p["text"]))]
            if full:
                comp, res, eff_mode = {**c2, "parts": full[:1]}, r2, "short"
    if "abstain" in comp:
        out = {**_abstain(comp["abstain"], res), "mode": eff_mode, "validation": comp.get("validation")}
        if comp.get("suggestions"):
            out["suggestions"] = comp["suggestions"]
        return out

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
               "note": comp.get("note"), "length_supported": comp.get("length_supported"), "support_gaps": comp.get("gaps") or [],
               "evidence": evidence, "citations": citations, "verification": verification,
               "retrieved": [{"chunk_id": r["id"], **r["scores"]} for r in res["results"]],
               "query_terms": res["terms"], "validation": comp.get("validation"), "engine": "extractive", "engine_version": ENGINE_VERSION,
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
    role = editions[0].get("role", "textbook")
    payload["structured"] = _structure(con, payload, question, res,
                                       {"supplementary": "supplementary", "personal": "personal"}.get(role, "quotation"))
    payload["structured"]["explanation"] = explain.build(con, payload)
    if use_cache:
        cache.put(con, key, norm, key_scope, versions, payload)
    return payload


def ask(con, question: str, scope: dict | None = None, mode: str = "auto", marks: int | None = None,
        session_id: str = "anonymous", input_method: str = "typed", use_cache: bool = True, router=None,
        supplementary_edition_id: int | None = None) -> dict:
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
    original_question = question
    language = lang.detect_language(question)
    translation = lang.to_gujarati_query(question)
    if translation:
        question = g.normalize_text(translation["query"])      # Gujarati working form; the original is kept for display
    norm = g.search_key(question)
    if translation and mode == "auto" and translation["intent"] in ("definition", "difference", "formula", "steps"):
        mode = translation["intent"]
        if mode == "definition":
            scope["_soft_definition"] = True
    scope.setdefault("session", session_id)
    editions = resolve_scope(con, scope)
    if language["language"] == "hi":
        payload = {**_abstain("language_not_supported"), "mode": mode}
    elif not editions:
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
            # every edition was searched on its own; its evidence is kept apart and never stands in for another edition
            per = [{"edition_id": v[0]["id"], "edition": v[0]["edition_label"], "book_title": v[0]["title"], "status": o["status"],
                    "reason": o.get("reason"), "reason_gu": o.get("reason_gu"), "answer": o.get("answer"),
                    "evidence": o.get("evidence") or [], "citations": o.get("citations") or [], "verification": o.get("verification"),
                    "trust": (o.get("structured") or {}).get("trust"),
                    "explanation": (o.get("structured") or {}).get("explanation"),
                    "message": None if o["status"] == "answered" else "આ આવૃત્તિમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી."}
                   for v, o in outs]
            answered = [(v, o) for v, o in outs if o["status"] == "answered"]
            missing = [x["edition"] for x in per if x["status"] != "answered"]
            miss_txt = (" આ આવૃત્તિમાં આધાર મળ્યો નથી: " + ", ".join(missing) + ".") if missing else ""
            if not answered:
                payload = dict(outs[0][1])
                payload["edition_note"] = "પસંદ કરેલી દરેક આવૃત્તિ અલગ તપાસી છે; એકેય આવૃત્તિમાં પૂરતો આધાર મળ્યો નથી."
            elif len(answered) == 1 or len({g.search_key(o["answer"]["text"]) for _, o in answered}) == 1:
                payload = dict(answered[-1][1])
                payload["edition_note"] = ("એક કરતાં વધુ આવૃત્તિ પસંદ થયેલી છે; દરેક અલગ તપાસી છે. આ ઉત્તર આ આવૃત્તિમાંથી છે: "
                                           + answered[-1][0][0]["edition_label"]
                                           + (" (બીજી આવૃત્તિમાં પણ આ જ લખાણ છે)." if len(answered) > 1 else ".") + miss_txt)
            else:
                payload = {"status": "edition_conflict", "mode": answered[0][1]["mode"],
                           "message": "પાઠ્યપુસ્તકની જુદી જુદી આવૃત્તિઓમાં આ પ્રશ્નનો ઉત્તર જુદો છે. દરેક આવૃત્તિનો ઉત્તર અલગ બતાવ્યો છે." + miss_txt,
                           "editions": [x for x in per if x["status"] == "answered"],
                           "answer": None, "evidence": [], "citations": [], "engine": "extractive",
                           "engine_version": ENGINE_VERSION, "cache": {"hit": False},
                           "external_api_calls": sum(o.get("external_api_calls", 0) for _, o in answered),
                           "verification": {"verified": all(o["verification"]["verified"] for _, o in answered)}}
            payload["edition_results"] = per
            payload["editions_missing_evidence"] = missing
    payload = dict(payload)
    if payload["status"] == "edition_conflict":
        payload["structured"] = {"simple_answer": [], "key_points": [], "basis": [], "word_help": [], "english_terms": [], "notes": [],
                                 "trust": _trust("partial", ["પાઠ્યપુસ્તકની આવૃત્તિઓમાં ઉત્તર જુદો છે; દરેક આવૃત્તિ અલગ બતાવી છે."])}
    if payload.get("structured"):
        payload["structured"] = {**payload["structured"], "question": original_question}
    payload["supplementary"] = None
    if supplementary_edition_id:
        sup = resolve_scope(con, {"edition_id": int(supplementary_edition_id)}, roles=("supplementary",))
        if sup:
            sp = _answer_variant(con, question, norm, sup, {"edition_id": sup[0]["id"]}, mode, marks, use_cache, None)
            payload["supplementary"] = {
                "label_gu": SOURCE_TYPE_LABELS["supplementary"],
                "notice_gu": "નીચેની માહિતી તમે પસંદ કરેલા પૂરક સ્રોતમાંથી છે. તે તમારા પાઠ્યપુસ્તકનો ભાગ નથી અને પરીક્ષા માટે પાઠ્યપુસ્તકને જ આધાર માનવો.",
                "source": {"edition_id": sup[0]["id"], "title": sup[0]["title"], "license": sup[0]["license"],
                           "attribution": sup[0]["attribution"], "source_url": sup[0]["source_url"]},
                **{k: sp.get(k) for k in ("status", "answer", "structured", "citations", "evidence", "verification", "reason",
                                          "reason_gu", "message", "note", "mode", "mode_label", "unmatched_terms")}}
    payload["language"] = language["language"]
    payload["query_translation"] = ({"working_question": question, "terms": translation["mapped"], "unmapped": translation["unmapped"],
                                     "note_gu": "અંગ્રેજી શબ્દોને શોધ માટે ગુજરાતી પારિભાષિક શબ્દોમાં ફેરવ્યા છે. શોધ અને ઉત્તર ગુજરાતી સ્રોતના લખાણમાંથી જ થાય છે.",
                                     "note_en": "English terms were mapped to Gujarati terms for searching. Search and answer use only the text of the Gujarati-medium source."}
                                    if translation else None)
    payload["question"] = original_question
    payload["normalized_question"] = norm
    scope.pop("session", None)
    scope.pop("_soft_definition", None)
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
