# Source permission register (Phase 4)

Checked 2026-11-13. Rule used: "free to read" or "for education" is **not** permission to copy, store, redistribute or package offline. Only a written licence or written permission counts.

| Source | Status | Basis | In the public corpus? |
|---|---|---|---|
| GRANTH-AI demo books (વિજ્ઞાન 2026, વિજ્ઞાન 2027, સામાજિક 2026) and supplementary notes | **APPROVED** | Written for this project, CC BY 4.0, labelled "GRANTH-AI Sample Board (demo – NOT GSEB)" | Yes |
| GSSTB (Gujarat State School Textbook Board) textbooks | **UNKNOWN** | No licence text has been read. The board's site could not be reached from the build environment in Phase 3, and in Phase 4 the environment could reach only GitHub, npm and PyPI. | No |
| NCERT textbooks | **DENIED** | NCERT's copyright notice reserves rights; no redistribution licence found (recorded in Phase 3, `data/registry/discovered.json`). | No |
| DIKSHA | **UNKNOWN** | Only 3 of 12 parts of the terms of use were read in Phase 3; the rest could not be fetched in Phase 4. Content on DIKSHA carries per-item licences that would have to be checked item by item. | No |
| Gujarati Wikipedia (CC BY-SA) | Candidate, not ingested | Licence allows reuse with attribution and share-alike; it is not a textbook. | No |
| A student's own notes | PERSONAL | Stored for that session only, never shared, deleted with the session. | No |

**Phase 4 made no progress on permissions: the sites were not reachable.** No real board, standard or subject is supported.

## How ingestion respects this

* Every edition has a permission status: `APPROVED`, `RESTRICTED`, `UNKNOWN` or `DENIED`.
* Only `APPROVED` editions are searchable and downloadable. Others appear locked with their status.
* A new book is added by configuration: a `book.json` with source, licence and permission evidence plus the text or PDF, then `python -m granth ingest`. Without `APPROVED` it stays locked.
* PDFs are not committed to the repository.

## What is needed

Written permission from GSSTB (or the relevant board) naming: which books, storage on a server, display of extracts, offline copies on student devices, and whether the app may be public. A letter is needed; reading the website is not enough.
