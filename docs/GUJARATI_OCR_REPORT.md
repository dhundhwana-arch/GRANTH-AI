# Gujarati OCR report

## Engine chosen

Tesseract 5 LSTM through **tesseract.js 7** (WebAssembly), languages `guj+eng`, "best-int" models. Reasons: free,
no system install, the same engine runs on the server (PDF ingestion) and in the student's browser (camera
questions, image never uploaded). No other engine was installed or compared.

## Measured (2026-11-13, `benchmarks/results/ocr_cer.json`)

Material: the 10-page demo science book, **computer-rendered** to PDF and rasterised at 200 dpi. Reference: the
source text. Whitespace collapsed before comparison.

| Metric | Value |
|---|---|
| Mean character error rate | **6.49%** |
| Best / worst page | 2.26% / 12.83% |
| Time for 10 pages | 15.6 s |

Resolution check on two pages (earlier run): 150 dpi → 13.4% / 9.0%; 200 dpi → 8.4% / 10.7%; 300 dpi → 13.9% / 5.2%.
No setting was best on both, so 200 dpi was kept.

In the browser: a rendered image of “હરિતદ્રવ્ય કોને કહે છે?” was read exactly, in about 1.3 s, and answered with the
correct page (`benchmarks/results/e2e_browser.json`).

## Typical errors

- Conjuncts and rare clusters: `જળચક્ર` → `જળચક્ઠ`, `શબ્દાર્થ` → `શબ્દાચ`.
- Large headings lose marks: `જળ સંસાધન` → `જળ સસાધન`.
- Latin text inside Gujarati lines: formulas, digits and `pH` → `PH`.
- Table cells and page headers produce noise.

## What this does and does not show

- Shown: clean printed Gujarati is readable enough for search and for short question photos, **with student
  correction** (the text box is always editable before submit).
- **Not tested: handwriting, phone photos of real pages (blur, skew, shadow), scanned books.** No claim is made for
  them. Expect clearly worse results.
- 6.5% CER is too high to publish textbook text unreviewed; hence admin approval for every OCR ingest.
