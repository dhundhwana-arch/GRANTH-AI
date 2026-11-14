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
        self.skeleton = {term.replace("્", ""): term for term in sorted(self.vocab, key=lambda x: self.df[x])}
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

    def resolve_terms(self, question: str) -> list[dict]:
        """Map question terms onto index vocabulary: exact, joined-compound, or small-edit fuzzy match."""
        raw = g.content_terms(question)
        out, i = [], 0
        while i < len(raw):
            t = raw[i]
            if i + 1 < len(raw):
                # students often split compounds: "વિદ્યુત પ્રવાહ" -> textbook "વિદ્યુતપ્રવાહ"
                joined = t + raw[i + 1]
                cand = joined if joined in self.vocab else (
                    self._fuzzy(joined, strict=True) if (t not in self.vocab or raw[i + 1] not in self.vocab) else None)
                if cand:
                    out.append({"query": t + " " + raw[i + 1], "term": cand, "match": "compound"})
                    i += 2
                    continue
            if t in self.vocab:
                out.append({"query": t, "term": t, "match": "exact"})
            else:
                f = self._fuzzy(t)
                out.append({"query": t, "term": f, "match": "fuzzy" if f else "none"})
            i += 1
        seen, uniq = set(), []
        for o in out:
            key = o["term"] or "?" + o["query"]
            if key not in seen:
                seen.add(key)
                uniq.append(o)
        return uniq

    def _fuzzy(self, t: str, strict: bool = False):
        if t.isdigit():
            return None
        sk = self.skeleton.get(t.replace("્", ""))   # "ઓહમ" vs "ઓહ્મ": differs only by a virama
        if sk:
            return sk
        if len(t) < 4:
            return None
        limit = 1 if (strict or len(t) < 8) else 2
        best, best_d = None, limit + 1
        for cand in self.by_first.get(t[0], []):
            if abs(len(cand) - len(t)) > limit:
                continue
            d = g.levenshtein(t, cand)
            if d < best_d or (d == best_d and best and self.df[cand] > self.df[best]):
                best, best_d = cand, d
        return best if best_d <= limit else None


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
    terms = idx.resolve_terms(question)
    eds = set(int(e) for e in edition_ids)
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
