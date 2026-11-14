# Progress log

Last updated: 2026-11-14 (UTC). **IDEA CONTRIBUTOR: BHAVESHBHAI SOLANKI** · **FOUNDER & PROJECT DEVELOPER: DIVYESH BAMBHANIYA**

## Completed phases

| Phase | State | Evidence |
|---|---|---|
| 0 Repository audit + baseline | Done | `docs/BASELINE_REPORT.md` |
| 1 Textbook discovery engine | Built and unit-tested; **live portals unreachable, 0 real books found** | `granth/discovery.py`, `data/registry/discovered.json` |
| 2 PDF ingestion + Gujarati OCR | Done on demo PDFs | `docs/PDF_INGESTION_REPORT.md`, `docs/GUJARATI_OCR_REPORT.md` |
| 3 Knowledge database | Done (SQLite, 20 tables) | `docs/DATABASE_SCHEMA.md` |
| 4 Textbook-only answer engine | Done | `docs/RAG_ENGINE_REPORT.md` |
| 5 Gujarati mobile web app | Done, browser-tested | `web/`, `tests/e2e/` |
| 6 Benchmarks A–L | Done, 46 / 48 at v1.0; 48 / 48 at v1.1 (one gold answer changed, see report) | `docs/BENCHMARK_REPORT.md` |
| 7 GitHub checkpoints | Done on `arena/b93bc898-granth-ai` (see below) | `git log` |
| 8 Documentation | Done | `docs/` |
| Add-on 1: cache, cost, providers, acceptance test | Done; providers exercised with fakes only | `benchmarks/results/acceptance.json` |
| Add-on 2: voice, camera, exam, dictionary, offline | Done; limits in `docs/TEST_REPORT.md` | `benchmarks/results/e2e_browser.json` |

## Current phase — information engine mission (2026-11-13)

Started from verified commit `571da29` (tree clean, `main` untouched). Delivered on the same branch:

| Milestone | State | Evidence |
|---|---|---|
| Permission vocabulary APPROVED/RESTRICTED/UNKNOWN/DENIED, edition roles, saved answers (migration 002) | Done | `granth/migrations/002_permissions_roles.sql`, upgrade test |
| Engine 1.1: English/mixed questions, structured answer, reliability status, steps, formula lookup, ambiguity refusal | Done | `docs/ANSWER_ENGINE_REPORT.md` |
| Opt-in supplementary source; private personal notes | Done | `tests/test_engine_v2.py` |
| UI: answer card, source buttons, supplementary block, saved answers, notes | Done, 31/31 browser steps | `benchmarks/results/e2e_browser.json` |
| Independent test set | Done, 83/92, failures listed | `docs/BENCHMARK_REPORT.md` |
| Portal investigation | NCERT terms read (DENIED); DIKSHA partly read (UNKNOWN); GSSTB unreachable (UNKNOWN) | `docs/TEXTBOOK_SOURCE_REGISTRY.md` |

Blockers: no publisher permission, so no real textbook; GSSTB portal unreachable; no physical phone available.

## Phase 3 — accuracy and understanding (2026-11-13)

Started from verified commit `a52e409`. Existing code was inspected and extended, not rebuilt.

| Priority | State | Evidence |
|---|---|---|
| 1 Wrong-answer bug (focal length of a concave mirror) | Fixed, with regression tests | `granth/concepts.py`, `tests/test_phase3.py`, `docs/PHASE3_REPORT.md` |
| 2 Paraphrase, mixed language, spelling | Improved; paraphrase is still the weakest category | `data/glossary/`, `granth/retrieval.py` |
| 3 Editions answered separately, conflict on paraphrase | Done on the one conflicting demo fact | `edition_results` in the API |
| 4 Simple explanation without an API | Done, modest depth | `granth/explain.py` |
| 5 Independent benchmark | 186 development + 40 + 35 held-out questions | `docs/BENCHMARK_REPORT.md` |
| 6 Real-device testing | **Not done.** Procedure written | `docs/MOBILE_TEST_REPORT.md` |
| 7 Source permissions | Re-checked; no status changed; no real textbook | `docs/TEXTBOOK_SOURCE_REGISTRY.md` |
| 8 Security and release audit | Weak admin tokens refused, lockout, erase-my-data, secret scan | `docs/SECURITY_REPORT.md` |

Verified pushed commits of this phase: `d530dde` (engine 1.2), `d54b0ea` (benchmark; engine frozen for held-out
set 1), `b9b2075` (fixes after set 1; frozen for set 2), `c9e29ff` (stricter Verified rule, results), `cfd946a`
(security), then the documentation commit that contains this file (`git log -1`).

Not production-ready: wrong answers still occur on unseen questions (3 of 75 on first runs), no real textbook is
loaded, and no physical phone has been used.

## Branch

The work is on **`arena/b93bc898-granth-ai`**, not `feature/granth-ai-textbook-engine`: the build environment
fixes the session to that branch and does not allow creating or pushing another. `main` is untouched; no force
push; no history rewritten. To get the requested name, open a pull request from this branch or create
`feature/granth-ai-textbook-engine` from it on GitHub.

## Commits

Every push was verified by fetching and comparing `HEAD` with `origin/arena/b93bc898-granth-ai`.

| Milestone | Verified pushed commit |
|---|---|
| Backend engine, ingestion, API, first tests | `c9964e1` |
| Web app, browser tests, engine fixes | `e0e6604` |
| Benchmarks and acceptance results | `5fc7c9a` |
| Documentation (first version) | `571da29` |
| Engine 1.1, UI, independent test set | `76566a6` |
| Documentation for version 0.2 | the commit that contains this file — run `git log -1` |

## Failures and how they were handled

- Official portals unreachable (TLS closed) → recorded as UNREACHABLE; not bypassed.
- No system OCR or PDF tools → tesseract.js (WebAssembly) on server and in browser.
- PDF text layer garbled for Gujarati → validation rejects it, OCR fallback.
- Empty `GRANTH_DB_PATH=` in `.env` crashed the server → fixed.
- Browser OCR failed to load (engine file missing for newer Chrome) → engine package updated to 7.0.0, fixed.
- Benchmark first run 43 / 48 → three defects fixed, two left failing and reported.
- False-premise question was being answered → fixed with a test.

## Pending

Real textbooks (permission), live discovery run, real-device testing, handwriting, external provider with a real
key, scale testing, HTTPS deployment, CI. See `docs/NEXT_STEPS.md`.

## Exact next action

Test on real phones (`docs/MOBILE_TEST_REPORT.md`) and send the permission request to the Gujarat State Board of School Textbooks; meanwhile run
`python -m granth discover` from a machine with normal internet access and commit the updated
`data/registry/discovered.json`.

## Phase 4 (2026-11-13)

| Checkpoint | Commit | What |
|---|---|---|
| 1 | `bcbc78d` | Engine 1.3: intent classification + evidence validator; dev sets 184/186, 40/40, 35/35 |
| 2 | `b7bc20f` | Validation set (first run 54/70, after tuning 67/70); engine frozen |
| 3 | `da67186` | Frozen test set committed before its run |
| 4 | `b76ae46` | Frozen run: 55/70, 4 wrong, 1 false Verified |
| 5 | final Phase 4 commit | Admin token expiry, "how the question was understood" line in the UI, performance measurements, Phase 4 documents |

Not done: real-device test, embedding evaluation, source permissions (sites unreachable), fixes for the frozen-test failures.

## Phase 5 (2026-11-14)

| Checkpoint | Commit | What |
|---|---|---|
| 1 | `3831b65` | Phase 4 baseline preserved and reproduced (55/70 identical) |
| 2 | `2c3f130` | Negation and polarity validation, conservative unknown-term matching, false-premise stage |
| 3 | `4cee29c` | Gujarati question forms, Phase 5 runner, development set (76) |
| 4 | `d4f81cf` | Explanations with English terms, 43 new tests, engine frozen as 1.4 |
| 5 | `50c9f98`, `c3ee08c` | Frozen set of 102 questions committed before its run |
| 6 | `fe309c2` | Frozen run: 83/102, 0 wrong, 19 incorrect refusals, 0 false Verified |
| 7 | final Phase 5 commit | 15 documents, teacher and student templates, permission request template, performance and regression results |

Not done: real-device test, teacher review, student trial, publisher permission, embedding evaluation, fixes for the 19 frozen refusals.
