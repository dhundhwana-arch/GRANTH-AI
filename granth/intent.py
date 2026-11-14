"""Question understanding: WHAT KIND of answer does the student want?

`analyse` reads only the question. It returns the intent (unit, organ, place, reason, choice ...), the cue words that
express that intent (they describe the question, not the topic) and, for "X છે કે Y?" questions, the two options.
Nothing here is ever shown as an answer; it only tells `granth.validate` what a source sentence must contain.
"""
from __future__ import annotations

import re

from . import gujarati as g, polarity

# intent -> Gujarati label shown to the student ("you asked for ...")
LABELS = {
    "choice": "બેમાંથી કયું", "reverse_unit": "કઈ રાશિનો એકમ", "unit": "એકમ", "instrument": "માપવાનું સાધન",
    "organ": "અંગ", "source": "ક્યાંથી (સ્રોત)", "place": "ક્યાં (સ્થાન)", "reason": "કારણ", "quantity": "કેટલું (સંખ્યા)",
    "naming": "નામ", "use": "ઉપયોગ", "types": "પ્રકાર", "function": "કાર્ય", "process": "કેવી રીતે (પ્રક્રિયા)",
    "example": "ઉદાહરણ", "between": "કોની વચ્ચે", "means": "શેના વડે (માધ્યમ)", "range": "ક્યાંથી ક્યાં સુધી", "relation": "સંબંધ", "fact": "હકીકત",
}
# one sentence is the whole answer for these
SINGLE = frozenset({"choice", "reverse_unit", "unit", "instrument", "organ", "source", "place", "quantity", "naming", "between", "range", "means"})

_CHOICE = re.compile(r"(\S+)\s+(?:(?:હોય\s+)?છે\s+)?કે\s+(\S+?)\s*(?:(?:હોય\s+)?છે)?\s*[?？]?\s*$")
_RULES = [
    ("reverse_unit", re.compile(r"(શેનો|શાનો|કોનો|કઈ\s+રાશિનો|કયા\s+\S+નો)\s+એકમ")),
    ("unit", re.compile(r"(?<!\S)એકમ")),
    ("instrument", re.compile(r"(?<!\S)સાધન|(?<!\S)શેનાથી\s+મ[ાપ]|(?<!\S)શેના\s+વડે\s+મ[ાપ]|(?<!\S)શાનાથી\s+મ[ાપ]")),
    ("organ", re.compile(r"(?<!\S)અંગ")),
    ("naming", re.compile(r"ને\s+શું\s+કહે|(?<!\S)શું\s+કહેવાય|(?<!\S)શું\s+કહેવામાં|(?<!\S)કયા\s+નામે|નું\s+નામ\s+(?:શું|જણાવો|આપો|લખો)")),
    ("reason", re.compile(r"(?<!\S)શા\s*માટે|(?<!\S)કેમ(?!\S)|(?<!\S)કારણ|(?<!\S)શાથી|(?<!\S)શાને\s+લીધે|(?<!\S)શેને\s+લીધે")),
    ("range", re.compile(r"(?<!\S)(?:ક્યાંથી|કેટલાથી|શેનાથી)\s+(?:ક્યાં|કેટલા|શેના)\s*સુધી")),
    ("means", re.compile(r"(?<!\S)(?:શેના|શાના|કોના)\s+(?:વડે|દ્વારા|થકી)|(?<!\S)(?:શેનાથી|શાનાથી)(?!\S)")),
    ("use", re.compile(r"(?<!\S)(?:ઉપયોગ|વપરા|વાપર)")),
    ("source", re.compile(r"(?<!\S)ક્યાંથી|(?<!\S)શેમાંથી|(?<!\S)શામાંથી|(?<!\S)કયા\s+સ્રોત|(?<!\S)સ્રોત\s+(?:કયો|શું)")),
    ("place", re.compile(r"(?<!\S)ક્યાં(?!થી)|(?<!\S)શેમાં(?!થી)|(?<!\S)શામાં(?!થી)|(?<!\S)કઈ\s+જગ્યા|(?<!\S)કયા\s+ભાગમાં|(?<!\S)કયા\s+અંગમાં")),
    ("relation", re.compile(r"(?<!\S)સંબંધ")),
    ("between", re.compile(r"(?<!\S)વચ્ચે")),
    ("quantity", re.compile(r"(?<!\S)કેટલ")),
    ("types", re.compile(r"(?<!\S)પ્રકાર")),
    ("function", re.compile(r"(?<!\S)(?:કાર્ય|કામ|ભૂમિકા)")),
    ("process", re.compile(r"(?<!\S)(?:કેવી|કઈ)\s+રીતે")),
    ("example", re.compile(r"(?<!\S)(?:ઉદાહરણ|દાખલ)")),
]
# words that express the intent itself; they are not part of the topic
_CUES = {
    "reverse_unit": "એકમ રાશિ", "unit": "એકમ", "instrument": "સાધન માપવા મપાય માપ માપવાનું માપવું", "organ": "અંગ",
    "naming": "નામ", "reason": "કારણ જરૂર જરૂરી", "source": "સ્રોત", "place": "જગ્યા ભાગ સ્થાન", "quantity": "",
    "types": "પ્રકાર", "use": "ઉપયોગ ઉપયોગી વપરાય વાપરવું વપરાશ", "function": "કાર્ય કામ ભૂમિકા", "process": "રીત",
    "example": "ઉદાહરણ દાખલો", "between": "", "means": "", "range": "", "relation": "સંબંધ", "choice": "", "fact": "",
}


def _stems(words: str) -> set:
    out = set()
    for w in words.split():
        out.update(g.content_terms(w) or [g.stem(g.fold(w))])
        out.add(g.fold(w))
    return out


def analyse(question: str) -> dict:
    q = g.normalize_text(question or "").strip()
    intent, options = "fact", []
    m = _CHOICE.search(q)
    if m:
        a, b = g.content_terms(m.group(1)), g.content_terms(m.group(2))
        if len(a) == 1 and len(b) == 1 and a != b:
            intent, options = "choice", [a[0], b[0]]
    if intent == "fact":
        for name, rx in _RULES:
            if rx.search(q):
                intent = name
                break
    # Verb forms. The same fact is often told with another verb or another form of it, so a verb is a SOFT word:
    # it helps to find the sentence, but its absence alone does not disqualify a sentence (the answer is then
    # "Partially supported"). Recognised by standard Gujarati grammar only, never by a list of topic words.
    raw = [t for t in g.tokenize(q)]
    soft, part = set(), set()
    last = len(raw) - 1
    while last >= 0 and raw[last] in g.STOPWORDS:
        last -= 1
    for i, t in enumerate(raw):
        if t in g.STOPWORDS:
            continue
        nxt = raw[i + 1] if i + 1 < len(raw) else ""
        nxt2 = raw[i + 2] if i + 2 < len(raw) else ""
        verb = False
        if i == last and intent != "choice" and _VERB_END.search(t) and not (_case_marked(t) and not t.endswith(_GERUND)):
            verb = True                                  # "... મેળવે છે?", "... જોડાય છે?", "... લગાવવામાં આવે છે?"
        elif t.endswith(_GERUND):
            verb = True                                  # બનીને, ગણવામાં, વાપરવાથી
        elif t.endswith(_FINITE_END) and (nxt in _CLAUSE or (nxt in _AUX and nxt2 in _CLAUSE)):
            verb = True                                  # "નીકળે તેને", "કરડે ત્યારે", "રાખે છે તેમને"
        if verb:
            soft.update(g.content_terms(t))
        elif i != last and t.endswith(_PARTICIPLE) and nxt and nxt not in g.STOPWORDS:
            part.update(g.content_terms(t))      # "રોકતા ગુણધર્મ": looks like a participle; `validate.plan` decides with the book's vocabulary
    return {"question": q, "negated": sorted(polarity.negated(q)), "intent": intent, "label": LABELS[intent], "options": options, "cues": _stems(_CUES[intent]),
            "soft": soft, "participles": part - soft, "single": intent in SINGLE, "wh": bool(_WH.search(q))}


_WH = re.compile(r"(?<!\S)(?:કયા|કયો|કઈ|કયું|કયાં|કોણ|કેવ\S*|શું|શેન\S*)(?!\S)")
_VERB_END = re.compile("(" + "|".join(g.fold(x) for x in ("ે", "ાય", "શે", "વામાં", "ી", "તી", "તો", "તું", "તા", "યું", "યો", "યા", "ીએ", "ેલો", "ેલી", "ેલું", "ેલા", "ેલાં", "વું")) + ")$")
_CASE = tuple(g.fold(x) for x in ("ને", "થી", "માં", "નું", "નો", "ની", "ના", "પર"))
_PARTICIPLE = tuple(g.fold(x) for x in ("તા", "તી", "તો", "તું", "તાં"))
_GERUND = tuple(g.fold(x) for x in ("ીને", "વામાં", "વાથી", "વાની", "વાનું"))
_FINITE_END = tuple(g.fold(x) for x in ("ે", "ાય"))
_CLAUSE = frozenset(g.fold(x) for x in ("તેને", "તેમને", "તે", "ત્યારે", "તો", "તેનું", "તેનો", "તેની"))
_AUX = frozenset(g.fold(x) for x in ("છે", "હોય"))
_ROOT_END = tuple(sorted((g.fold(x) for x in ("વામાં", "વાથી", "વાની", "વાનું", "વા", "વ", "ાય", "ે", "ીને", "ેલ", "ત", "્ય", "ી", "્યા")), key=len, reverse=True))


def _case_marked(tok: str) -> bool:
    return any(tok.endswith(c) and g._cluster_len(tok[: -len(c)]) >= 2 for c in _CASE)


def verb_root(stem: str) -> str:
    for suf in _ROOT_END:
        if stem.endswith(suf) and len(stem) - len(suf) >= 2:
            return stem[: -len(suf)]
    return stem


def is_cue(an: dict, stem: str) -> bool:
    if stem in an["cues"]:
        return True
    if an["intent"] in ("instrument", "unit") and stem.startswith(("માપ", "મપા")):
        return True
    if an["intent"] == "use" and stem.startswith(("વપરા", "વાપર", "ઉપયોગ")):
        return True
    return False
