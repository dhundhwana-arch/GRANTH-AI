"""Cost and resource accounting from the usage_events ledger."""
from __future__ import annotations

import os

from . import cache, config

# Indicative free-tier figures for planning ONLY. Secondary sources, checked 2026-11-13; providers change
# limits without notice. Authoritative values: the provider's own console (see docs/FREE_TIER_RESEARCH.md).
FREE_TIER_NOTES = {
    "gemini": {"docs": "https://ai.google.dev/gemini-api/docs/rate-limits", "verified_from_official_page": False,
               "note": "Free tier exists for Flash / Flash-Lite models; per-project limits shown in AI Studio. "
                       "Free-tier prompts may be used to improve Google products - do not send student data."},
    "huggingface": {"docs": "https://huggingface.co/docs/inference-providers/pricing", "verified_from_official_page": False,
                    "note": "Small monthly credit for free accounts (about $0.10, subject to change)."},
}


def summary(con) -> dict:
    rows = con.execute("SELECT kind, COALESCE(provider,'') provider, COUNT(*) n, SUM(tokens_in) ti, SUM(tokens_out) tout"
                       " FROM usage_events GROUP BY kind, provider").fetchall()
    events = [{"kind": r["kind"], "provider": r["provider"] or None, "count": r["n"],
               "est_tokens_in": r["ti"] or 0, "est_tokens_out": r["tout"] or 0} for r in rows]
    by_kind: dict = {}
    for e in events:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + e["count"]
    c = cache.stats(con)
    path = con.execute("PRAGMA database_list").fetchone()[2]
    size = os.path.getsize(path) if path and os.path.exists(path) else 0
    answered = con.execute("SELECT COUNT(*) FROM generated_answers").fetchone()[0]
    lat = con.execute("SELECT AVG(latency_ms) a, MAX(latency_ms) m FROM generated_answers").fetchone()
    return {
        "external_api_calls": by_kind.get("external_api_call", 0) + by_kind.get("external_api_error", 0),
        "local_model_calls": by_kind.get("local_model_call", 0),
        "local_retrievals": by_kind.get("local_retrieval", 0),
        "ocr_local_operations": by_kind.get("ocr_local", 0),
        "ingestion_jobs": by_kind.get("ingestion", 0),
        "cache": c,
        "api_calls_saved_by_cache": c["hits"] if config.get("GRANTH_GENERATIVE", "off").lower() == "on" else 0,
        "pipeline_runs_saved_by_cache": c["hits"],
        "answers_served": answered,
        "latency_ms": {"avg": round(lat["a"], 2) if lat["a"] is not None else None,
                       "max": round(lat["m"], 2) if lat["m"] is not None else None},
        "storage": {"database_bytes": size,
                    "chunks": con.execute("SELECT COUNT(*) FROM text_chunks").fetchone()[0]},
        "limits": {"GRANTH_GENERATIVE": config.get("GRANTH_GENERATIVE", "off"),
                   "GRANTH_MAX_EXTERNAL_CALLS_PER_DAY": config.get_int("GRANTH_MAX_EXTERNAL_CALLS_PER_DAY", 50)},
        "free_tier_notes": FREE_TIER_NOTES,
        "events": events,
    }
