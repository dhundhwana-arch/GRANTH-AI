"""Run the GRANTH-AI benchmark on the bundled sample books and write real, reproducible results.

    python benchmarks/run_benchmarks.py            # QA benchmark + acceptance test
    python benchmarks/run_benchmarks.py --ocr      # additionally measure OCR character error rate (needs npm install)

Nothing here calls an external service. Every number in docs/BENCHMARK_REPORT.md comes from the JSON this writes.
"""
from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from granth import ENGINE_VERSION, answer, cost, db, gujarati as g, retrieval  # noqa: E402
from granth.__main__ import seed_samples  # noqa: E402

OUT = ROOT / "benchmarks" / "results"
K = 3
REFUSAL = "આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી."


def fresh_db():
    con = db.connect(Path(tempfile.mkdtemp(prefix="granth-bench-")) / "bench.sqlite3")
    seed_samples(con)
    ed = {r["slug"]: r["id"] for r in con.execute("SELECT slug, id FROM textbook_editions")}
    return con, {"sci": ed["granth_vigyan_10_2026"], "sci27": ed["granth_vigyan_10_2027"], "soc": ed["granth_samajik_10_2026"]}


def scope_for(con, ids, item):
    if item["book"] == "sci_all":
        return {"standard": 10, "subject": "વિજ્ઞાન"}, [ids["sci"], ids["sci27"]]
    sc = {"edition_id": ids[item["book"]]}
    if item.get("chapter"):
        sc["chapter_id"] = con.execute("SELECT id FROM chapters WHERE edition_id=? AND number=?",
                                       (ids[item["book"]], item["chapter"])).fetchone()[0]
    return sc, [ids[item["book"]]]


def corpus_texts(con, edition_ids):
    q = "SELECT text FROM text_chunks WHERE edition_id IN (%s)" % ",".join("?" * len(edition_ids))
    return [g.normalize_text(r[0]) for r in con.execute(q, edition_ids)]


def variants(r):
    """Flatten a result into the answer variants it contains (one, or one per edition for a conflict)."""
    if r["status"] == "answered":
        return [r]
    if r["status"] == "edition_conflict":
        return r["editions"]
    return []


def run_qa():
    con, ids = fresh_db()
    spec = json.loads((ROOT / "benchmarks" / "questions.json").read_text(encoding="utf-8"))
    rows = []
    for item in spec["questions"]:
        sc, eds = scope_for(con, ids, item)
        res = retrieval.search(con, item["q"], eds, sc.get("chapter_id"), k=K)
        ranked_pages = [r["page_number"] for r in res["results"]]
        t0 = time.perf_counter()
        r = answer.ask(con, item["q"], sc, session_id="benchmark", use_cache=False)
        ms = (time.perf_counter() - t0) * 1000
        vs = variants(r)
        text = "\n".join(v["answer"]["text"] for v in vs)
        cited = [c["page_number"] for v in vs for c in v["citations"]]
        parts = [p for v in vs for p in v["answer"]["parts"]]
        ev_texts = [g.normalize_text(e["text"]) for v in vs for e in v["evidence"]]
        corpus = corpus_texts(con, eds)
        row = {"id": item["id"], "cat": item["cat"], "question": item["q"], "expected": item["expect"], "status": r["status"],
               "reason": r.get("reason"), "latency_ms": round(ms, 2), "cited_pages": cited, "retrieved_pages": ranked_pages,
               "external_api_calls": r.get("external_api_calls", 0)}
        row["status_ok"] = r["status"] == item["expect"]
        gold = set(item.get("pages", []))
        if gold:                                           # retrieval metrics only where a gold page exists
            hits = [p in gold for p in ranked_pages[:K]]
            row["p_at_1"] = 1.0 if hits[:1] == [True] else 0.0
            row["p_at_k"] = sum(hits) / K
            row["r_at_k"] = len(gold & set(ranked_pages[:K])) / len(gold) if item["book"] != "sci_all" else float(any(hits))
            row["rr"] = next((1 / (i + 1) for i, h in enumerate(hits) if h), 0.0)
        if vs:
            row["citation_ok"] = bool(cited) and (all(p in gold for p in cited) if gold else True)
            row["faithful"] = all(any(g.normalize_text(p["text"]) in c for c in corpus) for p in parts)      # verbatim in the selected book
            row["evidence_coverage"] = sum(any(g.normalize_text(p["text"]) in e for e in ev_texts) for p in parts) / max(len(parts), 1)
            row["content_ok"] = all(m in text for m in item.get("must", [])) and not any(m in text for m in item.get("must_not", []))
            row["answer"] = text
        else:
            row["refusal_text_ok"] = r.get("message") == REFUSAL and not r.get("citations")
        if item["expect"] == "abstained":
            row["success"] = row["status_ok"] and row.get("refusal_text_ok", False)
        else:
            row["success"] = bool(row["status_ok"] and row.get("citation_ok") and row.get("faithful") and row.get("content_ok"))
        rows.append(row)

    def mean(key, sel=rows):
        vals = [float(x[key]) for x in sel if key in x]
        return round(sum(vals) / len(vals), 4) if vals else None

    should_abstain = [x for x in rows if x["expected"] == "abstained"]
    should_answer = [x for x in rows if x["expected"] != "abstained"]
    answered = [x for x in rows if x["status"] != "abstained"]
    by_cat = defaultdict(list)
    for x in rows:
        by_cat[x["cat"]].append(x)
    lat = sorted(x["latency_ms"] for x in rows)
    summary = {
        "questions": len(rows), "k": K,
        "end_to_end_success_rate": mean("success"),
        "precision_at_1": mean("p_at_1"), f"precision_at_{K}": mean("p_at_k"), f"recall_at_{K}": mean("r_at_k"), "mrr": mean("rr"),
        "citation_correctness": mean("citation_ok", answered), "evidence_coverage": mean("evidence_coverage", answered),
        "faithfulness_verbatim": mean("faithful", answered), "answer_content_correct": mean("content_ok", should_answer),
        "abstention_accuracy": round(sum(x["status"] == "abstained" for x in should_abstain) / len(should_abstain), 4),
        "false_refusal_rate": round(sum(x["status"] == "abstained" for x in should_answer) / len(should_answer), 4),
        "wrong_answer_instead_of_refusal": sum(x["status"] != "abstained" for x in should_abstain),
        "latency_ms": {"median": round(statistics.median(lat), 2), "p95": lat[int(0.95 * (len(lat) - 1))], "max": lat[-1]},
        "external_api_calls": sum(x["external_api_calls"] for x in rows),
        "by_category": {c: {"name": spec["categories"][c], "n": len(v), "success": sum(bool(x["success"]) for x in v)} for c, v in sorted(by_cat.items())},
        "failures": [{"id": x["id"], "question": x["question"], "expected": x["expected"], "got": x["status"], "reason": x.get("reason"),
                      "answer": x.get("answer", "")[:200]} for x in rows if not x["success"]],
        "precision_note": f"Retrieval is scored per retrieved passage: a hit is a passage from a gold page. P@{K} is below 1 whenever fewer than {K} passages on the gold page mention the question terms, so P@1, R@{K} and MRR are the more informative numbers.",
    }
    con.close()
    return {"summary": summary, "rows": rows}


def run_acceptance():
    """Final acceptance test: Student A / B / C and 'all external APIs disconnected'."""
    con, ids = fresh_db()
    sc = {"board": None, "standard": 10, "subject": "વિજ્ઞાન", "edition_id": ids["sci"]}
    q = "પ્રકાશસંશ્લેષણ એટલે શું?"
    out = {}
    t = time.perf_counter(); a = answer.ask(con, q, sc, session_id="student-A"); a_ms = (time.perf_counter() - t) * 1000
    out["student_A"] = {"question": q, "status": a["status"], "answer": a["answer"]["text"], "cited_pages": [c["page_number"] for c in a["citations"]],
                        "chapter": a["citations"][0]["chapter_title"], "verified": a["verification"]["verified"], "cache_hit": a["cache"]["hit"],
                        "external_api_calls": a["external_api_calls"], "ms": round(a_ms, 2),
                        "pass": a["status"] == "answered" and a["citations"][0]["page_number"] == 1 and not a["cache"]["hit"]}
    t = time.perf_counter(); b = answer.ask(con, q, sc, session_id="student-B"); b_ms = (time.perf_counter() - t) * 1000
    out["student_B"] = {"question": q, "status": b["status"], "cache_hit": b["cache"]["hit"], "same_answer": b["answer"]["text"] == a["answer"]["text"],
                        "external_api_calls": b["external_api_calls"], "ms": round(b_ms, 2),
                        "pass": b["cache"]["hit"] and b["external_api_calls"] == 0 and b["answer"]["text"] == a["answer"]["text"]}
    c = answer.ask(con, "જ્વાળામુખી કેવી રીતે ફાટે છે?", sc, session_id="student-C")
    out["student_C"] = {"question": "જ્વાળામુખી કેવી રીતે ફાટે છે?", "status": c["status"], "message": c.get("message"), "citations": len(c.get("citations") or []),
                        "pass": c["status"] == "abstained" and c.get("message") == REFUSAL}
    # APIs disconnected: generative switched off and a router with no providers; cache bypassed so retrieval really runs.
    from granth.providers import Router
    d = answer.ask(con, "ઓહ્મનો નિયમ લખો", sc, session_id="offline", use_cache=False, router=Router([], enabled=False, daily_limit=0))
    out["apis_disconnected"] = {"question": "ઓહ્મનો નિયમ લખો", "status": d["status"], "cited_pages": [x["page_number"] for x in d.get("citations", [])],
                                "external_api_calls": d["external_api_calls"], "pass": d["status"] == "answered" and d["external_api_calls"] == 0}
    con.commit()
    st = cost.summary(con)
    out["usage"] = {"external_api_calls": st["external_api_calls"], "cache": st["cache"], "local_retrievals": st["local_retrievals"]}
    out["all_pass"] = all(out[k]["pass"] for k in ("student_A", "student_B", "student_C", "apis_disconnected"))
    con.close()
    return out


def run_extraction():
    """Extraction accuracy of the source-text route: every authored page must be stored character-for-character (after normalisation)."""
    con, ids = fresh_db()
    from granth import structure
    res = []
    for slug_dir in sorted((ROOT / "data" / "sample").iterdir()):
        src = (slug_dir / "content.txt").read_text(encoding="utf-8")
        ed = con.execute("SELECT id FROM textbook_editions WHERE slug=?", (slug_dir.name,)).fetchone()[0]
        stored = {r["page_number"]: r["text"] for r in con.execute("SELECT page_number, text FROM pages WHERE edition_id=?", (ed,))}
        import re
        pages = re.split(r"^=== પૃષ્ઠ (\d+) ===\s*$", src, flags=re.M)
        cers = []
        for i in range(1, len(pages), 2):
            ref = g.normalize_text(pages[i + 1]).strip()
            cers.append(g.cer(ref, g.normalize_text(stored.get(int(pages[i]), "")).strip()))
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t} WHERE edition_id=?", (ed,)).fetchone()[0] for t in ("pages", "chapters", "text_chunks")}
        res.append({"edition": slug_dir.name, "pages": len(cers), "max_page_cer": round(max(cers), 4), "mean_page_cer": round(sum(cers) / len(cers), 4), **counts})
    con.close()
    return res


def run_ocr():
    """OCR character error rate on the rendered printed sample PDF (tesseract.js guj+eng). Printed text only."""
    import re
    from granth import ocr
    pdf = ROOT / "var" / "sample_pdfs" / "granth_vigyan_10_2026.pdf"
    ok, why = ocr.TesseractJsAdapter().available()
    if not ok or not pdf.exists():
        return {"ran": False, "reason": why if not ok else "sample PDF missing: run scripts/build_sample_pdf.py"}
    import fitz
    src = (ROOT / "data" / "sample" / "granth_vigyan_10_2026" / "content.txt").read_text(encoding="utf-8")
    parts = re.split(r"^=== પૃષ્ઠ (\d+) ===\s*$", src, flags=re.M)
    ref = {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}
    tmp = Path(tempfile.mkdtemp(prefix="granth-ocr-"))
    doc = fitz.open(pdf)
    imgs = []
    for n, page in enumerate(doc, start=1):
        p = tmp / f"p{n}.png"
        page.get_pixmap(dpi=200).save(p)
        imgs.append(p)
    t0 = time.perf_counter()
    out = ocr.TesseractJsAdapter().recognize(imgs)
    secs = time.perf_counter() - t0
    squash = lambda s: re.sub(r"\s+", " ", g.normalize_text(s)).strip()
    per = []
    for n, o in enumerate(out, start=1):
        text = o["text"] if isinstance(o, dict) else o.text
        conf = o["confidence"] if isinstance(o, dict) else o.confidence
        per.append({"page": n, "cer": round(g.cer(squash(ref[n]), squash(text)), 4), "engine_confidence": round(conf, 3)})
    cers = [p["cer"] for p in per]
    return {"ran": True, "engine": "tesseract.js 7 (guj+eng), 200 dpi", "material": "printed, computer-rendered sample PDF (NOT scanned, NOT handwritten)",
            "pages": len(per), "seconds": round(secs, 1), "mean_cer": round(sum(cers) / len(cers), 4), "max_cer": max(cers), "min_cer": min(cers), "per_page": per}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    meta = {"executed_at": stamp, "engine_version": ENGINE_VERSION, "corpus": "bundled CC BY 4.0 sample books (data/sample)"}
    qa = run_qa()
    (OUT / "qa_benchmark.json").write_text(json.dumps({**meta, **qa}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    acc = run_acceptance()
    (OUT / "acceptance.json").write_text(json.dumps({**meta, **acc}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ext = run_extraction()
    (OUT / "extraction.json").write_text(json.dumps({**meta, "editions": ext}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qa["summary"], ensure_ascii=False, indent=2))
    print("acceptance all_pass:", acc["all_pass"])
    print("extraction:", ext)
    if "--ocr" in sys.argv:
        o = run_ocr()
        (OUT / "ocr_cer.json").write_text(json.dumps({**meta, **o}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("ocr:", {k: v for k, v in o.items() if k != "per_page"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
