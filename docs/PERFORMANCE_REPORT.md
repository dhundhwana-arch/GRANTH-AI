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

## Phase 5 measurements (engine 1.4, 2026-11-14)

All figures are from the development sandbox, a Linux container. **None is an Android measurement.** Device performance is not tested.

| Measure | Result |
|---|---|
| Question latency, no cache (59 questions) | median 2.7 ms, 95th percentile 7.4 ms, slowest 56 ms |
| Question latency, cached | median 1.4 ms |
| Retrieval only (90 frozen questions) | median 0.19 ms, 95th percentile 1.7 ms |
| Python import | 0.08 s |
| Index build, demo corpus | 0.02 s |
| Server start to first health response | 0.11 s |
| Peak memory, benchmark process | 29 MB |
| Server memory after the load run | 50 MB |
| Database file | 9.3 MB after the development runs (history rows included) |
| Large synthetic corpus, 9,797 chunks | index 1.8 s, question median 20.5 ms, slowest 34 ms, peak memory 158 MB |
| HTTP, 1 client, 8 requests | median 5.7 ms |
| HTTP, 8 parallel clients, 64 requests | all succeeded, median 15 ms, 95th percentile 120 ms |
| HTTP, 32 parallel clients, 256 requests | 167 succeeded, 89 got 429 from the per-address rate limit; successful ones median 15 ms, 95th percentile 342 ms |

The Phase 5 validation stages (polarity, premise, term confidence) added well under 1 ms to the median compared with Phase 4 (2.1 ms).

Scripts: `benchmarks/run_performance.py`, `benchmarks/phase5/run_concurrency.py`. Output: `benchmarks/results/phase5/phase5_performance.json`. The Phase 4 result file is unchanged.

| | |
|---|---|
| Implemented | measurement scripts |
| Automatically tested | server-side latency, memory, start-up, synthetic large corpus, concurrency from one machine |
| Manually tested | none |
| Not tested | Android phone or tablet, slow networks, real textbooks of real size, many clients from different addresses, OCR time on a device |
| Blocked | device measurements (no device available) |
