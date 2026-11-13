# Database schema

Source of truth: `granth/migrations/001_initial.sql` (20 tables). SQLite today. The SQL avoids SQLite-only features
(no FTS5, no `WITHOUT ROWID`, no JSON functions) so it can move to PostgreSQL by changing
`INTEGER PRIMARY KEY` to an identity column and `TEXT` timestamps to `timestamptz`.

| Table | Holds |
|---|---|
| `textbook_sources` | Publisher/portal (GSSTB, NCERT, DIKSHA, sample board) |
| `source_permissions` | Permission status per source with basis, URL, date checked |
| `subjects` | Subject names |
| `textbooks` | Board, medium, standard, subject, title |
| `textbook_editions` | Edition label/year, slug, file hash, licence, `permission_status`, `review_status`, `corpus_version` |
| `chapters`, `sections` | Number, title, page range |
| `pages` | Page number, full text, extraction method, confidence |
| `text_chunks` | The retrieval unit (see below) |
| `ingestion_jobs` | One row per ingestion attempt: file, hash, method, status, error |
| `extraction_quality` | Per-page Gujarati validation score, OCR engine confidence, notes |
| `questions` | Text, normalized text, scope, session, input method (typed/voice/camera) |
| `retrieved_evidence` | Chunk, rank and scores for each question |
| `generated_answers` | Answer text, mode, status, engine version, provider (if any) |
| `verification_results` | Verification method, pass/fail, details |
| `answer_cache` | Verified answers keyed by question + scope + versions |
| `usage_events` | Cache hit/miss, local retrieval, external call, tokens |
| `feedback` | Student reports on an answer |
| `vocabulary`, `saved_words` | Dictionary entries with source page; words a student saved |

## `text_chunks`

Each chunk carries everything needed to cite it without a join: board, medium, standard, subject, book title,
edition label, chapter number/title, section title, page number, source id, permission status, kind
(paragraph / table / formula / figure / example / vocabulary), text, SHA-256 of the text, extraction confidence.

## Rules enforced in code

- Only editions with `permission_status = 'AUTHORIZED'` **and** `review_status = 'approved'` are indexed or served.
- Re-ingesting an edition increments `corpus_version`, which invalidates its cache entries.
- A PDF whose SHA-256 is already registered is reported as a duplicate and not ingested again.
