# Copyright and permission register

Checked 2026-11-13. Status values: AUTHORIZED, UNKNOWN, PROHIBITED. Only AUTHORIZED content is ever ingested.

| Source | Status | Basis | Action taken |
|---|---|---|---|
| NCERT textbooks (ncert.nic.in/textbook.php) | **PROHIBITED** without written permission | The copyright notice on the page allows download for personal use as a textbook/reference, and strictly prohibits republication, redistribution of copies, hosting by other sites, and use "as a part of digital content packages or software" | Not ingested. Also outside first scope: NCERT publishes in Hindi, English and Urdu |
| GSSTB textbooks (gsstb.gujarat.gov.in) | **UNKNOWN** | Board site states all rights reserved; no open licence or reuse grant found. Portal could not be reached from the build machine to read current terms | Not ingested. URL recorded |
| DIKSHA (diksha.gov.in) | **UNKNOWN** | Licence is set per content item (some CC BY, some not); no item was inspected | Not ingested |
| Bharatavani listing of GSSTB books | **UNKNOWN** | Lists GSSTB titles; licence not verified | Not ingested |
| GRANTH-AI demo books (`data/sample/`) | **AUTHORIZED** | Written for this project; CC BY 4.0; not copied from any textbook | Ingested and served |

## What is needed to add real textbooks

1. Written permission from the Gujarat State Board of School Textbooks (and NCERT, if its books are wanted)
   that explicitly covers storing the text, showing extracts to students and offline download.
2. Record the letter (date, reference, scope) in `source_permissions` and set the source to AUTHORIZED.
3. Ingest the PDFs; each edition stays `pending` until approved on the admin review page.

## Safeguards in the software

- Ingestion refuses any edition whose permission is not AUTHORIZED.
- PDF/OCR ingests are never auto-approved; an admin must review extraction quality first.
- Offline packages and page views return 404 for unapproved or rejected editions.
- `.gitignore` blocks `*.pdf` and download folders so textbook files cannot be committed by accident.

This register is not legal advice.
