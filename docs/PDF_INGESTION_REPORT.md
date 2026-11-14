# PDF ingestion report

## Pipeline (`granth/ingest.py`)

1. **Integrity** – file opens, has pages, is not encrypted.
2. **Hash + duplicate check** – SHA-256 of the file; a file already registered is reported as duplicate.
3. **Permission gate** – edition must be APPROVED.
4. **Text layer** – extracted per page with PyMuPDF.
5. **Gujarati validation** – share of Gujarati letters, broken-cluster and replacement-character checks. A page that
   fails is not trusted.
6. **OCR fallback** – failed pages are rendered at 200 dpi and read with Tesseract (Gujarati + English).
7. **Normalization** – Unicode NFC, zero-width cleanup, header/footer noise removal.
8. **Structure** – chapter headings, numbered sections, paragraphs, tables, formulas, figure captions, worked
   examples, glossary; page numbers preserved on every chunk.
9. **Quality record** – one `extraction_quality` row per page; one `ingestion_jobs` row per attempt.
10. **Review** – result stays `pending` until an admin approves it.

## What was actually ingested

| Input | Route | Result |
|---|---|---|
| 3 demo books as source text | text | 14 pages, 8 chapters, 90 chunks; stored text identical to source (CER 0.0000 on every page, `benchmarks/results/extraction.json`) |
| Demo science book rendered to PDF (10 pages) | PDF → text layer rejected → OCR | Ingested; mean CER 6.5% (see OCR report) |
| Demo social-science book rendered to PDF (2 pages) | PDF → OCR | Ingested; chapters and sections detected; a question is answered with the right page |
| Any real GSEB / NCERT PDF | — | **None. Not permitted, not attempted** |

## Findings

- The text layer of the test PDFs is garbled for Gujarati (glyph order, not Unicode order). Validation catches it
  on every page and OCR takes over. Real board PDFs may or may not have a usable text layer — untested.
- OCR drops blank lines, so section headings run into paragraphs; the structure parser now recognises a numbered
  heading even without a blank line before it.
- Without Node/tesseract.js installed, PDF ingestion fails with a clear message and stores nothing.

## Known weaknesses

- Latin formulas and table cells are often wrong after OCR (e.g. `pH` → `PH`). Formula recovery from the Latin text
  layer is not implemented.
- The quality gate uses Gujarati-validity and engine confidence; it cannot detect a wrong but valid-looking word
  (`જળચક્ર` → `જળચક્ઠ`). Human review before approval is required and is enforced.
- Multi-column layouts, scanned pages, images inside pages: untested.
