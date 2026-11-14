"""Answer-evidence validator.

A source sentence may be shown as the answer only if it passes BOTH checks:
  1. concept  - it carries every topic word of the question (the student's own word, or a word reported as assumed);
  2. attribute - it has the mark of the kind of answer that was asked for (a unit sentence for a unit question,
                 a place for "where", a cause for "why", exactly one of the two options for "X or Y?" ...).
A sentence that only shares words with the question fails. Sentences that fail are never added as padding.

Result levels:  direct  -> may be labelled "Verified against source"
                partial -> shown as "Partially supported", with the reason in words
                none    -> the engine refuses
"""
from __future__ import annotations

import re

from . import concepts, gujarati as g, intent as intent_mod, retrieval, study

_ANAPHORA = ("આ ", "તે ", "તેથી", "આમ ", "આથી", "તેમાં", "તેના", "તેની", "તેનો", "તેનું")
_CAUSE = ("કારણ", "તેથી", "માટે", "લીધે", "જેથી", "વાથી", "આથી")
_AMOUNT = re.compile(r"કરતાં|જેટલ|ઓછ|વધુ|વધારે|સમાન|સરવાળ|ગુણાકાર")
_NUMBER = re.compile(r"[0-9૦-૯]|(?<!\S)(બે|ત્રણ|ચાર|પાંચ|છ|સાત|આઠ|નવ|દસ|બમણ\S*|અડધ\S*)(?!\S)")
_LOC = tuple(g.fold(x) for x in ("માં", "પર", "ઉપર", "અંદર"))
_ABL = tuple(g.fold(x) for x in ("માંથી", "થી"))
_NOT_PLACE = frozenset(g.fold(x) for x in ("હાજરીમાં", "ગેરહાજરીમાં", "રૂપમાં", "સ્વરૂપમાં", "સમપ્રમાણમાં", "પ્રમાણમાં"))
MAX_WINDOW = 3


def _attribute(an: dict, text: str, q_stems: set) -> str | None:
    """'explicit' if `text` carries the mark of the requested attribute, 'implied' for a weaker mark, None if not."""
    it = an["intent"]
    st = set(g.content_terms(text))
    toks = g.tokenize(text)
    if it in ("unit", "reverse_unit"):
        return "explicit" if "એકમ" in st else None
    if it == "organ":
        return "explicit" if "અંગ" in st else None
    if it == "instrument":
        return "explicit" if ("સાધન" in st or any(t.startswith(("માપ", "મપા")) for t in st)) else None
    if it in ("place", "source"):
        ends = _ABL if it == "source" else _LOC
        for t in toks:
            if t in _NOT_PLACE or g.stem(t) in q_stems or t in q_stems:
                continue
            if t.endswith(ends) and len(t) > 3 and not (it == "place" and t.endswith(_ABL[0])):
                return "explicit"
        return "explicit" if it == "source" and "સ્રોત" in st else None
    if it == "reason":
        return "explicit" if any(c in text for c in _CAUSE) else None
    if it == "quantity":
        return "explicit" if (_NUMBER.search(text) or _AMOUNT.search(text)) else None
    if it == "between":
        return "explicit" if "વચ્ચે" in text else None
    if it == "naming":
        return "explicit" if study.find_definitions(text) else None
    if it == "types":
        return "explicit" if (st & concepts.facet_stems("types")) else None
    if it == "use":
        return "explicit" if any(t.startswith(("ઉપયોગ", "વપરા", "વાપર")) for t in st) else None
    if it == "function":
        if "કાર્ય" in st:
            return "explicit"
        # the book tells what the thing DOES without the word "કાર્ય": the thing is the subject of an action sentence
        w0 = g.tokenize(text)[:1]
        first = g.content_terms(w0[0]) if w0 else []
        if first and first[0] in q_stems and first[0] == w0[0] and not study.find_definitions(text) and not text.rstrip(" .।").endswith(("કહે છે", "કહેવાય છે")):
            return "implied"
        return None
    return "explicit"                                   # fact / process / example: no attribute mark exists


def _present(term: str, st: set) -> str | None:
    if term in st:
        return "exact"
    for alt in concepts.synonyms(term):
        a = g.content_terms(alt)
        if a and all(x in st for x in a):
            return "related:" + alt
    if len(term) >= 4:
        for x in st:                                    # part of a compound: "વિદ્યુત" in "વિદ્યુતપુરવઠો"
            if len(x) >= len(term) + 3 and (x.startswith(term) or x.endswith(term)):
                return "related:" + x
    return None


def _soft_present(root: str, st: set) -> bool:
    return any(x.startswith(root) and len(x) <= len(root) + 4 for x in st)


def plan(an: dict, terms: list[dict], vocab: set) -> dict:
    """Split the question's words into HARD topic words that an answering sentence must carry, SOFT words (verbs)
    that it should carry, and UNKNOWN words that the selected source does not know at all."""
    need, weak, soft, unknown = [], [], [], []
    for t in terms:
        q, term = t["query"], t["term"]
        if any(intent_mod.is_cue(an, x) for x in ([term] if term else []) + q.split()):
            continue
        if an["intent"] == "choice" and term in an["options"]:
            continue
        if (q in an["soft"] and t["match"] != "synonym") or (term is None and q in an["soft_unknown"]) \
                or (term in concepts._generic() and term not in concepts.all_facet_stems() and t["match"] == "exact"):
            soft.append({"word": q, "root": intent_mod.verb_root(q)})
            continue
        if term is None:
            unknown.append(q)
            continue
        need.append(term)
        if t["match"] in ("synonym", "fuzzy", "fuzzy_context", "prefix", "root"):
            weak.append(f"{q} → {t.get('via') or term}")
    return {"need": list(dict.fromkeys(need)), "weak": weak, "soft": soft, "unknown": unknown}


def _check(an: dict, pl: dict, text: str, q_stems: set, claims: list) -> dict | None:
    st = set(g.content_terms(text))
    related = []
    for t in pl["need"]:
        how = _present(t, st)
        if not how:
            return None
        if how != "exact":
            related.append(f"{t} → {how[8:]}")
    missing_soft = [x["word"] for x in pl["soft"] if not _soft_present(x["root"], st)]
    if len(pl["need"]) + len(pl["soft"]) - len(missing_soft) < min(2, len(pl["need"]) + len(pl["soft"])):
        return None                                     # one topic word alone, with the verb missing, proves nothing
    if any(w not in text for w in claims):
        return None
    short_fact = False
    if an["intent"] == "choice":
        got = [o for o in an["options"] if o in st]
        if len(got) > 1:
            return None
        if not got:
            # neither option is printed: only a short statement about exactly that subject may be shown ("શુદ્ધ પાણી તટસ્થ છે.")
            seq = g.content_terms(text)
            if len(pl["need"]) < 2 or len(seq) > len(pl["need"]) + 1:
                return None
            short_fact = True
    attr = _attribute(an, text, q_stems)
    if not attr:
        return None
    return {"related": related, "attr": attr, "missing_soft": missing_soft, "neither": short_fact}


_ORDINAL = ("પહેલો", "પહેલી", "પહેલું", "બીજો", "બીજી", "બીજું", "ત્રીજો", "ત્રીજી", "ત્રીજું", "ચોથો", "ચોથી", "ચોથું")


def _chained(sents: list[str], q_stems: set) -> bool:
    """Neighbouring sentences form ONE explanation only if each refers back to the one before it ("આ સમયે ...") or
    carries on with a word that the question did not supply. Two sentences that merely share a question word do not."""
    for a, b in zip(sents, sents[1:]):
        if b.startswith(_ANAPHORA):
            continue
        link = (set(g.content_terms(a)) & set(g.content_terms(b))) - q_stems
        if not link:
            return False
    return True


def _antecedent_ok(pl: dict, prev: str, cur: str) -> bool:
    cur_t = set(g.content_terms(cur))
    lacking = [t for t in pl["need"] if not _present(t, cur_t)]
    defined = study.find_definitions(prev)
    if defined:
        allowed = {x for term in defined for x in g.content_terms(term)}
    else:
        allowed = set(g.content_terms(prev)[:2])          # the subject the sentence opens with
    return all(t in allowed for t in lacking)


def select(con, question: str, res: dict, edition_ids, chapter_id, target: int, claims: list | None = None) -> dict:
    """-> {'parts': [...], 'level': 'direct'|'partial', 'gaps': [...], 'analysis': {...}}  or  {'abstain': reason, ...}"""
    an = intent_mod.analyse(question)
    vocab = retrieval.get_index(con).scope(edition_ids)["vocab"]
    pl = plan(an, res["terms"], vocab)
    report = {"intent": an["intent"], "intent_label": an["label"], "concept_terms": pl["need"], "options": an["options"],
              "assumed": pl["weak"], "verbs": [x["word"] for x in pl["soft"]], "unknown_words": pl["unknown"]}
    if pl["unknown"]:
        return {"abstain": "low_coverage", "analysis": report}
    if not pl["need"]:
        return {"abstain": "no_content_terms" if not res["terms"] else "low_coverage", "analysis": report}
    q_stems = set(pl["need"]) | {t["query"] for t in res["terms"]} | set(an["options"])
    claims = claims or []
    rows = list(res["results"])
    have = {r["id"] for r in rows}
    extra = retrieval.search(con, " ".join(pl["need"]), edition_ids, chapter_id, k=8)["results"]
    rows += [r for r in extra if r["id"] not in have]
    pairs = [(a, b) for a, b in zip(pl["need"], pl["need"][1:])]

    found = []                                          # (sort key, [units], info)
    for rank, row in enumerate(rows):
        if row["kind"] == "example":
            # a worked example is one unit: its sentences only make sense together, and it is about one particular sum
            ok = _check(an, pl, row["text"], q_stems, claims)
            if ok:
                ok["example"] = True
                found.append(((True, True, False, False, 0, 9, rank, 0),
                              [{"text": st_, "row": row, "pos": i, "kind": "sentence"} for i, st_ in enumerate(g.split_sentences(row["text"]))], ok, False))
        elif row["kind"] == "paragraph":
            sents = g.split_sentences(row["text"])
            ex = False
            for pos, s in enumerate(sents):
                span = [pos]
                text = s
                if pos > 0 and s.startswith(_ANAPHORA):
                    span, text = [pos - 1, pos], sents[pos - 1] + " " + s
                ok = _check(an, pl, s, q_stems, claims)
                if ok:
                    span = [pos]
                elif len(span) > 1 and _attribute(an, s, q_stems) and _antecedent_ok(pl, sents[pos - 1], s):
                    # "આ પ્રક્રિયામાં ..." : the sentence before may supply only WHAT "આ / તે" refers to
                    ok = _check(an, pl, text, q_stems, claims)
                if not ok:
                    continue
                seq = g.content_terms(s)
                adj = sum(1 for pr in pairs if pr in set(zip(seq, seq[1:])))
                is_def = bool(study.find_definitions(s)) and an["intent"] != "naming"
                ok["example"] = ex
                key = (ex, bool(ok["related"] or ok["missing_soft"] or ok["neither"]), ok["attr"] != "explicit", is_def and an["single"], -adj, len(span), rank, pos)
                found.append((key, [{"text": sents[i], "row": row, "pos": i, "kind": "sentence"} for i in span], ok, False))
        elif row["kind"] == "formula" and an["intent"] in ("fact", "process"):
            ok = _check(an, pl, row["text"], q_stems, claims)   # "HCl અને NaOH ..." is answered by the printed equation
            if ok:
                found.append(((False, bool(ok["related"] or ok["missing_soft"]), False, False, 0, 1, rank, 0),
                              [{"text": row["text"], "row": row, "pos": 0, "kind": "formula"}], ok, False))
        elif row["kind"] == "table":
            lines = [ln for ln in row["text"].split("\n") if ln.strip()]
            body = [ln for ln in lines if ln.lstrip().startswith("|")]
            if len(body) < 2:
                continue
            head = lines[0] + " " + body[0]
            for ln in body[1:]:
                if not (set(pl["need"]) & set(g.content_terms(ln))):
                    continue
                ok = _check(an, pl, head + " " + ln, q_stems, claims)
                if ok and an["intent"] not in ("fact", "process", "example", "reason", "function"):
                    found.append(((False, True, True, False, 0, 9, rank, 0), [{"text": row["text"], "row": row, "pos": 0, "kind": "table"}], ok, True))
                    break
    window = False
    if not found and an["intent"] == "reason" and len(pl["need"]) >= 2:
        # a cause is often told over neighbouring sentences of ONE paragraph; show that run, never as Verified
        best = None
        for rank, row in enumerate(rows):
            if row["kind"] != "paragraph":
                continue
            sents = g.split_sentences(row["text"])
            for n in range(2, MAX_WINDOW + 1):
                for i in range(0, len(sents) - n + 1):
                    ok = _chained(sents[i:i + n], q_stems) and _check(an, pl, " ".join(sents[i:i + n]), q_stems, claims)
                    if ok and (best is None or (n, rank) < best[0]):
                        best = ((n, rank), [{"text": sents[j], "row": row, "pos": j, "kind": "sentence"} for j in range(i, i + n)], ok)
                if best and best[0][0] == n:
                    break
        if best:
            found.append(((False, True, True, False, 0, best[0][0], best[0][1], 0), best[1], best[2], False))
            window = True
    heading = False
    if not found and an["intent"] in ("fact", "process") and not pl["soft"]:
        # the topic is the title of a section ("શ્વસનતંત્ર વિશે લખો"): the opening sentences of that section are about it
        for rank, row in enumerate(rows):
            if row["kind"] != "paragraph" or not set(pl["need"]) <= set(g.content_terms(row.get("section_title") or "")):
                continue
            for pos, s_ in enumerate(g.split_sentences(row["text"])[:max(target, 1)]):
                found.append(((False, True, False, False, 0, 1, rank, pos), [{"text": s_, "row": row, "pos": pos, "kind": "sentence"}],
                              {"related": [], "attr": "explicit", "missing_soft": [], "neither": False}, False))
            if found:
                heading = True
                break
    if not found:
        aspect = an["intent"] in ("unit", "reverse_unit", "use", "types", "function", "organ", "instrument")
        return {"abstain": "aspect_not_found" if aspect else "evidence_not_specific", "analysis": report}

    found.sort(key=lambda f: f[0])
    if any(not f[3] for f in found):
        found = [f for f in found if not f[3]]          # a sentence that answers makes the whole table unnecessary
    if an["single"] or target <= 1:
        found = found[:1]
    else:
        strict = [f for f in found if not f[0][0] and not f[0][1] and not f[0][2]]
        found = (strict or found)[:target]
    units, seen = [], set()
    for f in sorted(found, key=lambda f: (f[0][6], f[1][0]["pos"])):
        for u in f[1]:
            k = (u["row"]["id"], u["pos"], u["kind"])
            if k not in seen:
                seen.add(k)
                units.append({**u, "lead": f is found[0] or None})
    out = []
    for u in units:                                     # "... બે નિયમો છે." is completed by "પહેલો નિયમ: ...", "બીજો નિયમ: ..."
        out.append(u)
        if u["kind"] == "sentence" and _NUMBER.search(u["text"]):
            sents = g.split_sentences(u["row"]["text"])
            j = u["pos"] + 1
            while j < len(sents) and sents[j].startswith(_ORDINAL):
                if not any(x["row"]["id"] == u["row"]["id"] and x["pos"] == j for x in units):
                    out.append({"text": sents[j], "row": u["row"], "pos": j, "kind": "sentence", "lead": None})
                j += 1
    units = out
    if not an["single"] and target > 1:
        # "આ સમયે સ્નાયુકોષોમાં ..." : a sentence that refers back to an accepted one AND stays on the question's topic
        # belongs to the same statement
        out = []
        for u in units:
            out.append(u)
            if u["kind"] != "sentence" or u["row"]["kind"] != "paragraph":
                continue
            sents = g.split_sentences(u["row"]["text"])
            j = u["pos"] + 1
            while j < len(sents) and len(out) < target and sents[j].startswith(_ANAPHORA) \
                    and set(pl["need"]) & set(g.content_terms(sents[j])) \
                    and not any(x["row"]["id"] == u["row"]["id"] and x["pos"] == j for x in units + out):
                out.append({"text": sents[j], "row": u["row"], "pos": j, "kind": "sentence", "lead": None})
                j += 1
        units = out
    lead = found[0]
    gaps = []
    related = list(dict.fromkeys(x for f in found for x in f[2]["related"]))
    if related:
        gaps.append("પ્રશ્નનો આ શબ્દ બતાવેલા વાક્યમાં નથી; તેને મળતો શબ્દ છે: " + ", ".join(related) + ". બંને એક જ બાબત છે કે નહીં તે જાતે ચકાસો.")
    ms = list(dict.fromkeys(x for f in found for x in f[2]["missing_soft"]))
    if ms:
        gaps.append("પ્રશ્નનું ક્રિયાપદ ‘" + ", ".join(ms) + "’ બતાવેલા વાક્યમાં નથી; બાકીના શબ્દો અને પૂછેલી બાબત (" + an["label"] + ") પરથી વાક્ય શોધ્યું છે.")
    if any(f[2]["neither"] for f in found):
        gaps.append("પ્રશ્નમાં આપેલા બેમાંથી એક પણ વિકલ્પ પુસ્તકના વાક્યમાં નથી; તે જ બાબત વિશે પુસ્તક જે કહે છે તે બતાવ્યું છે.")
    if any(f[2]["attr"] == "implied" for f in found):
        gaps.append("પુસ્તક ‘" + an["label"] + "’ શબ્દ વાપરતું નથી; તે વસ્તુ શું કરે છે તે જણાવતું વાક્ય બતાવ્યું છે.")
    if window:
        gaps.append("ઉત્તર કોઈ એક વાક્યમાં નથી; એક જ ફકરાનાં સળંગ વાક્યો બતાવ્યાં છે. કારણ તેમાંથી જાતે તારવવું પડશે.")
    if any(f[2].get("example") for f in found):
        gaps.append("આ લખાણ પાઠ્યપુસ્તકના એક ઉકેલેલા ઉદાહરણમાંથી છે; તે ફક્ત તે દાખલા પૂરતું છે, સામાન્ય નિયમ નથી.")
    if heading:
        gaps.append("પ્રશ્નનો શબ્દ વિભાગના મથાળામાં છે, વાક્યોમાં નથી; તે વિભાગની શરૂઆતનું લખાણ બતાવ્યું છે.")
    if any(f[3] for f in found):
        gaps.append("ઉત્તર કોષ્ટકની એક હરોળમાં છે; આખું કોષ્ટક બતાવ્યું છે.")
    if an["intent"] == "reason" and len(pl["need"]) < 2:
        gaps.append("પ્રશ્નમાં એક જ મુખ્ય શબ્દ છે; પુસ્તકનું હેતુ / કારણ દર્શાવતું વાક્ય બતાવ્યું છે.")
    level = "partial" if (gaps or pl["weak"]) else "direct"
    report.update(level=level, attribute=lead[2]["attr"], sentences=len(units))
    return {"units": units, "level": level, "gaps": gaps, "analysis": report, "n_found": len(found)}
