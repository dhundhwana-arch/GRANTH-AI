# GRANTH-AI documentation

Every report in this folder was written from evidence produced by this repository: test runs, benchmark
runs and readings of the actual source files. Where something was not done, the report says so.
Nothing here is a projection.

- Project overview, setup and results: [../README.md](../README.md)
- Visual identity and architecture diagrams: [`assets/`](assets/)
- Engine version: `extractive-1.4` (frozen at commit `d4f81cf`)

---

## 1. Start here

| Document | What it answers |
|---|---|
| [PHASE5_REPORT.md](PHASE5_REPORT.md) | The current state: what the engine does, what it gets right, what it gets wrong, and the honest limits. **Read this first.** |
| [PHASE5_FROZEN_BENCHMARK.md](PHASE5_FROZEN_BENCHMARK.md) | How the 102-question frozen evaluation set was built, run once, and scored — including its own limitations. |
| [NEXT_STEPS.md](NEXT_STEPS.md) | The work that is actually outstanding, in priority order, with the reason for each item. |
| [../README.md](../README.md) | Architecture, features, installation, testing, licensing, credits. |

## 2. Phase reports (history, in order)

| Phase | Report | Baseline |
|---|---|---|
| 1 | no separate report; see [BASELINE_REPORT.md](BASELINE_REPORT.md), [TEST_REPORT.md](TEST_REPORT.md) | — |
| 2 | [ANSWER_ENGINE_REPORT.md](ANSWER_ENGINE_REPORT.md), [EVIDENCE_VALIDATION_REPORT.md](EVIDENCE_VALIDATION_REPORT.md), [RAG_ENGINE_REPORT.md](RAG_ENGINE_REPORT.md) | — |
| 3 | [PHASE3_REPORT.md](PHASE3_REPORT.md) | [FROZEN_BENCHMARK_REPORT.md](FROZEN_BENCHMARK_REPORT.md) |
| 4 | [PHASE4_REPORT.md](PHASE4_REPORT.md) | [PHASE4_BASELINE.md](PHASE4_BASELINE.md) |
| 5 | [PHASE5_REPORT.md](PHASE5_REPORT.md) | [PHASE5_FROZEN_BENCHMARK.md](PHASE5_FROZEN_BENCHMARK.md) |

Historical reports are never rewritten. When a later phase changed a result, the newer report says so and
the older file is left as it was written.

## 3. Engine behaviour, defect by defect (Phase 5)

| Report | Subject | Frozen-set result (engine 1.4) |
|---|---|---|
| [NEGATION_VALIDATION_REPORT.md](NEGATION_VALIDATION_REPORT.md) | "…without oxygen" must not be answered with the sentence about *with* oxygen | 9/14, 0 wrong |
| [UNKNOWN_TERM_REPORT.md](UNKNOWN_TERM_REPORT.md) | An unknown or look-alike technical word must never be silently replaced | 13/14, 0 wrong |
| [FALSE_PREMISE_REPORT.md](FALSE_PREMISE_REPORT.md) | A question that assumes something the book does not say | 14/14 |
| [GUJARATI_LANGUAGE_REPORT.md](GUJARATI_LANGUAGE_REPORT.md) | Question forms, verb variation, paraphrases | paraphrase 21/26, English 7/10, mixed 5/6 |
| [EDITION_CONFLICT_REPORT.md](EDITION_CONFLICT_REPORT.md) | Two editions give different values (220 V vs 230 V) | 4/6 |
| [EXPLANATION_QUALITY_REPORT.md](EXPLANATION_QUALITY_REPORT.md) | The rule-based "simple explanation", and the one wrong gloss found | 40 of 43 answers get lines |

## 4. Engineering reports

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Modules, data flow, storage, the invariants the engine must never break |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Tables, columns, indexes, migrations |
| [TEXTBOOK_SOURCE_REGISTRY.md](TEXTBOOK_SOURCE_REGISTRY.md) | The source registry: what a source is, and what state each one is in |
| [SOURCE_PERMISSION_REGISTER.md](SOURCE_PERMISSION_REGISTER.md) | Permission status per publisher, as of Phase 5 |
| [COPYRIGHT_AND_PERMISSION_REGISTER.md](COPYRIGHT_AND_PERMISSION_REGISTER.md) | The longer-form register and the reasoning behind it |
| [PDF_INGESTION_REPORT.md](PDF_INGESTION_REPORT.md) | PDF → text → chunks → vocabulary, with the admin review gate |
| [GUJARATI_OCR_REPORT.md](GUJARATI_OCR_REPORT.md) | Gujarati OCR accuracy on a printed sample (mean character error 6.5 %) |
| [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md) | All benchmark sets and what each one is for |
| [TEST_REPORT.md](TEST_REPORT.md) | How to run every suite, and what each suite covers |
| [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md) | Latency, memory, index build, concurrency (dev sandbox, not a phone) |
| [SECURITY_REPORT.md](SECURITY_REPORT.md) | Threat model, what is protected, what is not |
| [MOBILE_TEST_REPORT.md](MOBILE_TEST_REPORT.md) | Emulated-phone layout tests |
| [REAL_DEVICE_TEST_REPORT.md](REAL_DEVICE_TEST_REPORT.md) | The physical-device procedure. **Nothing in it has been carried out.** |
| [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md) | Why there is no paid API in the default path |
| [OVERNIGHT_PROGRESS.md](OVERNIGHT_PROGRESS.md) | Reverse-chronological build log, phase by phase |
| [PRESENTATION.md](PRESENTATION.md) | A short non-technical description of the project |
| [SEMANTIC_ENGINE_REPORT.md](SEMANTIC_ENGINE_REPORT.md) | Why the "semantic" leg is character trigrams, not embeddings |

## 5. Templates for work that needs other people

| Template | For |
|---|---|
| [TEACHER_REVIEW_TEMPLATE.md](TEACHER_REVIEW_TEMPLATE.md) | A subject teacher reviewing answers for accuracy |
| [STUDENT_FEEDBACK_TEMPLATE.md](STUDENT_FEEDBACK_TEMPLATE.md) | Structured student feedback |
| [templates/teacher_questions_template.csv](templates/teacher_questions_template.csv) | The CSV a teacher fills in; convert it with `benchmarks/phase5/teacher_csv_to_set.py` |
| [templates/PUBLISHER_PERMISSION_REQUEST.md](templates/PUBLISHER_PERMISSION_REQUEST.md) | The letter to send to a publisher. **Not sent.** |

None of these has been used yet. That is why the README calls GRANTH-AI a demo and not a product.

## 6. Images

| File | Contents |
|---|---|
| [assets/granth-ai-logo.svg](assets/granth-ai-logo.svg) | Logo: an open book whose right page becomes a verified evidence pathway |
| [assets/granth-ai-architecture.svg](assets/granth-ai-architecture.svg) | The seven stages of the pipeline, with the real module names |
| [assets/granth-ai-workflow.svg](assets/granth-ai-workflow.svg) | One question through validation, and the four outcomes it can produce |
| [assets/granth-ai-social-preview.svg](assets/granth-ai-social-preview.svg) | 1280×640 social preview card |
| [assets/screenshots/](assets/screenshots/) | Real screenshots of the running demo (see the note in that section of the README) |

The diagrams are generated by [`../scripts/build_visual_assets.py`](../scripts/build_visual_assets.py);
`python3 scripts/build_visual_assets.py --check` fails if a committed file is out of date.

## 7. Where the numbers come from

| Number in the README | Produced by | Recorded in |
|---|---|---|
| 102 questions, 83 handled as expected, 19 incorrect refusals, 0 wrong | `benchmarks/run_phase5.py` on `benchmarks/phase5/frozen_test.json` | `benchmarks/results/phase5/phase5_frozen_run1.json` |
| 34/34 correct refusals, 43/43 lead citations, 0 false Verified | same run, `metrics` and `confusion_matrix` keys | same file |
| 224 Python tests | `.venv/bin/python -m pytest tests -q` | this repository, at HEAD |
| 18 JavaScript tests | `npm test` | this repository, at HEAD |
| 34 browser steps | `npm run test:e2e` | `benchmarks/results/e2e_browser.json` |
| Latency and memory | `benchmarks/run_performance.py` | `benchmarks/results/phase5/phase5_performance.json` |
| Regression figures | `benchmarks/results/phase5/regression_*_engine_1.4.json` | same folder |

Frozen sets and their recorded results are read-only. A change to engine behaviour requires a new engine
version and a new frozen set — never an edit to an existing one.
