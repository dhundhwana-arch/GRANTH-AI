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
                    out.append({"query": t, "term": f, "match": "fuzzy"})
                else:
                    out.append({"query": t, "term": None, "match": "none"})
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
        if not found:
            return None
        if len(found) > 1 and found[1][0] == found[0][0] and (strict or common(found[1][1]) == common(found[0][1])):
            return None                              # two equally close words: not a clear spelling variant
        return found[0][1]

    def _same_root(self, t: str, sc: dict):
        """Another grammatical form of the same word ("ઉમેરાય" / "ઉમેરવામાં"): the two share a root of at least four
        letters that covers most of the shorter word, and exactly one vocabulary word qualifies. A weak match."""
        if t.isdigit() or len(t) < 4:
            return None
        found = []
        for cand in sc["by_first"].get(t[0], []):
            n = _root_len(t, cand)
            if n >= 4 and n >= 0.7 * min(len(t), len(cand)) and abs(len(t) - len(cand)) <= 4:
                found.append(cand)
        return found[0] if len(found) == 1 else None

    def _fuzzy_context(self, t: str, sc: dict, matched: set):
        """A short word one edit away from exactly one vocabulary word that occurs together with another matched
        question word in the same passage. Without that support a 2-3 letter near-miss is too weak to accept."""
        if t.isdigit() or len(t) < 2 or not matched:
            return None
        found = [c for d, c in self._candidates(t, sc, 1)]
        ok = [c for c in found if any(self.tf[i].get(c) and any(self.tf[i].get(m) for m in matched if m != c) for i in sc["rows"])]
        return ok[0] if len(ok) == 1 else None


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
