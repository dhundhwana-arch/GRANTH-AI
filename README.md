# GRANTH-AI

GRANTH-AI is an educational information platform designed to help students understand their curriculum through
clear, accessible and evidence-grounded answers. It aims to make verified educational knowledge easier to access
for students across languages, subjects and educational boards.

- **IDEA CONTRIBUTOR: BHAVESHBHAI SOLANKI**
- **FOUNDER & PROJECT DEVELOPER: DIVYESH BAMBHANIYA**

A student picks Board → Medium → Standard → Subject → Textbook → Chapter and asks a question in Gujarati, English
or a mix. The answer is taken only from the text of the selected, approved source and is shown as
**પ્રશ્ન / સરળ જવાબ / મુખ્ય મુદ્દા / પુસ્તકનો આધાર / વિશ્વસનીયતા સ્થિતિ**, with a link to the cited page. If the
source does not support an answer, GRANTH-AI says so:

> આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી.

## What is and is not supported today (2026-11-13)

**No official board textbook is included.** No GSEB, NCERT or other board, standard or subject is supported yet,
because no publisher permission exists (GSSTB: UNKNOWN, NCERT: DENIED, DIKSHA: UNKNOWN — see the
[permission register](docs/COPYRIGHT_AND_PERMISSION_REGISTER.md)).

What the app actually contains:

| Content | Role | Permission |
|---|---|---|
| 3 small self-written demo books, "GRANTH-AI Sample Board (demo – NOT GSEB)", Std 10 Science (2 editions) and Social Science, Gujarati | textbook | APPROVED (own work, CC BY 4.0) |
| 1 self-written 4-page supplementary note set (Newton's third law, Constitution dates, quadratic equation, mitosis/meiosis) | supplementary, opt-in only | APPROVED (own work, CC BY 4.0); not reviewed by a teacher |
| A student's own pasted notes | personal, private to that student | user-provided |

The engine, registry and UI are board-, standard- and language-agnostic: a new approved source is added by writing a
`book.json` and ingesting it; nothing in the core changes.

| Area | State |
|---|---|
| Answer engine `extractive-1.2`: Gujarati, English and mixed questions; definitions, short/detailed/points, marks-based, differences, formulas, worked examples step by step; refusal when unsupported or ambiguous | Working, tested |
| Structured answer with reliability status (Verified against source / Partially supported / Insufficient source evidence), no percentages | Working, tested |
| Opt-in supplementary source, shown in a separate labelled block | Working, tested |
| Private personal notes (rights confirmation, per-student, never cached or published, deletable) | Working, tested |
| Shared verified-answer cache, saved answers, history | Working, tested |
| Voice and camera question input | Working in an emulated browser only (mock recogniser; printed text). **Not tested on a real phone** |
| Exam mode, revision, practice questions, dictionary, offline library | Working, tested |
| PDF ingestion with Gujarati OCR + admin review | Working on a printed sample PDF (mean character error 6.5%) |

Honest limits: answers are the source's own sentences, selected and arranged — the app does not paraphrase unless an
optional AI provider is configured (none is, and none is required). Since engine 1.2 common spelling slips, everyday synonyms and English terms are
matched, and answers that rest on an assumed word are labelled "Partially supported". Questions worded very differently from the book are
still refused, and a small share of answers is still wrong: see the [Phase 3 report](docs/PHASE3_REPORT.md) and the
[answer engine report](docs/ANSWER_ENGINE_REPORT.md).

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install pymupdf pytest
npm install                                  # OCR engine + test tools
.venv/bin/python scripts/setup_vendor.py     # copies the OCR engine into web/vendor (not committed)
.venv/bin/python -m granth seed-samples      # loads the demo books and the supplementary notes
.venv/bin/python -m granth serve             # http://localhost:8000
```

The server needs only the Python standard library; PyMuPDF and Node are needed for PDF ingestion and OCR.
An existing database from the first version is upgraded automatically (migration 002).
Copy `.env.example` to `.env` to change settings; set `GRANTH_ADMIN_TOKEN` to use the review page (`/#/admin`).
The token must be at least 24 random characters; short or well-known values are refused.
`GRANTH_ALLOW_WEAK_ADMIN_TOKEN=1` lifts that check for local development only — never set it on a public server.
Students can erase everything stored for their browser session from the history page.

## Test it

```bash
.venv/bin/python -m pytest tests -q                    # 142 engine / API / ingestion / security tests
npm test                                               # 18 browser-module tests
npm run test:e2e                                       # 33 browser steps (headless Chromium, phone-size viewport)
.venv/bin/python benchmarks/run_benchmarks.py --ocr    # 48-question in-house set + acceptance + OCR
.venv/bin/python benchmarks/run_independent.py         # 92-check independent set (91 pass, 1 fail — listed in the report)
.venv/bin/python benchmarks/run_phase3.py              # Phase 3 set, 186 questions (179 pass); --questions for the held-out sets
.venv/bin/python scripts/secret_scan.py --history      # secret scan of tracked files and all commits
```

## Documentation

[Phase 3 report](docs/PHASE3_REPORT.md) · [Architecture](docs/ARCHITECTURE.md) · [Answer engine](docs/ANSWER_ENGINE_REPORT.md) ·
[Source registry](docs/TEXTBOOK_SOURCE_REGISTRY.md) · [Copyright register](docs/COPYRIGHT_AND_PERMISSION_REGISTER.md) ·
[Benchmarks](docs/BENCHMARK_REPORT.md) · [Tests](docs/TEST_REPORT.md) · [Mobile test](docs/MOBILE_TEST_REPORT.md) ·
[Security](docs/SECURITY_REPORT.md) · [Progress log](docs/OVERNIGHT_PROGRESS.md) · [Next steps](docs/NEXT_STEPS.md) ·
[Database schema](docs/DATABASE_SCHEMA.md) · [PDF ingestion](docs/PDF_INGESTION_REPORT.md) ·
[Gujarati OCR](docs/GUJARATI_OCR_REPORT.md) · [RAG engine (v1.0 notes)](docs/RAG_ENGINE_REPORT.md) ·
[Free-tier research](docs/FREE_TIER_RESEARCH.md) · [Presentation](docs/PRESENTATION.md) · [Baseline](docs/BASELINE_REPORT.md)

## Licence

Code: see `LICENSE`. Demo books in `data/sample/` and notes in `data/supplementary/`: CC BY 4.0, written for this
project. Noto Sans Gujarati font: SIL Open Font License. Tesseract.js and language data: Apache-2.0.
