"""Study aids built strictly from stored textbook chunks: definitions, vocabulary (dictionary),
chapter revision and practice questions. Nothing here generates new facts: every item is a verbatim
textbook sentence (or a blank cut out of one) with its chunk id and page number."""
from __future__ import annotations

import re
from collections import Counter

from . import gujarati as g

_KAHE = ("કહે", "કહેવાય", "કહેવામાં")
MAX_TERM_TOKENS = 6
PRACTICE_DISCLAIMER = ("આ મહાવરાના પ્રશ્નો પાઠ્યપુસ્તકના લખાણ પરથી આપમેળે બનાવેલા છે. "
                       "પરીક્ષામાં આ જ પ્રશ્નો પુછાશે તેવો કોઈ દાવો નથી.")


def find_definitions(sentence: str) -> list[str]:
    """Terms that a textbook sentence defines.

    Recognised textbook patterns:  '<...>ને <TERM> કહે છે.'  ·  '<...>ને <TERM1> અને <...>ને <TERM2> કહે છે.'
    ·  '<TERM> એટલે <...>'.  Heuristic and conservative; returns [] when unsure.
    """
    s = sentence.strip()
    toks = s.replace(",", " , ").split()
    terms: list[str] = []
    if len(toks) >= 3 and "એટલે" in toks[1:4] and not s.endswith("?"):
        i = toks.index("એટલે")
        terms.append(" ".join(toks[:i]))
    if any(t.startswith(_KAHE) for t in toks) and not s.endswith("?"):
        for i, t in enumerate(toks):
            if len(t) > 3 and t.endswith("ને") and t != "અને":
                cand = []
                for u in toks[i + 1:i + 2 + MAX_TERM_TOKENS]:
                    if u.startswith(_KAHE) or u == "અને":
                        if cand:
                            terms.append(" ".join(cand))
                        break
                    if u == "," or (len(u) > 3 and u.endswith("ને")):
                        break
                    cand.append(u)
    out = []
    for t in terms:
        t = t.strip(" ,;:")
        # drop leading demonstratives ("તે બે બિંદુઓ વચ્ચેનો X" -> keep whole phrase but strip a leading 'તે')
        t = re.sub(r"^(તે|આ|એ)\s+", "", t)
        if t and g.content_terms(t) and t not in out:
            out.append(t)
    return out


def term_key(term: str) -> str:
    return " ".join(g.content_terms(term)) or g.fold(term)


def build_vocabulary(con, edition_id: int) -> int:
    rows = con.execute("SELECT * FROM text_chunks WHERE edition_id=? ORDER BY chunk_index", (edition_id,)).fetchall()
    seen: set[tuple] = set()
    n = 0
    by_chapter: dict = {}
    for r in rows:
        by_chapter.setdefault(r["chapter_id"], []).append(r)

    def add(r, word, kind, explanation, context):
        nonlocal n
        key = (r["chapter_id"], term_key(word), kind)
        if key in seen:
            return
        seen.add(key)
        con.execute("INSERT INTO vocabulary(edition_id, chapter_id, word, word_key, kind, explanation, context, chunk_id,"
                    " page_number) VALUES (?,?,?,?,?,?,?,?,?)",
                    (edition_id, r["chapter_id"], word, term_key(word), kind, explanation, context, r["id"], r["page_number"]))
        n += 1

    df = Counter()
    for r in rows:
        df.update(set(g.content_terms(r["text"])))
    for chapter_id, crow in by_chapter.items():
        sentences = [(r, s) for r in crow if r["kind"] in ("paragraph", "example") for s in g.split_sentences(r["text"])]
        explained = set()
        for r, s in sentences:
            for term in find_definitions(s):
                add(r, term, "textbook_definition", s, s)
                explained.add(term_key(term))
        for r in crow:
            if r["kind"] != "glossary":
                continue
            m = re.match(r"^(\S.{0,40}?)\s+[—–\-:]\s+(\S.*)$", r["text"])
            if not m:
                continue
            word, gloss = m.group(1).strip(), m.group(2).strip()
            wk = set(g.content_terms(word))
            ctx = next((s for _, s in sentences if wk and wk <= set(g.content_terms(s))), r["text"])
            add(r, word, "textbook_glossary", gloss, ctx)
            explained.add(term_key(word))
        # long, rare words that the book uses but never explains: context only, no meaning is invented
        cands = {}
        for r, s in sentences:
            for w in re.findall(r"[\u0A80-\u0AFF]{9,}", s):
                k = term_key(w)
                if k and k == g.fold(w) and k not in explained and all(k not in e and e not in k for e in explained) and df[k] <= 2:
                    cands.setdefault(k, (r, w, s))
        for k in sorted(cands, key=lambda k: (-len(k), k))[:8]:
            r, w, s = cands[k]
            add(r, w, "context_only", None, s)
    return n


KIND_LABELS = {
    "textbook_definition": "પાઠ્યપુસ્તકની વ્યાખ્યા",
    "textbook_glossary": "સરળ સમજૂતી (પાઠ્યપુસ્તકના શબ્દાર્થમાંથી)",
    "context_only": "માત્ર સંદર્ભ (પાઠ્યપુસ્તકમાં અર્થ આપેલો નથી)",
}


def _vocab_row(r) -> dict:
    d = dict(r)
    d["kind_label"] = KIND_LABELS[d["kind"]]
    d["origin"] = "textbook"
    return d


_VOCAB_SQL = ("SELECT v.*, c.number AS chapter_number, c.title AS chapter_title, e.edition_label AS edition, t.title AS book_title"
              " FROM vocabulary v LEFT JOIN chapters c ON c.id=v.chapter_id JOIN textbook_editions e ON e.id=v.edition_id"
              " JOIN textbooks t ON t.id=e.textbook_id WHERE e.permission_status='AUTHORIZED' AND e.review_status='approved' ")


def chapter_vocabulary(con, chapter_id: int) -> list[dict]:
    rows = con.execute(_VOCAB_SQL + "AND v.chapter_id=? ORDER BY v.page_number, v.id", (chapter_id,)).fetchall()
    return [_vocab_row(r) for r in rows]


def search_vocabulary(con, query: str, edition_id: int | None = None, limit: int = 30) -> list[dict]:
    key = term_key(query)
    if not key:
        return []
    sql, args = _VOCAB_SQL + "AND (v.word_key LIKE ? OR v.word_key LIKE ?)", [key + "%", "% " + key + "%"]
    if edition_id:
        sql += " AND v.edition_id=?"
        args.append(edition_id)
    rows = con.execute(sql + " ORDER BY (v.word_key=?) DESC, v.kind, v.page_number LIMIT ?", (*args, key, limit)).fetchall()
    return [_vocab_row(r) for r in rows]


def _chapter(con, chapter_id):
    return con.execute(
        "SELECT c.*, e.edition_label AS edition, e.id AS edition_id, t.title AS book_title, t.board, t.medium, t.standard,"
        " s.name_gu AS subject FROM chapters c JOIN textbook_editions e ON e.id=c.edition_id JOIN textbooks t ON t.id=e.textbook_id"
        " JOIN subjects s ON s.id=t.subject_id WHERE c.id=? AND e.permission_status='AUTHORIZED' AND e.review_status='approved'",
        (chapter_id,)).fetchone()


def chapter_revision(con, chapter_id: int) -> dict | None:
    ch = _chapter(con, chapter_id)
    if ch is None:
        return None
    chunks = con.execute("SELECT * FROM text_chunks WHERE chapter_id=? ORDER BY chunk_index", (chapter_id,)).fetchall()
    secs = con.execute("SELECT number, title, page_start FROM sections WHERE chapter_id=? ORDER BY id", (chapter_id,)).fetchall()
    out = {"chapter": dict(ch), "sections": [dict(s) for s in secs], "definitions": [], "formulas": [], "tables": [],
           "figures": [], "examples": [],
           "note": "આ પુનરાવર્તન સામગ્રીનું દરેક વાક્ય પાઠ્યપુસ્તકમાંથી શબ્દશઃ લીધેલું છે."}
    for r in chunks:
        item = {"chunk_id": r["id"], "page_number": r["page_number"], "section_title": r["section_title"], "text": r["text"]}
        if r["kind"] == "formula":
            out["formulas"].append(item)
        elif r["kind"] == "table":
            out["tables"].append(item)
        elif r["kind"] == "figure":
            out["figures"].append(item)
        elif r["kind"] == "example":
            out["examples"].append(item)
        elif r["kind"] == "paragraph":
            for s in g.split_sentences(r["text"]):
                terms = find_definitions(s)
                if terms:
                    out["definitions"].append({**item, "text": s, "terms": terms})
    return out


def practice_questions(con, chapter_id: int, limit: int = 20) -> dict | None:
    ch = _chapter(con, chapter_id)
    if ch is None:
        return None
    rev = chapter_revision(con, chapter_id)
    qs = []
    for d in rev["definitions"]:
        for term in d["terms"]:
            qs.append({"type": "definition", "question": f"વ્યાખ્યા આપો: {term}", "answer": d["text"],
                       "page_number": d["page_number"], "chunk_id": d["chunk_id"], "section_title": d["section_title"]})
            if term in d["text"] and len(d["terms"]) == 1:
                qs.append({"type": "fill_blank", "question": "ખાલી જગ્યા પૂરો: " + d["text"].replace(term, "________", 1),
                           "answer": term, "page_number": d["page_number"], "chunk_id": d["chunk_id"],
                           "section_title": d["section_title"]})
    for f in rev["formulas"]:
        body = re.sub(r"^સૂત્ર\s*[:\-]\s*", "", f["text"])
        for sep, word in (("=", "સૂત્ર"), ("→", "સમીકરણ")):
            if sep in body:
                lhs = body.split(sep, 1)[0].strip()
                qs.append({"type": "formula", "question": f"પાઠ્યપુસ્તકમાં આપેલું {word} પૂર્ણ કરો: {lhs} {sep} ________",
                           "answer": f["text"], "page_number": f["page_number"], "chunk_id": f["chunk_id"],
                           "section_title": f["section_title"]})
                break
    for s in rev["sections"]:
        qs.append({"type": "short_note", "question": f"ટૂંકનોંધ લખો: {s['title'].rstrip('?')}", "answer": None,
                   "page_number": s["page_start"], "chunk_id": None, "section_title": f"{s['number']} {s['title']}",
                   "answer_hint": f"જુઓ વિભાગ {s['number']}, પૃષ્ઠ {s['page_start']}"})
    order = {"definition": 0, "fill_blank": 1, "formula": 2, "short_note": 3}
    qs.sort(key=lambda q: (q["page_number"], order[q["type"]]))
    return {"chapter": dict(ch), "disclaimer": PRACTICE_DISCLAIMER, "questions": qs[:limit], "total_available": len(qs)}
