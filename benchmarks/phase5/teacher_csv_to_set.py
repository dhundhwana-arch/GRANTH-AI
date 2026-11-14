"""Convert a teacher's question sheet (docs/templates/teacher_questions_template.csv) into a question set for
benchmarks/run_phase5.py.   usage: python teacher_csv_to_set.py IN.csv OUT.json [--book sci]

The program can only check: answered or refused, the cited page, and that `expected_answer` appears in the answer when it
is a phrase copied from the book. The teacher must still read every answer (see docs/TEACHER_REVIEW_TEMPLATE.md)."""
import csv
import json
import sys

BEHAVIOUR = {"answer": "answered", "refuse": "abstained", "correct_premise": "abstained", "show_both_editions": "edition_conflict"}
BOOKS = {"sci": "granth_vigyan_10_2026", "sci27": "granth_vigyan_10_2027", "soc": "granth_samajik_10_2026",
         "both": ["granth_vigyan_10_2026", "granth_vigyan_10_2027"]}


def main(src: str, dst: str, book: str = "sci") -> int:
    out, skipped = [], 0
    with open(src, encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
            q = (row.get("question") or "").strip()
            if not q or q.upper().startswith("EXAMPLE ROW"):
                skipped += 1
                continue
            beh = (row.get("expected_behaviour") or "").strip().lower()
            if beh not in BEHAVIOUR:
                raise SystemExit(f"row {i}: expected_behaviour must be one of {sorted(BEHAVIOUR)}")
            item = {"id": f"T{i:03d}", "cat": "teacher", "lang": (row.get("language") or "gu").strip(), "q": q,
                    "book": "both" if beh == "show_both_editions" else book, "expect": BEHAVIOUR[beh],
                    "teacher": {k: (row.get(k) or "").strip() for k in ("standard", "subject", "chapter", "expected_answer",
                                                                         "supported", "comments")}}
            page = (row.get("source_page") or "").strip()
            if item["expect"] == "answered":
                if page.isdigit():
                    item["pages"] = [int(page)]
                if (row.get("expected_answer") or "").strip():
                    item["must"] = [row["expected_answer"].strip()]
            out.append(item)
    doc = {"suite": "Teacher-written questions", "source_file": src, "books": BOOKS,
           "about": "Written by a teacher; run once; the teacher's own review of each answer is the result that counts.",
           "questions": out}
    json.dump(doc, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(out)} questions written to {dst}; {skipped} empty or example rows skipped")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    book = "sci"
    if "--book" in args:
        i = args.index("--book")
        book = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2 or book not in BOOKS:
        raise SystemExit(__doc__)
    sys.exit(main(args[0], args[1], book))
