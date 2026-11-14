# Copyright and permission register

Checked 2026-11-13. Status values: **APPROVED, RESTRICTED, UNKNOWN, DENIED**. Only APPROVED content is ingested and
shown. This register is not legal advice.

| Source | Status | Basis (official terms) | Action |
|---|---|---|---|
| NCERT textbooks (ncert.nic.in/textbook.php) | **DENIED** | Copyright notice read on 2026-11-13: download for use as textbook/reference is allowed; republication, redistribution in any form, hosting by other sites and use "as a part of digital content packages or software" are strictly prohibited; links may be provided only with written permission. Contact given: dceta.ncert@nic.in | Not ingested, not linked from the app. Would change only with written permission |
| GSSTB / GSEB textbooks (gsstb.gujarat.gov.in) | **UNKNOWN** | Portal unreachable on 2026-11-13, so current terms could not be read. Earlier finding: all rights reserved, no open licence | Not ingested. **Blocker:** written permission from the Board |
| DIKSHA (diksha.gov.in) | **UNKNOWN** | Terms of Use (updated 07-07-2025) say the platform is for learning and that users may access and share content; the content-licence clause was not read and licences are per item | Not ingested |
| Gujarati Wikipedia | not used | CC BY-SA text; reuse would need attribution and share-alike | Not ingested; candidate supplementary source |
| GRANTH-AI demo books (`data/sample/`) | **APPROVED** | Written for this project; CC BY 4.0; not copied from any textbook | Ingested |
| GRANTH-AI supplementary notes (`data/supplementary/`) | **APPROVED** | Written for this project; CC BY 4.0; not reviewed by a teacher | Ingested as opt-in supplementary source |
| Student's own notes | private | Student confirms the right to use them; stored for that student only | Never published |

RESTRICTED is reserved for sources that allow some uses under conditions; none is recorded yet.

## Blocker and what unblocks it

Real textbooks cannot be added until the Gujarat State Board of School Textbooks (and NCERT, if wanted) gives
written permission that covers storing the text, showing extracts to students and offline download. Record the
letter (date, reference, scope) and set the source to APPROVED. All other work continues without it.

## Safeguards in the software

- Ingestion refuses any edition that is not APPROVED (personal notes are the one exception and stay private).
- PDF/OCR ingests are never auto-approved; an admin reviews extraction quality first.
- Catalogue, page views and offline packages return 404 for unapproved, rejected or other students' personal content.
- Supplementary sources are never searched unless the student selects one; they cannot be chosen as the textbook.
- Personal notes: explicit rights confirmation, 60,000-character limit, 5 per student, never in the shared cache,
  full deletion on request (text and stored answers).
- `.gitignore` blocks `*.pdf` and download folders so textbook files cannot be committed by accident.
