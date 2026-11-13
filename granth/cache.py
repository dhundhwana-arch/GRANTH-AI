"""Shared verified-answer cache.

Rules enforced here (and tested):
* only verified, answered responses are stored - never abstentions, failures or unverified text;
* the key covers question + board/medium/standard/subject + edition ids + chapter scope + answer mode
  + corpus version of every edition in scope + answer-engine version;
* on every hit the cited chunks are re-checked against the database (same id, same text hash);
* re-ingesting an edition bumps its corpus version and deletes its cache rows.
"""
from __future__ import annotations

import hashlib
import json

from . import ENGINE_VERSION, db


def make_key(normalized_question: str, scope: dict, corpus_versions: dict, engine_version: str = ENGINE_VERSION) -> str:
    material = json.dumps({
        "q": normalized_question,
        "board": scope.get("board"), "medium": scope.get("medium"), "standard": scope.get("standard"),
        "subject": scope.get("subject"),
        "editions": sorted(int(e) for e in scope.get("edition_ids", [])),
        "chapter": scope.get("chapter_id"),
        "mode": scope.get("mode"), "marks": scope.get("marks"),
        "corpus": {str(k): corpus_versions[k] for k in sorted(corpus_versions)},
        "engine": engine_version,
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def get(con, key: str) -> dict | None:
    row = con.execute("SELECT * FROM answer_cache WHERE cache_key=?", (key,)).fetchone()
    if row is None:
        return None
    hashes = json.loads(row["evidence_hashes_json"])
    for cid, h in hashes.items():
        cur = con.execute("SELECT text_sha256 FROM text_chunks WHERE id=?", (int(cid),)).fetchone()
        if cur is None or cur["text_sha256"] != h:
            con.execute("DELETE FROM answer_cache WHERE cache_key=?", (key,))
            con.commit()
            return None
    con.execute("UPDATE answer_cache SET hits=hits+1, last_hit_at=? WHERE cache_key=?", (db.now(), key))
    con.commit()
    payload = json.loads(row["payload_json"])
    payload["cache"] = {"hit": True, "created_at": row["created_at"], "hits": row["hits"] + 1,
                        "engine_version": row["engine_version"], "corpus_versions": json.loads(row["corpus_versions"])}
    return payload


def put(con, key: str, normalized_question: str, scope: dict, corpus_versions: dict, payload: dict) -> bool:
    """Store only verified answers. Returns False (and stores nothing) otherwise."""
    if payload.get("status") != "answered" or not payload.get("verification", {}).get("verified"):
        return False
    hashes = {str(e["chunk_id"]): e["text_sha256"] for e in payload.get("evidence", [])}
    if not hashes:
        return False
    stored = {k: v for k, v in payload.items() if k not in ("cache", "question_id", "answer_id", "latency_ms")}
    con.execute(
        "INSERT OR REPLACE INTO answer_cache(cache_key, normalized_question, scope_json, edition_ids, corpus_versions,"
        " engine_version, payload_json, evidence_hashes_json, verified, created_at) VALUES (?,?,?,?,?,?,?,?,1,?)",
        (key, normalized_question, json.dumps(scope, ensure_ascii=False, sort_keys=True),
         "," + ",".join(str(e) for e in sorted(scope.get("edition_ids", []))) + ",",
         json.dumps({str(k): v for k, v in corpus_versions.items()}), payload.get("engine_version", ENGINE_VERSION),
         json.dumps(stored, ensure_ascii=False), json.dumps(hashes), db.now()))
    con.commit()
    return True


def invalidate_edition(con, edition_id: int) -> int:
    cur = con.execute("DELETE FROM answer_cache WHERE edition_ids LIKE ?", (f"%,{int(edition_id)},%",))
    return cur.rowcount


def stats(con) -> dict:
    r = con.execute("SELECT COUNT(*) n, COALESCE(SUM(hits),0) h FROM answer_cache").fetchone()
    hits = con.execute("SELECT COUNT(*) FROM usage_events WHERE kind='cache_hit'").fetchone()[0]
    misses = con.execute("SELECT COUNT(*) FROM usage_events WHERE kind='cache_miss'").fetchone()[0]
    return {"entries": r["n"], "hits": hits, "misses": misses,
            "hit_rate": round(hits / (hits + misses), 4) if hits + misses else None}
