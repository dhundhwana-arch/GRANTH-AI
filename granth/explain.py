"""Controlled "simple explanation" (સરળ સમજૂતી) - rule based, no AI model, no paid API.

What it may do (each operation keeps the meaning of the source sentence):
  1. split one long source sentence into shorter ones at fixed, safe joints ("... છે તે પ્રક્રિયાને X કહે છે", ";");
  2. turn a definition "<વર્ણન>ને X કહે છે" into the question-answer form "કોને ‘X’ કહે છે? — <વર્ણન>ને";
  3. put an everyday word in brackets after a formal word (from data/glossary/gu_synonyms.json "plain"; labelled as
     NOT from the textbook);
  4. list the meaning of technical terms, copied word for word from the same edition (definition sentence / glossary);
  5. show an example only when the same section of the source prints one.
What it never does: add a fact, drop a fact, re-word the source freely, or invent an example.

Every explanation line carries the exact source words it was built from (`pieces`) and the chunk + page. `verify`
re-checks that (a) every piece is a verbatim substring of the quoted answer part and (b) the lines contain exactly the
content words of that part, apart from the fixed template words. If the check fails, or nothing can be simplified
safely, `available` is False and the app shows only the verified source passage.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from . import gujarati as g, study

ROOT = Path(__file__).resolve().parent.parent
LABEL = "સરળ સમજૂતી — GRANTH-AI એ ઉપરના અવતરણ પરથી નિયમો વડે બનાવી છે; આ પુસ્તકનું અવતરણ નથી"
FALLBACK = "આ ઉત્તર માટે સલામત સરળ સમજૂતી બનાવી શકાઈ નથી. ઉપર આપેલું પુસ્તકનું મૂળ લખાણ જ વાંચો."
_GLOSS = re.compile(r"\s*\[રોજિંદો શબ્દ: [^\]]*\]|\s*\((?:[a-z][a-z' -]*)\)(?=[\s.,;:?]|$)")
_T_NAME = "‘{t}’ એ એક નામ (પારિભાષિક શબ્દ) છે."
_T_WHO = "કોને ‘{t}’ કહે છે? — {d}."
_T_FIRST = "પહેલાં આ વાત સમજો: {c}."
_T_THEN = "પુસ્તક કહે છે: {r}"
_TEMPLATE_TERMS = None


def _template_terms() -> set:
    global _TEMPLATE_TERMS
    if _TEMPLATE_TERMS is None:
        _TEMPLATE_TERMS = set(g.content_terms(" ".join((_T_NAME, _T_WHO, _T_FIRST, _T_THEN)).replace("{t}", "").replace("{d}", "")
                                              .replace("{c}", "").replace("{r}", "")))
    return _TEMPLATE_TERMS


@lru_cache(maxsize=1)
def _plain() -> dict:
    raw = json.loads((ROOT / "data" / "glossary" / "gu_synonyms.json").read_text(encoding="utf-8")).get("plain", {})
    out = {}
    for k, v in raw.items():
        st = g.content_terms(k)
        if len(st) == 1:
            out[st[0]] = (k, v)
    return out


@lru_cache(maxsize=1)
def _english() -> tuple[dict, dict]:
    """(one-word stems, two-word stem pairs) -> English term, from GRANTH-AI's own word list (not textbook text)."""
    raw = json.loads((ROOT / "data" / "glossary" / "en_gu_terms.json").read_text(encoding="utf-8")).get("english_display", {})
    one, two = {}, {}
    for gu, en in raw.items():
        st = [x for w in gu.split() for x in g.content_terms(w)[:1]]
        if len(gu.split()) == 1 and len(st) == 1:
            one[st[0]] = (gu, en)
        elif len(gu.split()) == 2 and len(st) == 2:
            two[tuple(st)] = (gu, en)
    return one, two


def _digits(text: str) -> list:
    return sorted(re.findall(r"[0-9૦-૯]+(?:\.[0-9૦-૯]+)?", text))


def _restate(sentence: str) -> list[dict] | None:
    """Shorter sentences built only from the words of `sentence` plus fixed template words; None if no safe rule fits."""
    s = sentence.strip()
    terms = study.find_definitions(s)
    if len(terms) == 1 and s.endswith("."):
        t = terms[0]
        m = re.search(r"\s(?:(?:તે|આ|એ)\s+)?" + re.escape(t) + r"\s+કહે\S*\s+છે\.$", s)
        desc = s[:m.start()].strip() if m else ""
        if m and desc.endswith("ને") and len(desc) > 6:
            m2 = re.match(r"^(.+\sછે)\s+(તે\s+\S+ને)$", desc)
            if m2:
                rest = m2.group(2) + s[m.start():]
                return [{"kind": "split", "text": _T_FIRST.format(c=m2.group(1)), "pieces": [m2.group(1)]},
                        {"kind": "split", "text": _T_THEN.format(r=rest), "pieces": [rest]}]
            return [{"kind": "name", "text": _T_NAME.format(t=t), "pieces": [t]},
                    {"kind": "who", "text": _T_WHO.format(t=t, d=desc), "pieces": [t, desc]}]
    if ";" in s:
        bits = [b.strip() for b in s.split(";") if b.strip()]
        if len(bits) > 1 and all(len(g.content_terms(b)) >= 2 for b in bits):
            return [{"kind": "split", "text": b if b.endswith(".") else b + ".", "pieces": [b]} for b in bits]
    return None


def _gloss(text: str, used: set) -> tuple[str, list]:
    plain, out, added = _plain(), [], []
    for tok in text.split(" "):
        out.append(tok)
        core = tok.strip("‘’'\".,;:?()—")
        st = g.content_terms(core)
        if len(st) == 1 and st[0] in plain and st[0] not in used:
            used.add(st[0])
            word, every = plain[st[0]]
            # keep sentence punctuation after the bracket
            tail = ""
            while out[-1] and out[-1][-1] in ".,;:?":
                tail = out[-1][-1] + tail
                out[-1] = out[-1][:-1]
            out[-1] = f"{out[-1]} [રોજિંદો શબ્દ: {every}]{tail}"
            added.append({"word": word, "everyday": every, "source_type": "word_list"})
    return " ".join(out), added


def _english_gloss(text: str, used: set) -> tuple[str, list]:
    """Put the English term in round brackets after a Gujarati technical word: "હરિતદ્રવ્યની (chlorophyll)"."""
    one, two = _english()
    toks, out, added, low = text.split(" "), [], [], text.lower()
    stems = []
    for tok in toks:
        st = g.content_terms(tok.strip("‘’'\".,;:?()—")) if not tok.startswith("[") else []
        stems.append(st[0] if len(st) == 1 else None)
    i = 0
    while i < len(toks):
        hit, span = None, 1
        if i + 1 < len(toks) and (stems[i], stems[i + 1]) in two:
            hit, span = two[(stems[i], stems[i + 1])], 2
        elif stems[i] in one and not (i and (stems[i - 1], stems[i]) in two):
            hit = one[stems[i]]
        out.extend(toks[i:i + span])
        i += span
        if not hit or hit[1] in used or hit[1].lower() in low:
            continue
        used.add(hit[1])
        tail = ""
        while out[-1] and out[-1][-1] in ".,;:?":
            tail = out[-1][-1] + tail
            out[-1] = out[-1][:-1]
        out[-1] = f"{out[-1]} ({hit[1]}){tail}"
        added.append({"word": hit[0], "english": hit[1], "source_type": "word_list"})
    return " ".join(out), added


def verify(lines: list[dict], part_text: str) -> bool:
    if not lines:
        return True
    if any(piece not in part_text for ln in lines for piece in ln["pieces"]):
        return False
    orig = set(g.content_terms(part_text))
    built = set(g.content_terms(" ".join(_GLOSS.sub("", ln["text"]) for ln in lines)))
    if _digits(part_text) != _digits(" ".join(_GLOSS.sub("", ln["text"]) for ln in lines)):
        return False                                    # numbers, units and formula values must survive unchanged
    return orig <= built and (built - orig) <= _template_terms()


def build(con, payload: dict) -> dict:
    parts = payload["answer"]["parts"]
    out = {"available": False, "label_gu": LABEL, "method": "rule-based (no AI model, no external API)", "lines": [], "terms": [],
           "everyday_words": [], "english_terms": [], "examples": [], "fallback_gu": FALLBACK,
           "everyday_label_gu": "ચોરસ કૌંસમાંના રોજિંદા શબ્દો GRANTH-AI ની શબ્દસૂચિમાંથી છે; તે પુસ્તકનું લખાણ નથી.",
           "english_label_gu": "ગોળ કૌંસમાંના અંગ્રેજી શબ્દો GRANTH-AI ની શબ્દસૂચિમાંથી છે; તે પુસ્તકનું લખાણ નથી.",
           "terms_label_gu": "અઘરા શબ્દોનો અર્થ — પુસ્તકના પોતાના શબ્દોમાં", "examples_label_gu": "પુસ્તકમાં આપેલું ઉદાહરણ"}
    if payload["answer"].get("generated") or payload.get("mode") in ("steps", "formula"):
        return out
    used: set = set()
    used_en: set = set()
    changed = False
    for p in parts:
        if p["kind"] != "sentence":
            continue
        ev = [{"chunk_id": p["chunk_id"], "page_number": p["page_number"], "quote": p["text"]}]
        lines = _restate(p["text"])
        if lines and not verify(lines, p["text"]):
            lines = None
        if lines:
            changed = True
        else:
            lines = [{"kind": "same", "text": p["text"], "pieces": [p["text"]]}]
        for ln in lines:
            ln["text"], added = _gloss(ln["text"], used)
            out["everyday_words"] += added
            changed = changed or bool(added)
            before = ln["text"]
            ln["text"], added_en = _english_gloss(ln["text"], used_en)
            if added_en and _GLOSS.sub("", ln["text"]) != _GLOSS.sub("", before):
                ln["text"], added_en = before, []         # the bracket must be removable without changing the line
            out["english_terms"] += added_en
            changed = changed or bool(added_en)
            ln["evidence"] = ev
            out["lines"].append(ln)
    if not changed:
        out["lines"] = []

    answer_text = payload["answer"]["text"]
    quoted = {p["text"] for p in parts}
    ed_ids = sorted({e["edition_id"] for e in payload["evidence"]})
    if ed_ids:
        q = ("SELECT word, kind, explanation, page_number, chunk_id FROM vocabulary WHERE kind IN ('textbook_glossary','textbook_definition')"
             " AND edition_id IN (%s) ORDER BY CASE kind WHEN 'textbook_glossary' THEN 0 ELSE 1 END, id" % ",".join("?" * len(ed_ids)))
        seen = set()
        for w in con.execute(q, ed_ids):
            if (w["word"] in seen or w["word"] not in answer_text or not w["explanation"] or w["explanation"] in quoted
                    or w["explanation"] in answer_text):
                continue
            seen.add(w["word"])
            out["terms"].append({"term": w["word"], "meaning": w["explanation"], "source_type": w["kind"],
                                 "page_number": w["page_number"], "chunk_id": w["chunk_id"]})
            if len(out["terms"]) >= 5:
                break
        if payload.get("mode") in ("definition", "short", "one_line"):
            secs = sorted({e["section_id"] for e in payload["evidence"] if e.get("section_id")})
            if secs:
                q = "SELECT id, text, page_number FROM text_chunks WHERE kind='example' AND section_id IN (%s) ORDER BY chunk_index LIMIT 1" % ",".join("?" * len(secs))
                for r in con.execute(q, secs):
                    if r["text"] not in answer_text and any(t in g.content_terms(r["text"]) for t in g.content_terms(answer_text)):
                        out["examples"].append({"text": r["text"], "chunk_id": r["id"], "page_number": r["page_number"],
                                                "source_type": "textbook_example"})
    out["available"] = bool(out["lines"] or out["terms"] or out["examples"])
    return out
