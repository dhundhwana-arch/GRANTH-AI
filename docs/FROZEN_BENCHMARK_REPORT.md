# Frozen benchmark report (Phase 4)

All numbers below come from files in `benchmarks/results/` produced by `benchmarks/run_phase3.py`. Nothing is estimated.

## The three kinds of set

| Set | File | Questions | Role |
|---|---|---|---|
| Development | `benchmarks/phase3/questions.json`, `heldout.json`, `heldout2.json` | 186 + 40 + 35 | Seen and tuned on (Phase 3 and Phase 4). **Not independent**, including the two files still named "heldout". |
| Validation | `benchmarks/phase4/validation.json` | 70 | Written after engine 1.3 was committed (`bcbc78d`); first run recorded; then tuned on. |
| Frozen final | `benchmarks/phase4/frozen_test.json` | 70 | Written after the engine was frozen (`b7bc20f`), committed before its first run (`da67186`), run **once**. The engine's answer logic was not changed afterwards. |

Question sets are data files, separate from the code in `granth/`. The judge is automatic: right page, required words present, forbidden words absent, and (new in Phase 4) no more sentences than allowed – a right sentence padded with unrelated ones counts as wrong.

## Frozen final test – single run, engine 1.3

Result file: `benchmarks/results/phase4_frozen_run1.json`

| Metric | Result |
|---|---|
| Questions handled correctly | **55 / 70** |
| Exact answer accuracy (answerable questions answered correctly) | 36 / 48 |
| Wrong answer rate | **4 / 70** |
| False Verified rate (answers labelled Verified that were wrong) | **1 / 27** |
| Correct refusal rate (unanswerable questions refused) | 19 / 21 |
| Incorrect refusal rate (answerable questions or conflicts refused) | 11 / 49 |
| Citation accuracy (lead citation on the right page, answers to answerable questions) | 37 / 38 |
| Paraphrase accuracy | 8 / 11 |
| Edition conflict detection | **0 / 1** |

Per category:

| Category | Passed |
|---|---|
| direct | 14 / 19 |
| paraphrase | 8 / 11 |
| mixed language | 5 / 5 |
| English | 2 / 5 |
| spelling variation | 4 / 4 |
| concept distinction | 6 / 8 |
| adversarial keyword overlap | 7 / 8 |
| unsupported | 5 / 5 |
| ambiguous | 2 / 2 |
| edition conflict (3 questions: 1 conflict, 1 single edition, 1 missing in edition) | 2 / 3 |

By language: Gujarati 48 / 60, mixed 5 / 5, English 2 / 5.

The four wrong answers and the one false Verified are listed in `EVIDENCE_VALIDATION_REPORT.md`. The missed edition conflict: "ઘરે આવતા વિદ્યુતપુરવઠાનું વોલ્ટેજ…" was refused because "ઘરે" and "આવતા" are not in the book.

## Same frozen set on the previous engine (1.2, commit `3717484`)

Result file: `benchmarks/results/phase4_frozen_engine_1.2.json`

| | Engine 1.2 | Engine 1.3 |
|---|---|---|
| Handled correctly | 43 / 70 | 55 / 70 |
| Wrong answers | 17 / 70 | 4 / 70 |
| False Verified | 8 / 28 | 1 / 27 |
| Correct refusals | 17 / 21 | 19 / 21 |
| Edition conflict detected | 1 / 1 | 0 / 1 |

Part of 1.2's wrong-answer count comes from the new "no extra sentences" rule, which 1.2 was never built to satisfy.

## Validation set

| Run | Handled correctly | Wrong | False Verified | Incorrect refusals |
|---|---|---|---|---|
| First run, engine as committed at `bcbc78d` (`phase4_validation_first_run.json`) | 54 / 70 | 4 | 2 / 31 | 12 |
| Engine 1.2 on the same set (`phase4_validation_engine_1.2.json`) | 45 / 70 | 17 | 12 / 31 | 8 |
| After tuning on it (`phase4_validation_after_tuning.json`) – no longer independent | 67 / 70 | 0 | 0 / 33 | 3 |

The first validation run (54/70) and the frozen run (55/70) are close. The 67/70 after tuning did **not** carry over to new questions. That gap is the main finding: on unseen questions expect roughly 4 in 5 handled correctly, not 19 in 20.

## Development sets (tuned on; for regression only)

186-question set 184 / 186 (0 wrong, false Verified 0 / 93); "heldout" 40 / 40; "heldout2" 35 / 35. In-house 48-question benchmark 48 / 48; independent-format checks 92 / 92.

## What these numbers do not show

* The corpus is a 14-page, self-written demo with about 45 facts. No real textbook was tested.
* Every question was written by the developer who wrote the engine. Independent in time, not in authorship.
* 70 questions is a small sample; one question is 1.4 percentage points. One frozen question ("હરીતદ્રવ્ય કોને કહે છે?") duplicates an earlier set and is recorded in the file.
* No student or teacher has judged whether the answers are useful.
* The frozen set is now seen. Any further engine change turns it into development data; a new frozen set is then needed.
