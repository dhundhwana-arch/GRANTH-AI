"""Negation / polarity (Phase 5).

"ઑક્સિજન ન હોય ત્યારે ..." and "ઑક્સિજન હોય ત્યારે ..." share every content word; only the negation tells them apart.
The negation words are function words, so the search index never sees them. This module therefore reads the RAW
question (and the raw source sentence) and reports WHICH content term each negation applies to.

    negated("ઑક્સિજન ન હોય ત્યારે થતું શ્વસન")          -> {"ઓક્સિજન"}
    negated("ઑક્સિજનની ગેરહાજરીમાં થતા શ્વસનને ...")      -> {"ઓક્સિજન"}
    negated("ઑક્સિજનની હાજરીમાં થતા શ્વસનને ...")         -> set()

`conflict` compares question and evidence: a term the question negates must be negated in the evidence, and a term
the question uses positively must not be negated there. Nothing here knows any topic word.
"""
from __future__ import annotations

import re

from . import gujarati as g

# follows the noun it negates: "ઑક્સિજન વગર", "ઑક્સિજનની ગેરહાજરીમાં", "ઑક્સિજનની અછત"
_POST = ("વગર", "વિના", "સિવાય", "ગેરહાજર", "અભાવ", "અછત", "રહિત")
# negates the clause: "... ન હોય", "... નથી", "... નહીં"
_VERBAL = ("ન", "નથી", "નહીં", "નહિ", "નહી", "નહોતું", "નહોતી", "નહોતો", "ના")
# predicate words between the noun and the negation: "ઑક્સિજન હાજર ન હોય", "ઑક્સિજનની જરૂર નથી", "ઑક્સિજન મળતો નથી"
_PREDICATE = ("હાજર", "જરૂર", "ઉપલબ્ધ", "આવશ્યક", "ઉપયોગ", "વપરા", "વાપર", "મળ", "હોય", "પ્રાપ્ય", "પૂરત", "એક", "જ")
_CLAUSE_BREAK = re.compile(r"[,;:।.!?|]|\s(?:અને|તથા|પરંતુ|પણ|જ્યારે|ત્યારે|તો)\s")
_F = lambda words: tuple(g.fold(w) for w in words)  # noqa: E731
_POST_F, _VERBAL_F, _PRED_F = _F(_POST), frozenset(_F(_VERBAL)), _F(_PREDICATE)

# English, applied before translation. PRE: negates the term that follows; PRED: "X is not present/available/..."
_EN_PRE = re.compile(r"\b(?:without|absence\s+of|lack\s+of|lacking|no|non)\b[\s-]*", re.I)
_EN_NOT = re.compile(r"\b(?:not|never|cannot)\b|n't\b|n’t\b", re.I)
_EN_VERB_AFTER = re.compile(r"^\s*(?:need|needs|needed|require|requires|required|requiring|use|uses|used|using|have|has|"
                            r"involve|involves|involving|contain|contains|containing|consume|consumes|depend\s+on)\b", re.I)
_NA = g.fold("ન")
MARK = " વગર "          # the Gujarati post-position inserted into the working question for an English negation


def _term(tok: str) -> str | None:
    t = g.content_terms(tok)
    return t[0] if len(t) == 1 else None


def _is_pred(tok: str) -> bool:
    return any(tok.startswith(p) for p in _PRED_F)


def negated(text: str) -> set:
    """Content terms (stems) that a negation in `text` applies to."""
    out = set()
    for clause in _CLAUSE_BREAK.split(g.normalize_text(text or "")):
        toks = g.tokenize(clause)
        for i, tok in enumerate(toks):
            post = any(tok.startswith(p) for p in _POST_F)
            verbal = tok in _VERBAL_F and not (tok == g.fold("ના") and i != len(toks) - 1)
            if not post and not verbal:
                continue
            if tok == _NA and i + 1 < len(toks) and toks[i + 1] not in g.STOPWORDS and not _is_pred(toks[i + 1]):
                t = _term(toks[i + 1])                  # "ન ઍસિડિક, ન બેઇઝિક": the word that follows
                if t:
                    out.add(t)
                continue
            j = i - 1
            while j >= 0:
                cand = toks[j]
                t = _term(cand)
                if t and not _is_pred(cand) and not any(cand.startswith(p) for p in _POST_F):
                    out.add(t)
                    break
                if post and t is None and cand not in g.STOPWORDS:
                    break
                j -= 1
    return out


_INTERROGATIVE = re.compile(r"(?<!\S)(?:શા|શે\S*|શાન\S*|કય\S*|કઈ|કોણ|કોન\S*|કોને|કેમ|કેવ\S*|કેટલ\S*|ક્યાં\S*|ક્યારે|શું\s+કહે\S*|એટલે\s+શું)(?!\S)"
                            r"|લખો|સમજાવો|વર્ણવો|જણાવો|આપો")


def is_yes_no(question: str) -> bool:
    q = g.normalize_text(question or "")
    return bool(re.search(r"[?？]\s*$", q)) and not _INTERROGATIVE.search(q) and not re.search(r"(?<!\S)શું(?!\S)(?!\s*$)(?<!^શું)", q[1:])


def has_negation(text: str) -> bool:
    toks = g.tokenize(g.normalize_text(text or ""))
    return any(t in _VERBAL_F and t != g.fold("ના") or any(t.startswith(p) for p in _POST_F) for t in toks)


def conflict(question: str, evidence: str, shared: set | None = None) -> str | None:
    """None if the evidence has the polarity the question asks for; otherwise a short reason code.
    `shared`: terms of the question to check (default: every term the two texts share)."""
    if is_yes_no(question):
        return None                                 # "X અને Y એક છે?" - a sentence saying "... એક નથી" IS the answer
    qn, en = negated(question), negated(evidence)
    q_terms = set(g.content_terms(question)) if shared is None else set(shared) | qn
    e_terms = set(g.content_terms(evidence))
    for t in qn:
        if t in e_terms and t not in en:
            return "question_negates_" + t          # asked "without X", evidence speaks of X being present
        if t not in e_terms:
            return "negated_term_absent_" + t       # evidence does not mention X at all: it cannot settle "without X"
    for t in en:
        if t in q_terms and t not in qn:
            return "evidence_negates_" + t          # asked about X, evidence speaks of X being absent
    return None


def english_to_marked(text: str) -> tuple[str, list]:
    """Rewrite English negation so that it survives translation: the negated English word gets the marker `MARK`
    after it ("without oxygen" -> "oxygen વગર"). Returns (text, [negated English words])."""
    found = []

    def pre(m):
        rest = text[m.end():]
        w = re.match(r"(?:(?:the|any|a|an|enough|sufficient|free)\s+)*([A-Za-z][A-Za-z-]+)", rest, re.I)
        if not w:
            return m.group(0)
        found.append(w.group(1))
        return "\x00"
    out = _EN_PRE.sub(pre, text)
    # the marker goes after the word that followed each \x00
    out = re.sub(r"\x00((?:(?:the|any|a|an|enough|sufficient|free)\s+)*)([A-Za-z][A-Za-z-]+)", lambda m: m.group(1) + m.group(2) + MARK, out, flags=re.I)

    def neg(m):
        after = out2[m.end():]
        v = _EN_VERB_AFTER.match(after)
        if v:                                       # "does not need oxygen": the word after the verb
            w = re.match(r"\s*(?:(?:the|any|a|an|enough)\s+)*([A-Za-z][A-Za-z-]+)", after[v.end():], re.I)
            if w:
                found.append(w.group(1))
                return "\x01"
        w = re.match(r"\s*([A-Za-z][A-Za-z-]+)\s+(?:required|needed|necessary|present|available|used|supplied)\b", after, re.I)
        if w:                                       # "isn't oxygen required"
            found.append(w.group(1))
            return "\x03"
        return "\x02"                               # "oxygen is not present": the content word before
    out2 = out
    out3 = _EN_NOT.sub(neg, out2)
    out3 = re.sub(r"\x01(\s*\S+\s+(?:(?:the|any|a|an|enough)\s+)*)([A-Za-z][A-Za-z-]+)", lambda m: m.group(1) + m.group(2) + MARK, out3)
    out3 = re.sub(r"\x03(\s*)([A-Za-z][A-Za-z-]+)", lambda m: m.group(1) + m.group(2) + MARK, out3)
    if "\x02" in out3:
        def back(m):
            words = re.findall(r"[A-Za-z][A-Za-z-]+", m.group(1))
            skip = {"is", "are", "was", "were", "does", "do", "did", "can", "will", "be", "there", "it", "that", "which", "when", "if", "has", "have"}
            for w in reversed(words):
                if w.lower() not in skip:
                    found.append(w)
                    idx = m.group(1).rfind(w) + len(w)
                    return m.group(1)[:idx] + MARK + m.group(1)[idx:]
            return m.group(1) + " ન "
        out3 = re.sub(r"([^\x02]*)\x02", back, out3, count=1).replace("\x02", " ")
    return out3, found
