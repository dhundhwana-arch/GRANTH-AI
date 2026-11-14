"""Hybrid textbook retrieval: BM25 keyword search + character n-gram similarity, scoped by edition/chapter.

Only chunks of editions that are APPROVED *and* admin-approved are ever indexed.
The "semantic" leg is a character-trigram TF-IDF cosine (robust to Gujarati inflection and spelling
variation). It is NOT a neural embedding; see docs/RAG_ENGINE_REPORT.md for why and for the upgrade hook.
"""
from __future__ import annotations

import math
import threading
from collections import Counter

from . import gujarati as g

K1, B = 1.4, 0.75
W_COVERAGE, W_BM25, W_NGRAM = 0.55, 0.25, 0.20
RETRIEVAL_KINDS = ("paragraph", "example", "table", "formula", "figure")

_lock = threading.Lock()
_indexes: dict = {}


class Index:
    def __init__(self, rows):
        self.rows = [dict(r) for r in rows]
        self.tf = [Counter(g.content_terms(r["text"] + " " + (r["section_title"] or ""))) for r in self.rows]
        self.surface: dict = {}                      # stem -> the word as the book prints it (for "matched book word" messages)
        for r in self.rows:
            for w in r["text"].split():
                w = w.strip("‘’'\".,;:?!()[]|—-")
                st = g.content_terms(w)
                if len(st) == 1:
                    self.surface.setdefault(st[0], w)
        self.bigrams = set()                         # neighbouring content words, as printed ("અંતર્ગોળ અરીસો")
        for r in self.rows:
            for sent in g.split_sentences(r["text"]) if r["kind"] != "table" else r["text"].replace("|", "\n").split("\n"):
                seq = g.content_terms(sent)
                self.bigrams.update(zip(seq, seq[1:]))
        self.len = [sum(t.values()) or 1 for t in self.tf]
        self.avg = sum(self.len) / max(len(self.len), 1)
        self.df = Counter()
        for t in self.tf:
            self.df.update(t.keys())
        self.n = len(self.rows)
        self.vocab = set(self.df)
        self.by_first: dict = {}
        for term in self.vocab:
            self.by_first.setdefault(term[0], []).append(term)
        self._scopes: dict = {}
        grams = [Counter(g.char_ngrams(r["text"])) for r in self.rows]
        self.gdf = Counter()
        for c in grams:
            self.gdf.update(c.keys())
        self.gvec = []
        for c in grams:
            v = {k: (1 + math.log(tf)) * self.gidf(k) for k, tf in c.items()}
            norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
            self.gvec.append({k: x / norm for k, x in v.items()})

    def idf(self, term):
        return math.log(1 + (self.n - self.df.get(term, 0) + 0.5) / (self.df.get(term, 0) + 0.5))

    def gidf(self, gram):
        return math.log(1 + self.n / (1 + self.gdf.get(gram, 0)))

    # ---- vocabulary restricted to the editions in scope (a word from another book - or another student's
    #      private notes - must never be offered as a spelling suggestion)
    def scope(self, eds=None) -> dict:
        key = frozenset(int(e) for e in eds) if eds is not None else None
        hit = self._scopes.get(key)
        if hit:
            return hit
        rows = [i for i, r in enumerate(self.rows) if key is None or r["edition_id"] in key]
        df = Counter()
        for i in rows:
            df.update(self.tf[i].keys())
        sc = {"rows": rows, "df": df, "vocab": set(df), "by_first": {}, "skeleton": {}}
        for term in sorted(df, key=lambda x: (df[x], x)):
            sc["by_first"].setdefault(term[0], []).append(term)
            sc["skeleton"][_skel(term)] = term
        if len(self._scopes) > 64:
            self._scopes.clear()
        self._scopes[key] = sc
        return sc

    def resolve_terms(self, question: str, eds=None) -> list[dict]:
        """Map question terms onto the vocabulary of the editions in scope.

        match kinds, strongest first: exact, compound (split compound re-joined), fuzzy (clear spelling variant),
        then the WEAK kinds synonym, fuzzy_context (short word, accepted only next to another matched word) and prefix
        (first part of a single compound). Weak kinds are reported so that the answer is never marked Verified.
        """
        from . import concepts
        sc = self.scope(eds)
        vocab = sc["vocab"]
        raw = g.content_terms(question)
        out, i = [], 0
        while i < len(raw):
            t = raw[i]
            if i + 1 < len(raw):
                # students often split compounds: "વિદ્યુત પ્રવાહ" -> textbook "વિદ્યુતપ્રવાહ"
                joined = t + raw[i + 1]
                cand = joined if joined in vocab else (
                    self._fuzzy(joined, sc, strict=True) if (t not in vocab or raw[i + 1] not in vocab) else None)
                if cand:
                    out.append({"query": t + " " + raw[i + 1], "term": cand, "match": "compound"})
                    i += 2
                    continue
            if t in vocab:
                out.append({"query": t, "term": t, "match": "exact"})
            else:
                f = self._fuzzy(t, sc)
                alt = next((a for a in concepts.synonyms(t) if g.content_terms(a) and all(x in vocab for x in g.content_terms(a))), None)
                if f and _skel(f) == _skel(t):
                    out.append({"query": t, "term": f, "match": "spelling"})
                elif alt:
                    # a listed everyday word ("વધારે" -> "વધુ") is a better guess than a merely similar-looking word
                    for x in g.content_terms(alt):
                        out.append({"query": t, "term": x, "match": "synonym", "via": alt})
                elif f:
                    out.append({"query": t, "term": f, "match": "fuzzy", "confidence": spelling_confidence(t, f, vocab)})
                else:
                    out.append({"query": t, "term": None, "match": "none", "near": self._near(t, sc)})
            i += 1
        # second pass: weak matches that need the context of the words already matched
        matched = {o["term"] for o in out if o["term"]}
        for o in out:
            if o["term"] is None:
                c = self._fuzzy_context(o["query"], sc, matched)
                if c:
                    o.update(term=c, match="fuzzy_context")
                else:
                    pre = [v for v in sc["by_first"].get(o["query"][0], []) if v.startswith(o["query"]) and len(v) >= len(o["query"]) + 2]
                    if len(o["query"]) >= 2 and len(pre) == 1:
                        o.update(term=pre[0], match="prefix")
                    else:
                        r = self._same_root(o["query"], sc)
                        if r:
                            o.update(term=r, match="root")
        # Phase 5: a spelling guess needs CONTEXT - the guessed word must stand in one passage with another word of
        # the question. Otherwise it stays unknown and is only offered as "did you mean".
        firm = {o["term"] for o in out if o["term"] and o["match"] in ("exact", "compound", "spelling", "synonym")}
        for o in out:
            if o["match"] == "fuzzy" and firm and not any(
                    self.tf[i].get(o["term"]) and any(self.tf[i].get(m) for m in firm if m != o["term"]) for i in sc["rows"]):
                o.update(near=o["term"], term=None, match="none")
        seen, uniq = set(), []
        for o in out:
            key = o["term"] or "?" + o["query"]
            if key not in seen:
                seen.add(key)
                uniq.append(o)
        return uniq

    def _candidates(self, t: str, sc: dict, limit: int):
        st = _skel(t)
        for cand in sc["by_first"].get(t[0], []):
            if abs(len(cand) - len(t)) > limit + 1:
                continue
            d = min(g.levenshtein(t, cand), g.levenshtein(st, _skel(cand)))
            if d <= limit:
                yield d, cand

    def _fuzzy(self, t: str, sc: dict, strict: bool = False):
        """A clear spelling variant: same skeleton, or one edit away for a word of four or more letters
        (two edits for long words). Two equally close candidates = not clear = no match."""
        if t.isdigit():
            return None
        sk = sc["skeleton"].get(_skel(t))            # "ઓહમ" / "ઓહ્મ", "તટસ્થિકરણ" / "તટસ્થીકરણ"
        if sk:
            return sk
        if len(_skel(t)) < 4:
            return None
        limit = 1 if (strict or len(t) < 8) else 2
        def common(c):
            n = 0
            for x, y in zip(t, c):
                if x != y:
                    break
                n += 1
            return n
        found = sorted(self._candidates(t, sc, limit), key=lambda x: (x[0], -common(x[1]), x[1]))
        # Phase 5: a near word is a SPELLING variant only if every differing letter is a known spelling confusion
        # (ધ/ઘ, શ/સ, a vowel sign ...). "વૉટમીટર" / "વોલ્ટમીટર" differ by a whole consonant: a different word.
        found = [f for f in found if spelling_confidence(t, f[1], sc["vocab"]) >= FUZZY_MIN_CONFIDENCE]
        if not found:
            return None
        if len(found) > 1 and found[1][0] == found[0][0] and (strict or common(found[1][1]) == common(found[0][1])):
            return None                              # two equally close words: not a clear spelling variant
        return found[0][1]

    def _near(self, t: str, sc: dict):
        """The closest book word to an unknown word - shown as a question ("did you mean ...?"), never used to answer."""
        if t.isdigit() or len(t) < 4:
            return None
        found = sorted(self._candidates(t, sc, 2), key=lambda x: (x[0], x[1]))
        return found[0][1] if found and found[0][0] <= max(1, len(t) // 4) else None

    def _same_root(self, t: str, sc: dict):
        """Another grammatical form of the same word ("ઉમેરાય" / "ઉમેરવામાં"): the two share a root of at least four
        letters that covers most of the shorter word, and exactly one vocabulary word qualifies. A weak match."""
        if t.isdigit() or len(t) < 4:
            return None
        found = []
        for cand in sc["by_first"].get(t[0], []):
            n = _root_len(t, cand)
            if n >= 4 and n >= 0.7 * min(len(t), len(cand)) and abs(len(t) - len(cand)) <= 4 \
                    and set(t[n:] + cand[n:]) <= _GRAMMAR_TAIL:      # the endings differ only by grammar, not by a new consonant
                found.append(cand)
        return found[0] if len(found) == 1 else None

    def _fuzzy_context(self, t: str, sc: dict, matched: set):
        """A short word one edit away from exactly one vocabulary word that occurs together with another matched
        question word in the same passage. Without that support a 2-3 letter near-miss is too weak to accept."""
        if t.isdigit() or len(t) < 2 or not matched:
            return None
        found = [c for d, c in self._candidates(t, sc, 1) if spelling_confidence(t, c, sc["vocab"]) >= FUZZY_MIN_CONFIDENCE]
        ok = [c for c in found if any(self.tf[i].get(c) and any(self.tf[i].get(m) for m in matched if m != c) for i in sc["rows"])]
        return ok[0] if len(ok) == 1 else None


FUZZY_MIN_CONFIDENCE = 0.75
_GRAMMAR_TAIL = set("ાિીુૂેૈોૌંયવમનતણલળ્")
_CONFUSABLE = [set(x) for x in ("કખ", "ગઘ", "ચછ", "જઝ", "ટઠતથ", "ડઢદધઘ", "નણ", "પફ", "બભ", "શષસ", "લળ", "રઋૃ",
                                "ાેૈોૌૅૉિુ", "એઍઐ", "ઓઑઔ", "ઇઈ", "ઉઊ", "અઆ")]
_DROPPABLE = set("યરાેૈોૌૅૉિુૃ")          # conjunct members and vowel signs are the letters students drop or add


def _spelling_cost(a: str, b: str) -> int:
    """Weighted edit distance: 1 for a usual spelling confusion, 100 for any other change of a letter."""
    def sub(x, y):
        return 0 if x == y else (1 if any(x in c and y in c for c in _CONFUSABLE) else 100)

    def gap(x):
        return 1 if x in _DROPPABLE else 100
    prev = [0]
    for ch in b:
        prev.append(prev[-1] + gap(ch))
    for x in a:
        cur = [prev[0] + gap(x)]
        for k, y in enumerate(b, 1):
            cur.append(min(prev[k] + gap(x), cur[k - 1] + gap(y), prev[k - 1] + sub(x, y)))
        prev = cur
    return prev[-1]


def spelling_confidence(asked: str, book: str, vocab=()) -> float:
    """0..1: how sure we are that `asked` is a misspelling of the book word `book` and not another word.
    1.0 same skeleton; 0 if any differing letter is not a usual spelling confusion, or if the part that differs is
    itself a word of the book ("વૉટ" in "વૉટમીટર")."""
    sa, sb = _skel(asked), _skel(book)
    if sa == sb:
        return 1.0
    cost = _spelling_cost(sa, sb)
    if cost >= 100:
        return 0.0
    # compound check: strip what the two words share at the end / start; a remainder that is a book word of its own
    # means the student wrote a different compound on purpose
    k = 0
    while k < min(len(asked), len(book)) and asked[-1 - k] == book[-1 - k]:
        k += 1
    p = 0
    while p < min(len(asked), len(book)) and asked[p] == book[p]:
        p += 1
    for rem_a, rem_b in ((asked[:len(asked) - k], book[:len(book) - k]), (asked[p:], book[p:])):
        if len(rem_a) >= 2 and rem_a != rem_b and (rem_a in vocab or _skel(rem_a) in {_skel(v) for v in vocab if v[:1] == rem_a[:1]}):
            return 0.0
    return round(1 - cost / max(len(sa), len(sb)), 2)


def _root_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _skel(term: str) -> str:
    """Spelling skeleton: virama, vowel length and anusvara are the commonest Gujarati spelling slips."""
    return term.replace("્", "").replace("ી", "િ").replace("ૂ", "ુ").replace("ં", "")


def _signature(con) -> str:
    rows = con.execute("SELECT id, corpus_version, review_status, permission_status, role FROM textbook_editions ORDER BY id").fetchall()
    return "|".join(f"{r[0]}:{r[1]}:{r[2]}:{r[3]}:{r[4]}" for r in rows)


def _db_key(con) -> str:
    row = con.execute("PRAGMA database_list").fetchone()
    return row[2] or f"mem-{id(con)}"


def get_index(con) -> Index:
    key, sig = _db_key(con), _signature(con)
    with _lock:
        hit = _indexes.get(key)
        if hit and hit[0] == sig:
            return hit[1]
    rows = con.execute(
        "SELECT c.* FROM text_chunks c JOIN textbook_editions e ON e.id=c.edition_id "
        "WHERE ((e.permission_status='APPROVED' AND e.review_status='approved') OR e.role='personal') "
        "AND c.kind IN (%s) ORDER BY c.id"
        % ",".join("?" * len(RETRIEVAL_KINDS)), RETRIEVAL_KINDS).fetchall()
    idx = Index(rows)
    with _lock:
        _indexes[key] = (sig, idx)
    return idx


def invalidate_index() -> None:
    with _lock:
        _indexes.clear()


def search(con, question: str, edition_ids: list[int], chapter_id: int | None = None, k: int = 6) -> dict:
    """Return ranked, de-duplicated evidence plus the resolved query terms."""
    idx = get_index(con)
    eds = set(int(e) for e in edition_ids)
    terms = idx.resolve_terms(question, eds)
    max_idf = math.log(1 + (idx.n + 0.5) / 0.5) if idx.n else 1.0
    weights = {(t["term"] or "?" + t["query"]): (idx.idf(t["term"]) if t["term"] else max_idf) for t in terms}
    total_w = sum(weights.values()) or 1.0
    matched = [t["term"] for t in terms if t["term"]]
    qgrams = Counter(g.char_ngrams(question))
    qv = {k_: (1 + math.log(tf)) * idx.gidf(k_) for k_, tf in qgrams.items()}
    qn = math.sqrt(sum(x * x for x in qv.values())) or 1.0
    scored = []
    for i, row in enumerate(idx.rows):
        if row["edition_id"] not in eds or (chapter_id and row["chapter_id"] != int(chapter_id)):
            continue
        tf = idx.tf[i]
        bm, cov = 0.0, 0.0
        for t in matched:
            f = tf.get(t, 0)
            if f:
                bm += idx.idf(t) * f * (K1 + 1) / (f + K1 * (1 - B + B * idx.len[i] / idx.avg))
                cov += weights[t]
        if not bm:
            continue
        cov /= total_w
        gv = idx.gvec[i]
        cos = sum(w * gv.get(k_, 0.0) for k_, w in qv.items()) / qn
        score = W_COVERAGE * cov + W_BM25 * bm / (bm + 3.0) + W_NGRAM * cos
        scored.append((score, bm, cos, cov, i))
    scored.sort(key=lambda s: (-s[0], idx.rows[s[4]]["id"]))
    results, seen = [], set()
    for score, bm, cos, cov, i in scored:
        row = idx.rows[i]
        sig = (row["edition_id"], row["text_sha256"])
        if sig in seen:
            continue
        seen.add(sig)
        results.append({**row, "scores": {"score": round(score, 4), "keyword_bm25": round(bm, 4),
                                          "ngram_cosine": round(cos, 4), "coverage": round(cov, 4)},
                        "matched_terms": [t for t in matched if idx.tf[i].get(t)]})
        if len(results) >= k:
            break
    return {"terms": terms, "weights": weights, "results": results}
