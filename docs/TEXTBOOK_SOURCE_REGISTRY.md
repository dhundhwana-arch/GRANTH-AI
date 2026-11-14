# Source registry

Last verified: 2026-11-13. Permission values: **APPROVED, RESTRICTED, UNKNOWN, DENIED**. Public availability is not
permission. Only APPROVED sources are ingested. The live registry is the database (`/api/catalog`, `/api/sources`);
each edition carries board, medium, standard, subject, title, edition and year, chapter list, source URL, owner,
licence, permission status, last verification date and ingestion status.

## Official portals investigated

| Source | Owner | Catalogue URL | Offers | Reachable | Permission | Ingested |
|---|---|---|---|---|---|---|
| GSSTB (Gujarat State Board of School Textbooks) — the publisher of GSEB textbooks | Government of Gujarat | https://gsstb.gujarat.gov.in/Home/gsstb/Std9to12 | Std 1–12, Gujarati and other mediums (not confirmed: page could not be opened) | **No** — failed from the build machine and from the page-fetch tool on 2026-11-13 | **UNKNOWN** — terms could not be read; earlier finding: all rights reserved, no open licence | 0 |
| NCERT | NCERT, Government of India | https://ncert.nic.in/textbook.php | Classes I–XII in Hindi, English, Urdu | Yes (page-fetch tool) | **DENIED** for this use — the page's copyright notice prohibits use "as a part of digital content packages or software", hosting and redistribution; even links need written permission | 0 |
| DIKSHA | NCERT / Ministry of Education | https://diksha.gov.in/ | Content from many boards; licence set per item | Yes; only the first part of the Terms of Use (updated 07-07-2025) was read | **UNKNOWN** — content-licence clause not yet read; no item inspected | 0 |
| Gujarati Wikipedia | Wikimedia contributors | https://gu.wikipedia.org/ | Encyclopaedia articles, e.g. પ્રકાશસંશ્લેષણ, ભારતનું બંધારણ | Yes | Text is under CC BY-SA (attribution + share-alike). Candidate supplementary source; **not ingested**, and to be re-checked against the licence page before any use | 0 |

No catalogue metadata of real textbooks was collected: the discovery command (`python -m granth discover`) still
cannot reach the portals from the build machine, and nothing was scraped through other routes.

## Sources actually in the app

| Slug | Role | Board label | Medium | Std | Subject | Edition / year | Chapters | Owner | Licence | Permission | Ingestion |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `granth_vigyan_10_2026` | textbook | GRANTH-AI Sample Board (demo – NOT GSEB) | Gujarati | 10 | વિજ્ઞાન | 2026 / 2026-27 | 5 (10 pages) | GRANTH-AI project | CC BY 4.0 | APPROVED | ingested |
| `granth_vigyan_10_2027` | textbook | same | Gujarati | 10 | વિજ્ઞાન | 2027 (230 V instead of 220 V) | 1 (2 pages) | GRANTH-AI project | CC BY 4.0 | APPROVED | ingested |
| `granth_samajik_10_2026` | textbook | same | Gujarati | 10 | સામાજિક વિજ્ઞાન | 2026 / 2026-27 | 2 (2 pages) | GRANTH-AI project | CC BY 4.0 | APPROVED | ingested |
| `granth_purak_nondh_2026` | supplementary (opt-in) | GRANTH-AI Supplementary Source (demo – NOT a textbook) | Gujarati | — | પૂરક અભ્યાસ નોંધ | 2026 | 4 (4 pages) | GRANTH-AI project | CC BY 4.0 | APPROVED | ingested |
| personal notes | personal | "મારી નોંધ (ખાનગી)" | — | — | — | — | — | the student | user-provided, private | not public | per student |

These are demonstration material written for the project. They are **not** GSEB or NCERT content, so **no real
board, standard or subject is supported yet.** The supplementary notes have not been reviewed by a teacher.

## Adding a real source later

1. Obtain written permission and record it (see the permission register).
2. Write a `book.json` (board, medium, standard, subject, title, edition, year, source URL, owner, licence,
   `permission_status: APPROVED`, `role`) and ingest the file. PDF ingests wait for admin review.
3. Other boards, standards and languages need no code change; a non-Gujarati source also needs stop-words and a term
   list for that language.

## Phase 3 re-check (2026-11-13)

| Source | Checked | Result | Status |
|---|---|---|---|
| GSSTB portal `gsstb.gujarat.gov.in` | Fetch attempted again | Unreachable from this environment | UNKNOWN (unchanged) |
| DIKSHA Terms of Use (last updated 07-07-2025) | First 3 of 12 parts read; the Content Policy part was not reached | For "learning and educational purposes"; users may access and share content; modifying or adapting is allowed only as "expressly permitted by the license applicable to such Content". The licence is therefore per item. No item licence for a Gujarat textbook was inspected | UNKNOWN (unchanged) |
| NCERT | Not re-read | Earlier finding stands | DENIED (unchanged) |
| Demo books and supplementary notes | — | Self-authored, CC BY 4.0, labelled demo | APPROVED (unchanged) |

No status was changed in Phase 3 and no third-party content was added. No real board, standard or subject is supported.
