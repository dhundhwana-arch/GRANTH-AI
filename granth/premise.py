"""False-premise stage (Phase 5).

A question such as "અંતર્ગોળ અરીસો વાહનોમાં શા માટે વપરાય છે?" takes something for granted: that concave mirrors ARE
used in vehicles. Before any answer is shown, that assumption has to be found in the source.

    question -> concepts (hard terms) -> assumptions -> evidence -> check -> answer / show what the book says / refuse

Three pieces, none of which knows any topic:

* `assumptions`   - what the question presupposes, in words, for the student to read;
* `sibling_break` - a sentence that speaks about a SIBLING concept ("બહિર્ગોળ અરીસો" where the question says
                    "અંતર્ગોળ અરીસો") cannot support the premise, even when a neighbouring sentence defines the asked one;
* `book_says`     - when the premise is not found: the source sentences that carry all of the question's concepts
                    but one. They are shown as "this is what the book says", never as the answer, and GRANTH-AI
                    does not state that the premise is false - only that the selected book does not contain it.
"""
from __future__ import annotations

from . import gujarati as g, polarity

SPECIFIC = ("unit", "reverse_unit", "instrument", "organ")     # intents whose attribute mark alone identifies a fact


def bindings(question: str, need: list, bigrams: set) -> list:
    """(modifier, head) pairs: two concept words that stand side by side in the question AND in the book."""
    need_set, out = set(need), []
    toks = g.tokenize(g.normalize_text(question))
    for a, b in zip(toks, toks[1:]):
        ta, tb = g.content_terms(a), g.content_terms(b)
        if len(ta) == 1 and len(tb) == 1 and ta[0] in need_set and tb[0] in need_set and ta[0] != tb[0] and (ta[0], tb[0]) in bigrams:
            out.append((ta[0], tb[0]))
    return out


def sibling_break(binds: list, sentence: str, bigrams: set, q_stems: set) -> str | None:
    """Returns the sibling word if `sentence` speaks of '<other> head' and not of '<modifier> head'."""
    if not binds:
        return None
    seq = g.content_terms(sentence)
    for mod, head in binds:
        pos = [i for i, t in enumerate(seq) if t == head]
        if not pos:
            continue
        if any(mod in seq[max(0, i - 3):i] for i in pos):
            continue                                    # the asked modifier stands with the head here
        for i in pos:
            if i and seq[i - 1] != mod and seq[i - 1] not in q_stems and (seq[i - 1], head) in bigrams:
                return seq[i - 1]
    return None


def assumptions(an: dict, pl: dict, surface) -> dict:
    """What the question takes for granted. `surface(stem)` gives a printable word."""
    terms = [surface(t) for t in pl["need"]]
    verbs = [x["word"] for x in pl["soft"]]
    neg = [surface(t) for t in an.get("negated", [])]
    text = "પ્રશ્ન માની લે છે કે આ બાબતો પુસ્તકની એક જ હકીકતમાં સાથે આવે છે: " + ", ".join(terms + verbs)
    if neg:
        text += " (નકાર સાથે: " + ", ".join(neg) + ")"
    return {"concepts": terms, "actions": verbs, "negated": neg, "statement_gu": text + "."}


def book_says(an: dict, pl: dict, rows: list, attribute, limit: int = 2) -> list:
    """Sentences that carry every concept of the question but one. [] if the question has too little to compare."""
    need = pl["need"]
    n = len(need)
    if n < 2:
        return []
    roots = [x["root"] for x in pl["soft"]]
    out, seen = [], set()
    for rank, row in enumerate(rows):
        if row["kind"] != "paragraph":
            continue
        for pos, s in enumerate(g.split_sentences(row["text"])):
            st = set(g.content_terms(s))
            got = [t for t in need if t in st]
            if len(got) != n - 1:
                continue
            verb = any(any(x.startswith(r) and len(x) <= len(r) + 4 for x in st) for r in roots)
            mark = bool(attribute(s))
            if n == 2 and not ((an["intent"] in SPECIFIC and mark) or verb):
                continue                                # one shared word proves nothing
            if s in seen:
                continue
            seen.add(s)
            missing = [t for t in need if t not in st]
            out.append(((not verb, not mark, rank, pos), {"text": s, "chunk_id": row["id"], "page_number": row["page_number"],
                                                         "edition_id": row["edition_id"], "missing": missing}))
    out.sort(key=lambda x: x[0])
    return [o[1] for o in out[:limit]]
