# Architecture

Credits — Idea Contributor: **BHAVESHBHAI SOLANKI** · Founder & Developer: **DIVYESH BAMBHANIYA**

## One picture

```
Browser (web/, plain HTML + ES modules, Gujarati UI)
  typed / voice (Web Speech) / camera (tesseract.js on the device)  ──►  editable question text
  IndexedDB: downloaded books, reading progress, saved verified answers      Service worker: app shell
        │  JSON over HTTP
        ▼
granth/api.py        stdlib ThreadingHTTPServer, security headers, rate limit, admin token
        ▼
granth/answer.py     scope → cache → retrieval → sufficiency → extractive compose → verify → persist
   ├─ cache.py       shared verified-answer cache (key = question + scope + corpus version + engine version)
   ├─ retrieval.py   in-memory BM25 + character-trigram cosine over authorized, approved chunks
   ├─ providers.py   optional generative router (OFF by default); output accepted only if verified
   ├─ study.py       definitions, revision, practice questions, dictionary
   └─ cost.py        usage events: cache hits, local retrievals, external calls, limits
        ▼
granth/db.py + migrations/001_initial.sql     SQLite (portable SQL, PostgreSQL-migratable)
        ▲
granth/ingest.py     text-source route and PDF route (integrity → hash → text layer → validate → OCR fallback)
granth/structure.py  pages → chapters → sections → chunks (paragraph, table, formula, figure, example, vocabulary)
granth/ocr.py        OCR adapters (tesseract.js via Node; system tesseract if present)
granth/discovery.py  metadata-only catalogue discovery with robots.txt and per-source permission
```

## The rule that everything else serves

Every sentence of an answer is a **verbatim substring of a stored chunk** of an edition that is AUTHORIZED,
admin-approved and inside the student's selection. `verify_extractive` re-checks this against the database before
an answer leaves the engine. If the check fails, or evidence is thin, the engine abstains with the fixed refusal
sentence and no citation.

## Answer pipeline

1. Normalize the question (Unicode NFC, Gujarati spelling folds, light stemming, stop-words).
2. Resolve scope to editions. More than one edition in scope → each is answered separately; if the answers differ
   the student sees an *edition conflict* card with both, never a blend.
3. Cache lookup. A hit re-validates the evidence hashes; external calls = 0.
4. Hybrid retrieval, ranking, de-duplication.
5. Sufficiency: the best passage must cover ≥ 60% of the question's weighted terms (or ≥ 80% across the top
   passages of one chapter). Otherwise abstain.
6. Compose by mode: one-line, definition, short, detailed, point-wise, difference, formula. Marks 1–5 set the number
   of points; if the book has fewer, the answer says so instead of padding.
7. "Why" questions answer only if one textbook sentence carries every question term (guards false premises).
8. Verify, persist question / evidence / answer / verification, cache if verified.

## Fallback order

cache → local retrieval + extractive answer → (only if enabled and configured) external provider, verified →
extractive answer → abstain. With every external API off the application is fully functional; that is the default
and the tested configuration.

## Why these choices

| Choice | Reason |
|---|---|
| Python standard library server | No paid or heavy dependency; runs on a free tier or a school PC |
| SQLite, portable SQL, no FTS5 | Zero setup now; the migration file runs on PostgreSQL with minor type changes |
| BM25 + character trigrams instead of neural embeddings | Works offline, no model download, handles Gujarati inflection; a neural leg can be added behind `retrieval.search` |
| Extractive answers | Cannot hallucinate; a generative layer is optional and gated by verification |
| OCR in the browser for student photos | Photos never leave the device |
