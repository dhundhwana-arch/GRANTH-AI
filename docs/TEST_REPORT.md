# Test report

## Run of 2026-11-13, engine `extractive-1.2` (Phase 3; supersedes the numbers further down)

| Suite | Command | Result |
|---|---|---|
| Python unit and API tests | `.venv/bin/python -m pytest -q` | 141 passed |
| JavaScript unit tests | `npm test` | 18 passed |
| Browser suite (headless Chromium, 390 px, touch) | `npm run test:e2e` | 33 of 33 steps |
| In-house benchmark, acceptance, OCR | `python benchmarks/run_benchmarks.py --ocr` | 48 of 48; acceptance pass; mean CER 0.0649 |
| Independent set | `python benchmarks/run_independent.py` | 91 of 92 |
| Phase 3 development set | `python benchmarks/run_phase3.py` | 179 of 186 |
| Phase 3 held-out sets, first runs | `--questions benchmarks/phase3/heldout.json` / `heldout2.json` | 36 of 40 / 32 of 35 |
| Secret scan | `python scripts/secret_scan.py --history` | clean |

New test files: `tests/test_phase3.py` (33), `tests/test_security_phase3.py` (7). Two browser steps were added: the Phase 3 answer card,
and erasing a session's data.

Not tested: any physical phone, real speech recognition, camera photos of real pages, real textbooks.

## Run of 2026-11-13, engine `extractive-1.1` (supersedes the numbers further down)

| Suite | Command | Result |
|---|---|---|
| Engine, API, ingestion, migration | `pytest tests -q` | **101 passed**, 0 failed |
| Browser modules | `npm test` | **18 passed**, 0 failed |
| Browser end-to-end, headless Chromium, 390×800 | `npm run test:e2e` | **31 of 31 steps passed** |
| In-house benchmark + acceptance | `benchmarks/run_benchmarks.py --ocr` | 48 / 48; acceptance pass; OCR mean character error 6.5% |
| Independent test set | `benchmarks/run_independent.py` | **83 of 92; 9 failures**, listed in `BENCHMARK_REPORT.md` |

New tests in this version: language detection; English, mixed and Hindi questions; structured answer and
reliability status; no percentage in the answer; ambiguity refusal; worked-example steps; formula lookup;
supplementary separation; personal-notes privacy and deletion; saved answers; registry fields; upgrade of a
first-version database.

Failures met while building this version and fixed: saved-answer list test counted nested elements (test bug);
a JavaScript error when leaving the notes screen before its list loaded (app bug, fixed); the formula lookup first
returned the wrong statement for `m = -v/u` (engine bug, fixed before commit).

Not tested: any physical phone; real Gujarati speech recognition; photos of real or handwritten pages; real
textbooks; an external AI provider with a real key; load; HTTPS deployment. There is still no CI.

All suites executed 2026-11-13 on Python 3.11, Node 22, headless Chromium 153.

| Suite | Command | Result |
|---|---|---|
| Engine, API, ingestion, OCR | `.venv/bin/python -m pytest tests -q` | **79 passed** |
| Browser modules (IndexedDB store, search, voice, image prep) | `npm test` | **18 passed** |
| Browser end-to-end, 390×800 phone viewport | `npm run test:e2e` | **24 passed** (`benchmarks/results/e2e_browser.json`) |
| Benchmark + acceptance | `python benchmarks/run_benchmarks.py --ocr` | 46 / 48; acceptance 4 / 4 |

## The 12 required feature tests

| # | Test | Ran? | How | Honest limit |
|---|---|---|---|---|
| 1 | Voice transcription | Yes | Mock recogniser in Chromium + unit test: transcript shown, editable, not auto-submitted, recorded as `voice` | **No real microphone or speech service was used**; Gujarati recognition accuracy is untested |
| 2 | Microphone permission denial | Yes | Mock returns `not-allowed`: Gujarati message, mic resets, typing still works | Mock, as above |
| 3 | Camera / image upload | Yes | Real PNG file uploaded through the gallery input; preview, rotate, crop verified | The live camera capture button cannot be driven headlessly; it shares the same code path |
| 4 | OCR extraction | Yes | Real tesseract.js in the browser and on the server | Printed, rendered text only |
| 5 | OCR correction | Yes | Mis-read text refused; corrected text answered | |
| 6 | Exam evidence validation | Yes | Every exam answer verified verbatim with page; formats tested | |
| 7 | Unsupported exam request rejection | Yes | Unsupported difference refused; 5-mark shortfall flagged | |
| 8 | Dictionary source validation | Yes | Every entry has chapter + page; unknown word refused; labels separate | |
| 9 | Offline open | Yes | Chromium network cut, page reloaded from service worker, book opened and paged | |
| 10 | Offline search | Yes | Search inside the downloaded book with network cut | |
| 11 | Cache reuse | Yes | Second identical question served from cache, 0 external calls | |
| 12 | Mobile responsiveness | Yes | No horizontal overflow at 360 and 390 px on 9 screens; touch targets ≥ 40 px | Emulated viewport, **not a physical Android phone** |

## Not tested

- Real Android device, real microphone, real camera, handwriting.
- Live GSSTB / NCERT / DIKSHA portals (unreachable from the build machine).
- Any external AI provider with a real key.
- Load, concurrency, large corpora.

## Reproducing the browser suite in a minimal container

`@sparticuz/chromium` needs its bundled libraries: extract `node_modules/@sparticuz/chromium/bin/al2023.tar.br`
and run with `LD_LIBRARY_PATH=<extracted>/lib npm run test:e2e`, or set `CHROME_PATH` to an installed Chrome.
