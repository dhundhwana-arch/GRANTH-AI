"""Question language detection and English → Gujarati query mapping.

The corpus is Gujarati. An English or mixed question is mapped onto Gujarati search terms with a small curated
term list (data/glossary/en_gu_terms.json). This is a retrieval aid only: the answer itself is still copied from the
selected source, and an English word that is not in the list is reported as unmatched instead of being guessed.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'’]*")

EN_STOP = frozenset("""a an the is are was were be been am do does did of in on at to for from by with as and or but if then than that this
these those it its what which who whom whose when where why how me my we our you your i please tell give write state explain describe
define definition meaning mean means called known between difference differentiate distinguish formula equation about
there their they can could would should will shall has have had not no yes into out up down also any some each one two
short long note answer question law?""".split())

_INTENTS = [
    ("difference", re.compile(r"\b(?:difference|differences|differentiate|distinguish)\s+between\s+(.+?)\s+and\s+(.+?)\s*[?.!]*$", re.I)),
    ("steps", re.compile(r"\bstep[\s-]*by[\s-]*step\b|\bworked example\b|\bsolved example\b", re.I)),
    ("formula", re.compile(r"\b(?:formula|equation)\b", re.I)),
    ("definition", re.compile(r"^\s*(?:what\s+(?:is|are)|define|definition\s+of|what\s+do\s+you\s+mean\s+by|what\s+is\s+meant\s+by|meaning\s+of)\b", re.I)),
    ("why", re.compile(r"\bwhy\b", re.I)),
    ("how_many", re.compile(r"\bhow\s+(?:many|much)\b", re.I)),
    ("how", re.compile(r"^\s*how\b", re.I)),
    ("where_from", re.compile(r"\bfrom\s+where\b|\bwhere\b.*\bfrom\s*[?.!]*$", re.I)),
    ("where", re.compile(r"\bwhere\b", re.I)),
    ("when", re.compile(r"\bwhen\b", re.I)),
]


def detect_language(text: str) -> dict:
    """Script-based: 'gu', 'en', 'hi', 'mixed' (Gujarati with Latin words) or 'other'."""
    gu = sum(1 for ch in text if "\u0a80" <= ch <= "\u0aff")
    hi = sum(1 for ch in text if "\u0900" <= ch <= "\u097f")
    words = _LATIN_WORD.findall(text)
    en_words = [w for w in words if len(w) > 2 or w.lower() in EN_STOP]
    if hi > gu and hi > 3:
        lang = "hi"
    elif gu == 0 and words:
        lang = "en"
    elif gu and en_words:
        lang = "mixed"
    elif gu:
        lang = "gu"
    else:
        lang = "other"
    return {"language": lang, "gujarati_letters": gu, "devanagari_letters": hi, "latin_words": len(words)}


@lru_cache(maxsize=1)
def glossary() -> dict:
    data = json.loads((ROOT / "data" / "glossary" / "en_gu_terms.json").read_text(encoding="utf-8"))
    return {k.lower().replace("’", "'"): v for k, v in data["terms"].items()}


@lru_cache(maxsize=1)
def _phrases() -> list:
    return sorted(glossary(), key=len, reverse=True)


@lru_cache(maxsize=1)
def reverse_glossary() -> dict:
    out: dict = {}
    for en, gu in glossary().items():
        if gu not in out or len(en) > len(out[gu]):          # prefer the fullest English form
            out[gu] = en
    return out


def _map_terms(text: str) -> tuple[str, list, list]:
    """Replace glossary phrases with Gujarati; return (text, mapped pairs, leftover English content words)."""
    work, mapped = text.replace("’", "'"), []
    for en in _phrases():
        pat = re.compile(r"(?<![A-Za-z])" + re.escape(en) + r"(?![A-Za-z])", re.I)
        if pat.search(work):
            work = pat.sub(" " + glossary()[en] + " ", work)
            mapped.append({"en": en, "gu": glossary()[en]})
    leftover = [w for w in _LATIN_WORD.findall(work) if w.lower().strip("'") not in EN_STOP and len(w) > 2]
    return work, mapped, leftover


def _strip_english(text: str, keep: list) -> str:
    keepset = {k.lower() for k in keep}

    def repl(m):
        w = m.group(0)
        return w if (w.lower() in keepset or (len(w) <= 2 and w.lower() not in EN_STOP)) else " "
    return re.sub(r"\s+", " ", _LATIN_WORD.sub(repl, text)).strip(" ?.!,")


def to_gujarati_query(question: str) -> dict | None:
    """Return a Gujarati working question for an English / mixed question, or None when nothing needs mapping."""
    info = detect_language(question)
    if info["language"] not in ("en", "mixed"):
        return None
    if info["language"] == "mixed":
        work, mapped, leftover = _map_terms(question)
        if not mapped:
            return None                                      # e.g. formulas or symbols inside a Gujarati question
        return {"query": re.sub(r"\s+", " ", work).strip(), "mapped": mapped, "unmapped": leftover, "intent": None,
                "language": "mixed"}
    intent, groups = None, None
    mapped_text = _map_terms(question)[0]          # "quadratic equation" must not look like a request for a formula
    for name, pat in _INTENTS:
        m = pat.search(mapped_text if name in ("formula", "steps") else question)
        if m:
            intent, groups = name, m.groups()
            break
    if intent == "difference":
        sides, mapped, leftover = [], [], []
        for side in groups:
            w, mp, lo = _map_terms(side)
            sides.append(_strip_english(w, lo))
            mapped += mp
            leftover += lo
        query = f"{sides[0]} અને {sides[1]} વચ્ચેનો તફાવત લખો"
    else:
        # English is head-first ("focal length of a concave mirror"), Gujarati head-final ("અંતર્ગોળ અરીસાની કેન્દ્રલંબાઈ"):
        # keep that structure so the engine knows WHICH concept is asked about.
        segs, mapped, leftover = [], [], []
        for seg in re.split(r"(?<![A-Za-z])of(?![A-Za-z])", question, flags=re.I):
            w, mp, lo = _map_terms(seg)
            mapped += mp
            leftover += lo
            c = _strip_english(w, lo)
            if c:
                segs.append(c)
        core = " ની ".join(reversed(segs))
        tail = {"definition": " એટલે શું?", "formula": " સૂત્ર લખો", "steps": " ઉદાહરણ પગલાંવાર સમજાવો", "why": " શા માટે?",
                "when": " ક્યારે?", "how_many": " કેટલા?", "how": " કેવી રીતે?", "where_from": " ક્યાંથી?", "where": " ક્યાં?"}.get(intent, " સમજાવો")
        query = core + tail
    return {"query": query, "mapped": mapped, "unmapped": leftover, "intent": intent, "language": "en"}
