"""Phase 3 benchmark runner. Reads benchmarks/phase3/questions.json (gold; never read by the engine) and writes
benchmarks/results/phase3.json with every wrong answer and every wrong refusal listed.

Usage:  python benchmarks/run_phase3.py [--questions FILE] [--out FILE] [--engine-root DIR]
        --engine-root runs the SAME questions against another checkout of the engine (used for the "before" numbers).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "benchmarks" / "results" / "phase3.json"))
ap.add_argument("--engine-root", default=str(ROOT))
ap.add_argument("--questions", default=str(ROOT / "benchmarks" / "phase3" / "questions.json"))
args = ap.parse_args()
sys.path.insert(0, args.engine_root)

from granth import ENGINE_VERSION, answer, db  # noqa: E402
from granth.__main__ import seed_samples  # noqa: E402


def judge(q: dict, r: dict, ed: dict) -> dict:
    """-> outcome: correct_answer | wrong_answer | correct_refusal | incorrect_refusal | conflict_detected | conflict_missed"""
    status, exp = r["status"], q["expect"]
    txt = (r.get("answer") or {}).get("text", "") if r.get("answer") else ""
    cites = [c["page_number"] for c in r.get("citations", [])]
    content_ok = (status == "answered" and all(m in txt for m in q.get("must", []))
                  and not any(m in txt for m in q.get("must_not", [])))
    lead_ok = bool(cites) and cites[0] in q.get("pages", [])
    all_ok = bool(cites) and all(p in q.get("pages", []) for p in cites)
    out = {"lead_citation_ok": None, "all_citations_ok": None}
    if exp == "edition_conflict":
        ok = status == "edition_conflict"
        if ok:
            by = {e["edition_id"]: e["answer"]["text"] for e in r["editions"]}
            a, b = by.get(ed["granth_vigyan_10_2026"], ""), by.get(ed["granth_vigyan_10_2027"], "")
            ok = "220" in a and "230" not in a and "230" in b and "220" not in b
            ok = ok and all(ev["edition_id"] == e["edition_id"] for e in r["editions"] for ev in e["evidence"])
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
    out["lead_citation_ok"], out["all_citations_ok"] = lead_ok, all_ok
    ok = content_ok and lead_ok
    if ok and q.get("missing_in"):          # the edition without evidence must be named, never silently skipped
        ok = set(q["missing_in"]) <= {s for s, i in ed.items() for e in r.get("edition_results", [])
                                      if e["edition_id"] == i and e["status"] != "answered"}
    out["outcome"] = "correct_answer" if ok else "wrong_answer"
    return out


def main() -> int:
    spec = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    con = db.connect(Path(tempfile.mkdtemp()) / "p3.sqlite3")
    seed_samples(con)
    ed = {r["slug"]: r["id"] for r in con.execute("SELECT slug, id FROM textbook_editions")}
    book = con.execute("SELECT textbook_id FROM textbook_editions WHERE id=?", (ed["granth_vigyan_10_2026"],)).fetchone()[0]
    rows = []
    for q in spec["questions"]:
        scope = {"textbook_id": book} if q["book"] == "both" else {"edition_id": ed[spec["books"][q["book"]]]}
        r = answer.ask(con, q["q"], scope, use_cache=False)
        j = judge(q, r, ed)
        trust = ((r.get("structured") or {}).get("trust") or {}).get("status")
        rows.append({"id": q["id"], "cat": q["cat"], "lang": q["lang"], "q": q["q"], "expect": q["expect"], **j,
                     "status": r["status"], "reason": r.get("reason"), "trust": trust, "mode": r.get("mode"),
                     "pages": [c["page_number"] for c in r.get("citations", [])],
                     "answer": ((r.get("answer") or {}).get("text", "") if r.get("answer") else "")[:220]})

    good = ("correct_answer", "correct_refusal", "conflict_detected")

    def summary(rs):
        n = len(rs)
        c = defaultdict(int)
        for x in rs:
            c[x["outcome"]] += 1
        return {"n": n, "pass": sum(c[k] for k in good), **{k: c[k] for k in
                ("correct_answer", "wrong_answer", "correct_refusal", "incorrect_refusal", "conflict_detected", "conflict_missed")}}

    def rate(a, b):
        return round(a / b, 4) if b else None
    should_answer = [x for x in rows if x["expect"] == "answered"]
    should_refuse = [x for x in rows if x["expect"] == "abstained"]
    conflicts = [x for x in rows if x["expect"] == "edition_conflict"]
    answered = [x for x in rows if x["status"] == "answered"]
    verified = [x for x in rows if x["trust"] == "verified"]
    cited = [x for x in rows if x["lead_citation_ok"] is not None]
    by = lambda key: {k: summary([x for x in rows if x[key] == k]) for k in dict.fromkeys(x[key] for x in rows)}  # noqa: E731
    out = {
        "suite": spec["suite"], "engine_version": ENGINE_VERSION, "questions": len(rows),
        "overall": summary(rows),
        "metrics": {
            "correct_answer_rate": {"value": rate(sum(x["outcome"] == "correct_answer" for x in should_answer), len(should_answer)),
                                    "of": len(should_answer), "meaning": "questions the book can answer that got the right passage + right page"},
            "wrong_answer_rate": {"value": rate(sum(x["outcome"] == "wrong_answer" for x in rows), len(rows)), "of": len(rows),
                                  "count": sum(x["outcome"] == "wrong_answer" for x in rows),
                                  "meaning": "any shown answer that is wrong: wrong passage, wrong page, or an answer where refusal was required"},
            "correct_refusal_rate": {"value": rate(sum(x["outcome"] == "correct_refusal" for x in should_refuse), len(should_refuse)),
                                     "of": len(should_refuse), "meaning": "questions the book cannot answer that were refused"},
            "incorrect_refusal_rate": {"value": rate(sum(x["outcome"] == "incorrect_refusal" for x in should_answer + conflicts),
                                                     len(should_answer) + len(conflicts)), "of": len(should_answer) + len(conflicts),
                                       "meaning": "answerable questions that were refused"},
            "citation_correctness": {"lead_citation": rate(sum(bool(x["lead_citation_ok"]) for x in cited), len(cited)),
                                     "all_citations_within_gold_pages": rate(sum(bool(x["all_citations_ok"]) for x in cited), len(cited)),
                                     "of": len(cited), "meaning": "over answers shown for answerable questions"},
            "false_verified_rate": {"value": rate(sum(x["outcome"] not in good for x in verified), len(verified)), "of": len(verified),
                                    "count": sum(x["outcome"] not in good for x in verified),
                                    "meaning": "answers labelled 'Verified against source' that were wrong"},
            "edition_conflict_detection": {"value": rate(sum(x["outcome"] == "conflict_detected" for x in conflicts), len(conflicts)),
                                           "of": len(conflicts)},
            "trust_labels_on_answers": {k: sum(x["trust"] == k for x in answered) for k in ("verified", "partial")},
        },
        "by_category": by("cat"), "by_language": by("lang"),
        "failures": [x for x in rows if x["outcome"] not in good],
        "limitations": spec["limitations"], "gold_corrections": spec.get("gold_corrections", []),
        "results": rows,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("engine_version", "questions", "overall", "metrics", "by_category", "by_language")},
                     ensure_ascii=False, indent=1))
    for x in out["failures"]:
        print("FAIL", x["id"], x["outcome"], "|", x["q"], "→", x["status"], x["reason"], x["pages"], x["trust"], "|", x["answer"][:90].replace("\n", " / "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
