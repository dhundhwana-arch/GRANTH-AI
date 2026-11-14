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

Every sentence of an answer is a **verbatim substring of a stored chunk** of an edition that is APPROVED,
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

## Changes in version 0.2 (engine `extractive-1.1`)

```
question → language detection (lang.py) → scope: board/medium/standard/subject/book/chapter
        → normalisation (English→Gujarati term list, stemming) → retrieval over APPROVED textbook editions
        → evidence check (coverage, false premise, ambiguity) → answer building by question type
        → sentence-level validation against the database → citations → shared verified cache → UI
                                                   └→ optional, only if the student selects it:
                                                      same engine run on ONE supplementary edition → separate block
```

- **Edition roles** (`textbook_editions.role`): `textbook`, `supplementary`, `personal`. Scope resolution returns
  textbooks only; a supplementary edition is reachable only through the explicit `supplementary_edition_id`
  parameter; a personal edition only by its owner selecting it. This is what keeps the three kinds of text apart.
- **Permission vocabulary** APPROVED / RESTRICTED / UNKNOWN / DENIED (migration `002`, upgrades old databases).
- **Extending to another board, standard or language** = registering a source (`book.json`) and ingesting it. The
  core has no board- or standard-specific code. A new language needs its own stop-words/stemmer and term list;
  today only Gujarati text processing exists, so Hindi- and English-medium books are not yet usable.
- **New endpoints**: `/api/personal-notes` (GET/POST/DELETE), `/api/saved-answers` (GET/POST/DELETE);
  `/api/ask` accepts `supplementary_edition_id` and returns `structured`, `language`, `query_translation`,
  `supplementary`.
- Voice, camera, keyboard, exam mode and suggestions all post to the same `/api/ask`; the dictionary reads the
  vocabulary built from the same ingested text.
