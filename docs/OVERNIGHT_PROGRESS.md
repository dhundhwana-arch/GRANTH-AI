# Progress log

Last updated: 2026-11-13 (UTC). **IDEA CONTRIBUTOR: BHAVESHBHAI SOLANKI** · **FOUNDER & PROJECT DEVELOPER: DIVYESH BAMBHANIYA**

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
