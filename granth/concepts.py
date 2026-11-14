"""What exactly is the student asking about?

Three small, deterministic tools used by the answer engine:

* ``analyse``  - split a Gujarati noun phrase into the HEAD concept (what is asked) and its MODIFIERS (whose / of what).
  Gujarati is head-final: in "અંતર્ગોળ અરીસાની કેન્દ્રલંબાઈ" the question is about કેન્દ્રલંબાઈ, not about the mirror.
* ``match_definition`` - decide whether a term defined by a source sentence IS the requested concept.
* ``expansions`` - everyday words / concept aliases used to FIND evidence when the student's own words are not in the
  source. Expansion never supplies answer text and an answer found this way is never reported as "Verified".
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from . import gujarati as g

ROOT = Path(__file__).resolve().parent.parent
_GEN = re.compile(r"(નું|ની|નો|ના|નાં)$")
_GEN_WORDS = {"નું", "ની", "નો", "ના", "નાં"}
# words that merely END in a genitive-looking syllable (pronouns, adjectives, ordinary nouns)
_NOT_GEN = re.compile(r"^(પોતાન|તેન|એન|જેન|કોન|આન|તેમન|જેમન|નાન|જૂન|ચૂન|સોન|ગુન|ઘટન|રચન|સૂચન|કલ્પન|વિન|યોજન|સંભાવન|સ્થાપન|વેદન|ભાવન|તુલન|ગણન|પ્રાર્થન|કેટલ|ઊન|પાન|માન|દાન|સ્થાન|જ્ઞાન|વિજ્ઞાન|તાપમાન|વિદ્યુતસ્થિતિમાન|સમાન|અનુમાન|મેદાન|મકાન|દુકાન|વાહન|દહન|વહન|શ્વસન|પાચન|ઉત્સર્જન|પરાવર્તન|વક્રીભવન|જીવન|પવન|ભોજન|સાધન|બંધન|વજન|કારણન)(ું|ી|ો|ા|ાં)$")

# words that name the ASPECT wanted (unit, formula, use ...) rather than the thing itself
FACETS = {
    "unit": ("એકમ",), "formula": ("સૂત્ર", "સમીકરણ"), "application": ("ઉપયોગ", "વપરાય", "ઉપયોગી"),
    "types": ("પ્રકાર",), "property": ("ગુણધર્મ", "લક્ષણ"), "function": ("કાર્ય",), "example": ("ઉદાહરણ",),
    "instrument": ("સાધન",), "value": ("મૂલ્ય",),
}
_FACET_STEMS = {st: name for name, words in FACETS.items() for w in words for st in g.content_terms(w)}


def analyse(phrase: str) -> dict:
    """{'terms': ordered stems, 'head': stems after the last genitive word, 'modifiers': stems before it, 'facet': name|None}"""
    words = [w for w in re.split(r"\s+", g.normalize_text(phrase)) if w]
    items = []                                   # (stems, is_genitive)
    for w in words:
        w = w.strip("?.,!;:\"'()")
        if w in _GEN_WORDS:
            if items:
                items[-1] = (items[-1][0], True, items[-1][2])
            continue
        st = g.content_terms(w)
        if st:
            items.append((st, bool(_GEN.search(w)) and len(w) > 3 and not _NOT_GEN.match(w), w))
    last_gen = max((i for i, it in enumerate(items) if it[1]), default=-1)
    if last_gen == len(items) - 1:               # phrase ends with a genitive: nothing follows it, so no split
        last_gen = -1
    mods = [s for it in items[:last_gen + 1] for s in it[0]]
    head = [s for it in items[last_gen + 1:] for s in it[0]]
    terms = mods + head
    mod_words = " ".join(it[2] for it in items[:last_gen + 1])
    head_words = " ".join(it[2] for it in items[last_gen + 1:])
    facet = next((_FACET_STEMS[s] for s in reversed(terms) if s in _FACET_STEMS), None)
    head_facet = _FACET_STEMS.get(head[0]) if (mods and head) else None
    return {"terms": terms, "head": head, "modifiers": mods, "facet": facet, "head_facet": head_facet,
            "mod_words": mod_words, "head_words": head_words}


@lru_cache(maxsize=1)
def _generic() -> frozenset:
    words = "નિયમ સૂત્ર તફાવત સિદ્ધાંત પ્રક્રિયા ક્રિયા રીત ઘટના પદાર્થ વસ્તુ ભાગ"
    return frozenset(g.content_terms(words)) | frozenset(_FACET_STEMS)


def all_facet_stems() -> frozenset:
    return frozenset(_FACET_STEMS)


def facet_stems(name: str) -> set:
    return {st for st, n in _FACET_STEMS.items() if n == name}


def match_definition(asked: list[str], asked_modifiers: list[str], defined_term: str, sentence: str) -> dict | None:
    """Compare the requested concept (ordered stems) with a term a sentence defines.

    Returns None when the defined term is NOT the requested concept, otherwise
    {'kind': 'exact' | 'fuller_name' | 'head_only', 'missing': [modifier stems the sentence does not mention]}.
    """
    d = analyse(defined_term)
    if not asked or not d["terms"]:
        return None
    a_set, d_set = set(asked), set(d["terms"])
    if a_set == d_set:
        return {"kind": "exact", "missing": []}
    if asked[-1] != d["terms"][-1]:
        return None                              # different head noun: a related sentence, not the concept asked for
    if a_set < d_set:
        # the source uses a fuller name ("પ્રકાશનું પરાવર્તન" for "પરાવર્તન"); allowed only when the extra words are
        # its own "of ..." modifiers. "જારક શ્વસન" is a narrower concept than "શ્વસન", not a fuller name.
        extra = d_set - a_set
        if a_set <= _generic():
            return None                          # "નિયમ એટલે શું?" is not a request for "ઓહ્મનો નિયમ"
        return {"kind": "fuller_name", "missing": []} if extra <= set(d["modifiers"]) else None
    if d_set < a_set:
        # the source defines the head concept in general; the student's qualifiers must be checked separately
        sent = set(g.content_terms(sentence))
        return {"kind": "head_only", "missing": [t for t in asked if t not in d_set and t not in sent]}
    return None


# ----------------------------------------------------------------------------- expansion (retrieval aid only)
@lru_cache(maxsize=1)
def _data() -> dict:
    raw = json.loads((ROOT / "data" / "glossary" / "gu_synonyms.json").read_text(encoding="utf-8"))
    words = {}
    for k, alts in raw["words"].items():
        for st in g.content_terms(k) or [g.fold(k)]:
            words.setdefault(st, [])
            for a in alts:
                if a not in words[st]:
                    words[st].append(a)
    concepts = []
    for c in raw["concepts"]:
        concepts.append({"term": c["term"],
                         "gu": [{s for w in keys for s in g.content_terms(w)} for keys in c.get("gu", [])],
                         "en": [{w.lower() for w in keys} for keys in c.get("en", [])]})
    return {"words": words, "concepts": concepts}


def synonyms(stem: str) -> list[str]:
    return _data()["words"].get(stem, [])


def concept_for(gujarati_question: str, english_question: str | None = None) -> str | None:
    """A named concept whose everyday description matches the question (all key words present), else None."""
    stems = set(g.content_terms(gujarati_question))
    expanded = set(stems)
    for s in stems:
        for alt in synonyms(s):
            expanded.update(g.content_terms(alt))
    en = set(re.findall(r"[a-z]+", (english_question or "").lower()))
    def has(keys):
        return all(any(x == k or (len(k) >= 2 and x.startswith(k)) for x in expanded) for k in keys)
    for c in _data()["concepts"]:
        if any(has(keys) for keys in c["gu"]) or (en and any(keys <= en for keys in c["en"])):
            return c["term"]
    return None
