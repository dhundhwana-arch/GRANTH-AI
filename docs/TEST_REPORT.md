# Test report

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
