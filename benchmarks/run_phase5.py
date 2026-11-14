"""Phase 5 benchmark runner.

Usage:  python benchmarks/run_phase5.py --questions FILE --out FILE [--engine-root DIR]

The judge is the Phase 4 judge (benchmarks/run_phase3.py), copied without change of rules:
  answered   -> lead citation on a gold page, every 'must' string present, no 'must_not' string, <= max_sentences
  abstained  -> the engine must refuse
  either     -> refusal accepted; an answer must satisfy the answered rules
  edition_conflict -> both editions shown separately with their own value and their own evidence
New in Phase 5: EVERY row is stored (not only failures), a confusion matrix, per-capability accuracy, paraphrase-group
consistency and automatic explanation checks. Gold files are data; the engine never reads them.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--engine-root", default=str(ROOT))
ap.add_argument("--questions", required=True)
args = ap.parse_args()
sys.path.insert(0, args.engine_root)

from granth import ENGINE_VERSION, answer, db  # noqa: E402
from granth.__main__ import seed_samples  # noqa: E402

GOOD = ("correct_answer", "correct_refusal", "conflict_detected")


def judge(q: dict, r: dict, ed: dict) -> dict:
    status, exp = r["status"], q["expect"]
    txt = (r.get("answer") or {}).get("text", "") if r.get("answer") else ""
    cites = [c["page_number"] for c in r.get("citations", [])]
    content_ok = (status == "answered" and all(m in txt for m in q.get("must", []))
                  and not any(m in txt for m in q.get("must_not", [])))
    if content_ok and q.get("max_sentences"):
        content_ok = len(r["answer"]["parts"]) <= q["max_sentences"]
    lead_ok = bool(cites) and cites[0] in q.get("pages", [])
    out = {"lead_citation_ok": None}
    if exp == "edition_conflict":
        ok = status == "edition_conflict"
        if ok:
            by = {e["edition_id"]: e["answer"]["text"] for e in r["editions"]}
            a, b = by.get(ed["granth_vigyan_10_2026"], ""), by.get(ed["granth_vigyan_10_2027"], "")
            ok = "220" in a and "230" not in a and "230" in b and "220" not in b
            ok = ok and all(ev["edition_id"] == e["edition_id"] for e in r["editions"] for ev in e["evidence"])
            ok = ok and all(e.get("citations") and e["citations"][0].get("page_number") for e in r["editions"])
        out["outcome"] = "conflict_detected" if ok else ("incorrect_refusal" if status == "abstained" else "conflict_missed")
        return out
    if exp == "abstained":
        out["outcome"] = "correct_refusal" if status == "abstained" else "wrong_answer"
        return out
    if status == "abstained":
        out["outcome"] = "correct_refusal" if exp == "either" else "incorrect_refusal"
        return out
    if status != "answered":
        out["outcome"] = "wrong_answer"
        return out
    out["lead_citation_ok"] = lead_ok
    out["outcome"] = "correct_answer" if (content_ok and lead_ok) else "wrong_answer"
    return out


def explanation_checks(r: dict) -> dict | None:
    """Automatic part of the explanation evaluation. Meaning preservation and readability for a child need a human."""
    if r["status"] != "answered":
        return None
    from granth import explain, gujarati as g
    e = r.get("explanation") or (r.get("structured") or {}).get("explanation") or {}
    lines = e.get("lines") or []
    src = " ".join(p["text"] for p in r["answer"]["parts"])
    words = lambda t: len(t.split())  # noqa: E731
    src_sents = [p["text"] for p in r["answer"]["parts"] if p.get("kind", "sentence") == "sentence"]
    by_src = defaultdict(list)
    for ln in lines:
        by_src[(ln.get("evidence") or [{}])[0].get("quote", "")].append(ln)
    consistent = all(explain.verify(v, k) for k, v in by_src.items()) if lines else None
    return {"has_simplified_lines": bool(lines), "has_glossary_terms": bool(e.get("terms")), "has_english_terms": bool(e.get("english_terms")),
            "fallback_shown": not lines, "every_line_has_evidence": all(ln.get("evidence") for ln in lines) if lines else None,
            "no_new_content_words": consistent,
            "numbers_and_formulas_kept": (set(__import__("re").findall(r"[0-9]+|[A-Za-z]+", src)) <=
                                          set(__import__("re").findall(r"[0-9]+|[A-Za-z]+", " ".join(ln["text"] for ln in lines)))) if lines else None,
            "avg_words_source_sentence": round(sum(map(words, src_sents)) / len(src_sents), 1) if src_sents else None,
            "avg_words_simplified_line": round(sum(words(ln["text"]) for ln in lines) / len(lines), 1) if lines else None,
            "lines": [ln["text"] for ln in lines], "source": src[:400], "content_terms_source": len(set(g.content_terms(src)))}


def main() -> int:
    spec = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    con = db.connect(Path(tempfile.mkdtemp()) / "p5.sqlite3")
    seed_samples(con)
    ed = {r["slug"]: r["id"] for r in con.execute("SELECT slug, id FROM textbook_editions")}
    book = con.execute("SELECT textbook_id FROM textbook_editions WHERE id=?", (ed["granth_vigyan_10_2026"],)).fetchone()[0]
    rows = []
    for q in spec["questions"]:
        scope = {"textbook_id": book} if q["book"] == "both" else {"edition_id": ed[spec["books"][q["book"]]]}
        r = answer.ask(con, q["q"], scope, use_cache=False)
        j = judge(q, r, ed)
        trust = ((r.get("structured") or {}).get("trust") or {}).get("status")
        txt = (r.get("answer") or {}).get("text", "") if r.get("answer") else ""
        if r["status"] == "edition_conflict":
            txt = " || ".join(f'{e.get("edition_label", e["edition_id"])}: {e["answer"]["text"]} (p.{e["citations"][0]["page_number"] if e.get("citations") else "?"})' for e in r["editions"])
        rows.append({"id": q["id"], "cat": q["cat"], "lang": q["lang"], "group": q.get("group"), "q": q["q"], "expect": q["expect"], **j,
                     "status": r["status"], "reason": r.get("reason"), "trust": trust, "mode": r.get("mode"),
                     "pages": [c["page_number"] for c in r.get("citations", [])], "answer": txt[:400],
                     "intent": (r.get("validation") or {}).get("intent"), "negated_terms": (r.get("validation") or {}).get("negated_terms"),
                     "term_matches": r.get("term_matches"), "unknown_terms": r.get("unknown_terms"), "did_you_mean": r.get("did_you_mean"),
                     "book_says": [b["text"] for b in ((r.get("premise") or {}).get("book_says") or [])],
                     "explanation": explanation_checks(r)})

    def summary(rs):
        c = Counter(x["outcome"] for x in rs)
        return {"n": len(rs), "pass": sum(c[k] for k in GOOD), **{k: c[k] for k in
                ("correct_answer", "wrong_answer", "correct_refusal", "incorrect_refusal", "conflict_detected", "conflict_missed")}}

    def frac(a, b):
        return {"count": a, "of": b}
    answerable = [x for x in rows if x["expect"] == "answered"]
    unanswerable = [x for x in rows if x["expect"] == "abstained"]
    conflicts = [x for x in rows if x["expect"] == "edition_conflict"]
    verified = [x for x in rows if x["trust"] == "verified" and x["status"] == "answered"]
    cited = [x for x in rows if x["lead_citation_ok"] is not None and x["expect"] in ("answered", "either")]
    by = lambda key: {str(k): summary([x for x in rows if x[key] == k]) for k in dict.fromkeys(x[key] for x in rows)}  # noqa: E731
    actual = lambda x: {"correct_answer": "answered_correctly", "wrong_answer": "answered_wrongly", "correct_refusal": "refused",  # noqa: E731
                        "incorrect_refusal": "refused", "conflict_detected": "showed_both_editions", "conflict_missed": "answered_wrongly"}[x["outcome"]]
    confusion = {e: dict(Counter(actual(x) for x in rows if x["expect"] == e)) for e in ("answered", "abstained", "either", "edition_conflict")}
    groups = defaultdict(list)
    for x in rows:
        if x["group"]:
            groups[x["group"]].append(x)
    expl = [x["explanation"] for x in rows if x["explanation"] and x["outcome"] == "correct_answer"]
    out = {
        "suite": spec["suite"], "engine_version": ENGINE_VERSION, "questions": len(rows),
        "overall": summary(rows),
        "counts": {"total": len(rows), "answerable": len(answerable), "unanswerable": len(unanswerable),
                   "either": sum(x["expect"] == "either" for x in rows), "edition_conflict": len(conflicts)},
        "metrics": {
            "correct_answers": frac(sum(x["outcome"] == "correct_answer" for x in answerable), len(answerable)),
            "wrong_answers": frac(sum(x["outcome"] in ("wrong_answer", "conflict_missed") for x in rows), len(rows)),
            "correct_refusals": frac(sum(x["outcome"] == "correct_refusal" for x in unanswerable), len(unanswerable)),
            "incorrect_refusals": frac(sum(x["outcome"] == "incorrect_refusal" for x in rows), len(answerable) + len(conflicts)),
            "false_verified": frac(sum(x["outcome"] != "correct_answer" for x in verified), len(verified)),
            "citation_accuracy": frac(sum(bool(x["lead_citation_ok"]) for x in cited), len(cited)),
            "edition_conflict": frac(sum(x["outcome"] == "conflict_detected" for x in conflicts), len(conflicts)),
        },
        "confusion_matrix": {"rows": "expected behaviour", "columns": "actual behaviour", "matrix": confusion},
        "by_category": by("cat"), "by_language": by("lang"),
        "paraphrase_groups": {"groups": len(groups), "all_phrasings_handled": sum(all(x["outcome"] in GOOD for x in v) for v in groups.values()),
                              "detail": {k: f'{sum(x["outcome"] in GOOD for x in v)}/{len(v)}' for k, v in groups.items()}},
        "explanations_automatic": {
            "answers_checked": len(expl),
            "with_simplified_lines": sum(e["has_simplified_lines"] for e in expl),
            "fallback_shown": sum(e["fallback_shown"] for e in expl),
            "with_glossary_terms": sum(e["has_glossary_terms"] for e in expl),
            "with_english_terms": sum(e["has_english_terms"] for e in expl),
            "lines_without_new_content_words": frac(sum(e["no_new_content_words"] is True for e in expl), sum(e["has_simplified_lines"] for e in expl)),
            "lines_with_evidence_link": frac(sum(e["every_line_has_evidence"] is True for e in expl), sum(e["has_simplified_lines"] for e in expl)),
            "numbers_and_formulas_kept": frac(sum(e["numbers_and_formulas_kept"] is True for e in expl), sum(e["has_simplified_lines"] for e in expl)),
            "note": "automatic checks only; meaning preservation and readability are NOT judged by this script"},
        "failures": [x for x in rows if x["outcome"] not in GOOD],
        "rows": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("suite", "engine_version", "overall", "metrics", "by_category", "by_language")}, ensure_ascii=False, indent=1))
    for x in out["failures"]:
        print("FAIL", x["id"], x["outcome"], "|", x["q"], "→", x["status"], x["reason"], x["pages"], x["trust"], "|", x["answer"][:110].replace("\n", " / "), "| unk", x["unknown_terms"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
