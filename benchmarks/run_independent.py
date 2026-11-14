"""Independent test set runner. Writes benchmarks/results/independent.json with every failure listed.

Usage: python benchmarks/run_independent.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from granth import answer, api, db, ingest  # noqa: E402
from granth.__main__ import seed_samples  # noqa: E402


def main() -> int:
    spec = json.loads((ROOT / "benchmarks" / "independent" / "questions.json").read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp()) / "ind.sqlite3"
    con = db.connect(tmp)
    seed_samples(con)
    ed = {r["slug"]: r["id"] for r in con.execute("SELECT slug, id FROM textbook_editions")}
    sup = con.execute("SELECT id FROM textbook_editions WHERE role='supplementary'").fetchone()[0]
    rows, cats = [], defaultdict(lambda: [0, 0])

    def record(id_, cat, desc, ok, got, note=""):
        cats[cat][0] += bool(ok)
        cats[cat][1] += 1
        rows.append({"id": id_, "category": cat, "test": desc, "passed": bool(ok), "got": got, "note": note})

    for q in spec["questions"]:
        r = answer.ask(con, q["q"], {"edition_id": ed[spec["books"][q["book"]]]}, use_cache=False)
        pages = sorted({c["page_number"] for c in r.get("citations", [])})
        ok = r["status"] == q["expect"]
        if ok and q["expect"] == "answered":
            ok = bool(set(pages) & set(q["pages"])) and all(m in r["answer"]["text"] for m in q.get("must", []))
        got = {"status": r["status"], "reason": r.get("reason"), "pages": pages, "trust": r["structured"]["trust"]["status"],
               "answer": (r.get("answer") or {}).get("text", "")[:160] if r.get("answer") else ""}
        record(q["id"], q["cat"], q["q"], ok, got, q.get("why", ""))

    sci, sci27, soc = ed["granth_vigyan_10_2026"], ed["granth_vigyan_10_2027"], ed["granth_samajik_10_2026"]
    book = con.execute("SELECT textbook_id FROM textbook_editions WHERE id=?", (sci,)).fetchone()[0]

    # --- conflicting editions (question phrased independently of the book wording, and one near the wording)
    r = answer.ask(con, "ઘરમાં આવતી વીજળીનું વોલ્ટેજ કેટલું હોય છે?", {"textbook_id": book}, use_cache=False)
    record("CE01", "conflicting_editions", "paraphrased voltage question over both editions → must not merge 220 and 230",
           r["status"] in ("edition_conflict", "abstained"), {"status": r["status"], "reason": r.get("reason")},
           "pass = conflict shown or refusal; a single merged answer would be a failure")
    record("CE01b", "conflicting_editions", "same paraphrase: ideally the conflict itself is detected",
           r["status"] == "edition_conflict", {"status": r["status"], "reason": r.get("reason")})
    r = answer.ask(con, "ઘરવપરાશના વિદ્યુતપુરવઠાનું વોલ્ટેજ કેટલું છે?", {"textbook_id": book}, use_cache=False)
    txt = json.dumps(r, ensure_ascii=False)
    record("CE02", "conflicting_editions", "voltage question over both editions → edition_conflict with both values shown separately",
           r["status"] == "edition_conflict" and "220" in txt and "230" in txt, {"status": r["status"]})
    r = answer.ask(con, "ઘરવપરાશના વિદ્યુતપુરવઠાનું વોલ્ટેજ કેટલું છે?", {"edition_id": sci27}, use_cache=False)
    record("CE03", "conflicting_editions", "2027 edition alone → 230 only",
           r["status"] == "answered" and "230" in r["answer"]["text"] and "220" not in r["answer"]["text"], {"status": r["status"]})

    # --- missing pages / unavailable sources
    def http_status(fn):
        try:
            fn()
            return 200
        except api.ApiError as e:
            return e.status
    record("MP01", "missing_pages", "page 99 of a 10-page book → 404", http_status(lambda: api.page(con, sci, 99)) == 404, {})
    record("MP02", "missing_pages", "page of an unknown edition → 404", http_status(lambda: api.page(con, 9999, 1)) == 404, {})
    r = answer.ask(con, "ઓહ્મનો નિયમ લખો", {"edition_id": sci}, use_cache=False)
    cited_ok = all(http_status(lambda c=c: api.page(con, c["edition_id"], c["page_number"])) == 200 for c in r["citations"])
    record("MP03", "missing_pages", "every cited page can be opened", r["status"] == "answered" and cited_ok, {})

    # --- unsupported subjects / boards / languages
    for i, (scope, desc) in enumerate([({"subject": "ગણિત"}, "subject ગણિત (no source added)"),
                                        ({"board": "GSEB"}, "board GSEB (no approved source)"),
                                        ({"board": "NCERT"}, "board NCERT (permission denied)"),
                                        ({"standard": 12}, "standard 12 (no source added)")], 1):
        r = answer.ask(con, "પ્રકાશસંશ્લેષણ એટલે શું?", scope, use_cache=False)
        record(f"US0{i}", "unsupported_scope", desc + " → refusal, reason no_authorized_textbook_in_scope",
               r["status"] == "abstained" and r["reason"] == "no_authorized_textbook_in_scope", {"status": r["status"], "reason": r.get("reason")})
    r = answer.ask(con, "प्रकाश संश्लेषण क्या है?", {"edition_id": sci}, use_cache=False)
    record("US05", "unsupported_scope", "Hindi question → refusal (no Hindi source)", r["status"] == "abstained", {"reason": r.get("reason")})

    # --- supplementary separation
    r = answer.ask(con, "ન્યૂટનનો ત્રીજો નિયમ સમજાવો", {"edition_id": sci}, use_cache=False)
    record("SU01", "supplementary_mode", "not selected → no supplementary block at all", r["status"] == "abstained" and r["supplementary"] is None, {})
    r = answer.ask(con, "ન્યૂટનનો ત્રીજો નિયમ સમજાવો", {"edition_id": sci}, use_cache=False, supplementary_edition_id=sup)
    s = r["supplementary"]
    record("SU02", "supplementary_mode", "selected → textbook part still refuses, supplementary answers separately with its own label",
           r["status"] == "abstained" and r["answer"] is None and s and s["status"] == "answered"
           and all(p["source_type"] == "supplementary" for p in s["answer"]["parts"]), {"sup_status": s and s["status"]})
    r = answer.ask(con, "What is quadratic equation?", {"edition_id": sci}, use_cache=False, supplementary_edition_id=sup)
    record("SU03", "supplementary_mode", "English maths definition via supplementary source",
           r["status"] == "abstained" and r["supplementary"]["status"] == "answered" and "દ્વિઘાત સમીકરણ કહે છે" in r["supplementary"]["answer"]["text"], {})
    r = answer.ask(con, "દ્વિઘાત સમીકરણનું ઉદાહરણ પગલાંવાર સમજાવો", {"edition_id": sci}, use_cache=False, supplementary_edition_id=sup)
    record("SU04", "supplementary_mode", "step-by-step worked example from the supplementary source",
           r["supplementary"]["status"] == "answered" and "પગલું 4" in r["supplementary"]["answer"]["text"], {})
    r = answer.ask(con, "પ્રકાશસંશ્લેષણ એટલે શું?", {"edition_id": sup}, use_cache=False)
    record("SU05", "supplementary_mode", "a supplementary source can never be chosen as the textbook", r["status"] == "abstained", {"reason": r.get("reason")})

    # --- cache correctness
    q = "પરાવર્તન એટલે શું?"
    a1 = answer.ask(con, q, {"edition_id": sci}, session_id="stu-a-000001")
    a2 = answer.ask(con, q, {"edition_id": sci}, session_id="stu-b-000002")
    record("CA01", "cache", "identical question + scope → second student served from cache with identical text and sources",
           not a1["cache"]["hit"] and a2["cache"]["hit"] and a1["answer"]["text"] == a2["answer"]["text"] and a1["citations"] == a2["citations"], {})
    a3 = answer.ask(con, q, {"edition_id": soc})
    record("CA02", "cache", "same question, different book → not served from the other book's cache", not a3["cache"]["hit"] and a3["status"] == "abstained", {})
    a4 = answer.ask(con, q, {"edition_id": sci}, mode="detailed")
    record("CA03", "cache", "same question, different answer type → separate cache entry", not a4["cache"]["hit"], {})
    ingest.ingest_text_source(con, ROOT / "data" / "sample" / "granth_vigyan_10_2026", force=True, auto_approve=True)
    a5 = answer.ask(con, q, {"edition_id": sci})
    record("CA04", "cache", "re-ingesting the book (corpus version change) invalidates the cached answer", not a5["cache"]["hit"] and a5["status"] == "answered", {})
    from granth import cache as cache_mod
    k1 = cache_mod.make_key("x", {"edition_ids": [1]}, {1: 1}, "extractive-1.0")
    k2 = cache_mod.make_key("x", {"edition_ids": [1]}, {1: 1}, "extractive-1.1")
    record("CA05", "cache", "engine version is part of the cache key", k1 != k2, {})
    a6 = answer.ask(con, "ઓહ્મનો નિયમ લખો", {"edition_id": sci}, supplementary_edition_id=sup)
    a7 = answer.ask(con, "ઓહ્મનો નિયમ લખો", {"edition_id": sci})
    record("CA06", "cache", "an answer cached while a supplementary source was selected does not carry supplementary text to a textbook-only request",
           a7["supplementary"] is None and a6["answer"]["text"] == a7["answer"]["text"], {})

    # --- personal material privacy
    n = ingest.add_personal_notes(con, "stu-a-000001", "મારી નોંધ", "ચુંબકની આસપાસ જે વિસ્તારમાં તેની અસર અનુભવાય છે તે વિસ્તારને ચુંબકીય ક્ષેત્ર કહે છે.", True)
    mine = answer.ask(con, "ચુંબકીય ક્ષેત્ર એટલે શું?", {"edition_id": n["edition_id"]}, session_id="stu-a-000001")
    other = answer.ask(con, "ચુંબકીય ક્ષેત્ર એટલે શું?", {"edition_id": n["edition_id"]}, session_id="stu-b-000002")
    everyone = answer.ask(con, "ચુંબકીય ક્ષેત્ર એટલે શું?", {}, session_id="stu-b-000002")
    record("PM01", "personal_material", "owner gets an answer from own notes, labelled personal, never cached",
           mine["status"] == "answered" and mine["structured"]["answer_source_type"] == "personal" and not mine["cache"]["hit"]
           and con.execute("SELECT COUNT(*) FROM answer_cache WHERE payload_json LIKE '%ચુંબકીય%'").fetchone()[0] == 0, {})
    record("PM02", "personal_material", "another student cannot use the notes, even with the id; notes are not in any wider scope",
           other["status"] == "abstained" and everyone["status"] != "answered", {"other": other.get("reason"), "all": everyone["status"]})
    record("PM03", "personal_material", "notes are absent from the public catalogue and offline packages",
           "મારી નોંધ" not in json.dumps(api.catalog(con), ensure_ascii=False)
           and http_status(lambda: api.offline_package(con, n["edition_id"])) == 404, {})
    try:
        ingest.add_personal_notes(con, "stu-a-000001", "x", "ચુંબકને બે ધ્રુવ હોય છે: ઉત્તર ધ્રુવ અને દક્ષિણ ધ્રુવ.", False)
        refused = False
    except ingest.IngestionRefused:
        refused = True
    record("PM04", "personal_material", "notes without the rights confirmation are refused", refused, {})
    gone = ingest.delete_personal_notes(con, "stu-a-000001", n["edition_id"])
    left = con.execute("SELECT COUNT(*) FROM text_chunks WHERE edition_id=?", (n["edition_id"],)).fetchone()[0] \
        + con.execute("SELECT COUNT(*) FROM generated_answers WHERE answer_json LIKE '%ચુંબકીય ક્ષેત્ર કહે%'").fetchone()[0]
    record("PM05", "personal_material", "delete erases the text and stored answers that quoted it", gone and left == 0, {"left": left})

    # --- offline package
    pkg = api.offline_package(con, sci)
    record("OF01", "offline", "offline package of an approved book carries all pages", len(pkg["pages"]) == 10 and pkg["edition"]["permission_status"] == "APPROVED", {})
    con.execute("UPDATE textbook_editions SET review_status='pending' WHERE id=?", (soc,))
    record("OF02", "offline", "a book that is not approved cannot be downloaded", http_status(lambda: api.offline_package(con, soc)) == 404, {})

    failed = [r for r in rows if not r["passed"]]
    out = {"suite": "independent test set (questions not written from the demo books' wording)",
           "engine_version": answer.ENGINE_VERSION, "total": len(rows), "passed": len(rows) - len(failed), "failed": len(failed),
           "by_category": {k: {"passed": v[0], "total": v[1]} for k, v in cats.items()},
           "wrong_answers_instead_of_refusal": [r["id"] for r in failed if r["got"].get("status") == "answered" and r["category"] not in ("conflicting_editions",)
                                                and any(q["id"] == r["id"] and q["expect"] == "abstained" for q in spec["questions"])],
           "failures": failed, "results": rows,
           "not_covered_here": "offline behaviour in a real browser and phone-size layout are covered by tests/e2e/run_e2e.mjs (emulated viewport, not a physical phone)"}
    (ROOT / "benchmarks" / "results" / "independent.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("total", "passed", "failed", "by_category", "wrong_answers_instead_of_refusal")}, ensure_ascii=False, indent=1))
    for f in failed:
        print("FAIL", f["id"], f["test"][:70], "→", f["got"].get("status"), f["got"].get("reason"), f["got"].get("pages"), "|", (f["got"].get("answer") or "")[:90])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
