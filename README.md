# GRANTH-AI

**Textbook-only question answering for Gujarati-medium students.**
A student picks Board → Medium → Standard → Subject → Textbook → Chapter and asks in Gujarati. The answer is built
only from the text of that authorized textbook, with chapter and page number. If the book does not support an
answer, GRANTH-AI says so:

> આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી.

## Credits

- **IDEA CONTRIBUTOR: BHAVESHBHAI SOLANKI**
- **FOUNDER & DEVELOPER: DIVYESH BAMBHANIYA**

GRANTH-AI — An initiative conceptualized from an educational idea shared by Bhaveshbhai Solanki and developed and
engineered by Divyesh Bambhaniya. Our mission is to make verified textbook-based knowledge accessible to
Gujarati-medium students.

## Status (first functional version, 2026-11-13)

| Area | State |
|---|---|
| Answer engine (extractive, verbatim, cited, abstaining) | Working, tested |
| Shared verified-answer cache, cost accounting, provider router | Working, tested; external AI is **off** by default and not needed |
| Web app (Gujarati, mobile-first): selection, ask, evidence, page viewer, history | Working, browser-tested |
| Voice question, camera/gallery question with on-device OCR | Working; voice tested with a mock recogniser only, OCR tested on printed text only |
| Exam mode, chapter revision, practice questions, dictionary | Working, tested |
| Offline library (download, read, search, progress, delete) | Working, tested with the network cut |
| PDF ingestion with Gujarati OCR fallback + admin review | Working on a printed sample PDF (mean CER 6.5%) |
| **Real GSEB / NCERT textbooks** | **Not included.** No permission; see below |

**Important:** the only content in this repository is three small *self-written demo books* (CC BY 4.0), labelled
"GRANTH-AI Sample Board (demo – NOT GSEB)". NCERT prohibits use of its books inside software; GSSTB publishes no
open licence. Until written permission is obtained, real textbooks must not be ingested. Details:
[docs/COPYRIGHT_AND_PERMISSION_REGISTER.md](docs/COPYRIGHT_AND_PERMISSION_REGISTER.md).

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install pymupdf pytest
npm install                                  # OCR engine + test tools
.venv/bin/python scripts/setup_vendor.py     # copies the OCR engine into web/vendor (not committed)
.venv/bin/python -m granth seed-samples      # loads the demo books
.venv/bin/python -m granth serve             # http://localhost:8000
```

The server itself needs only the Python standard library; PyMuPDF and Node are needed for PDF ingestion and OCR.
Copy `.env.example` to `.env` to change settings. To use the source-review page (`/#/admin`) set
`GRANTH_ADMIN_TOKEN` in `.env`.

## Test it

```bash
.venv/bin/python -m pytest tests -q          # 79 engine/API/ingestion tests
npm test                                     # 18 browser-module tests
npm run test:e2e                             # 24 browser end-to-end steps (headless Chromium)
.venv/bin/python scripts/build_sample_pdf.py && .venv/bin/python benchmarks/run_benchmarks.py --ocr
```

Results of the last run are in [docs/TEST_REPORT.md](docs/TEST_REPORT.md) and
[docs/BENCHMARK_REPORT.md](docs/BENCHMARK_REPORT.md); raw output is in `benchmarks/results/`.

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [Database schema](docs/DATABASE_SCHEMA.md) ·
[Source registry](docs/TEXTBOOK_SOURCE_REGISTRY.md) · [Copyright register](docs/COPYRIGHT_AND_PERMISSION_REGISTER.md) ·
[PDF ingestion](docs/PDF_INGESTION_REPORT.md) · [Gujarati OCR](docs/GUJARATI_OCR_REPORT.md) ·
[RAG engine](docs/RAG_ENGINE_REPORT.md) · [Benchmarks](docs/BENCHMARK_REPORT.md) · [Tests](docs/TEST_REPORT.md) ·
[Security](docs/SECURITY_REPORT.md) · [Free-tier research](docs/FREE_TIER_RESEARCH.md) ·
[Progress log](docs/OVERNIGHT_PROGRESS.md) · [Next steps](docs/NEXT_STEPS.md) · [Presentation](docs/PRESENTATION.md) ·
[Baseline](docs/BASELINE_REPORT.md)

## Licence

Code: see `LICENSE`. Demo books in `data/sample/`: CC BY 4.0, written for this project.
Noto Sans Gujarati font: SIL Open Font License. Tesseract.js and language data: Apache-2.0.
