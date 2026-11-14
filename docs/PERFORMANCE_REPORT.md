# Performance report (Phase 4)

Measured on the development sandbox (x86-64 Linux server, Python 3.11) with `benchmarks/run_performance.py`; raw output in `benchmarks/results/phase4_performance.json`. **Nothing here was measured on an Android device.** The answer engine runs on the server; the phone or tablet runs only the web page, the offline store and (optionally) on-device OCR.

| Measurement | Result |
|---|---|
| Server start to first page served | 0.09 s |
| Server memory at idle (RSS) | 25 MB |
| Python import of the engine | 0.05 s |
| Loading the 4 demo books into a new database | 0.03 s |
| Building the search index (97 chunks) | 0.01 s |
| Question → answer, no cache (59 frozen-set questions) | median 2 ms, 95th percentile 9 ms, slowest 45 ms |
| Question → answer, repeated | median 1.5 ms |
| Cache hits when the same 59 questions are asked again | 33 / 59 (the 33 are the questions that produced an answer) |
| Peak process memory during the run | 29 MB |
| PDF open + first page text, 10-page 6.2 MB demo PDF (server side, PyMuPDF) | 5 ms; rendering page 1: 3 ms |
| OCR of 10 printed demo pages (tesseract.js on the server) | 18 s total, mean character error rate 0.065 |

## Large-textbook check (synthetic)

The demo chunks were copied 100 times (97 → 9,797 chunks, roughly a 1,000-page book of repeated text):

| | Result |
|---|---|
| Index build | 1.2 s |
| Question → answer | median 19 ms, slowest 29 ms |
| Peak memory | 157 MB |

Repeated text is not a real book: vocabulary does not grow, so this understates index size for a real 1,000-page textbook. Memory grows roughly in line with chunk count because the index is held in RAM.

## Not measured

* Page load, PDF viewing, OCR and memory use **on an Android phone or tablet**.
* Service-worker offline behaviour on a real device (it is exercised in headless Chromium by the e2e test: the offline textbook step passes).
* Behaviour on a slow mobile network.
* More than one user at a time.

## Dependencies

No model and no paid service is used. A local embedding model was not added: it could not be downloaded here, so neither its benefit nor its cost was demonstrated.
