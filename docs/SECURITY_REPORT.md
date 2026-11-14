# Security report

## In place and tested

| Control | Detail |
|---|---|
| Secrets | `.env` is git-ignored and chmod 600; `.env.example` has empty placeholders; keys are masked in any output; no key was ever created or stored |
| Private files | `PRIVATE_API_REGISTRY.md`, `PRIVATE_API_SETUP.md`, `private/`, `*.pdf`, databases and downloads are git-ignored |
| SQL injection | All queries are parameterised; an injection string is treated as a question |
| Input limits | Request body ≤ 64 KB (413), question ≤ 500 characters (400), marks 1–5, known modes only |
| Path traversal | Static files are resolved inside `web/` only |
| Headers | CSP (self only, WASM allowed for OCR), `X-Content-Type-Options`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy` |
| Rate limit | 240 API requests per minute per IP |
| Admin | `X-Admin-Token` required; wrong token 401; admin disabled (403) when no token is configured |
| Content gating | Unauthorized, pending or rejected editions return 404 on every student route |
| XSS | All server text is HTML-escaped in the UI; no inline scripts |
| Student privacy | No accounts, no personal data; a random session id links history; photos are OCR'd on the device |
| Prompt injection | Extractive engine ignores instructions in questions; benchmark category L passes |

## Open risks

- **No HTTPS in the built-in server.** Deploy behind a TLS proxy. Service worker, microphone and camera need HTTPS
  outside localhost.
- `X-Frame-Options: SAMEORIGIN` blocks embedding in other sites. `GRANTH_ALLOW_FRAMING=1` removes it for iframe-based previews; do not set it in production.
- Rate limiting is in memory, per process, and trusts the socket address; behind a proxy it needs the forwarded IP.
- A single shared admin token; no user accounts, roles or audit log.
- Session ids are unauthenticated; anyone who knows one can read that history.
- Browser speech recognition may send audio to the browser vendor's service. The UI says so; there is no offline
  alternative yet.
- No dependency audit or penetration test has been done.

## Added in version 0.2

- **Personal notes.** Stored per session id (a random UUID kept in the browser). Not listed in the catalogue, not
  served to other sessions (404), excluded from the shared cache and from offline packages, deleted completely on
  request. Rights confirmation is enforced on the server. Limits: 60,000 characters, 5 note sets per session.
  **Risk:** the session id is the only key. There are no accounts; anyone who obtains a student's session id can
  read that student's notes, history and saved answers. Notes are stored unencrypted in the server database.
  Clearing browser data loses access to them (they remain on the server until deleted by an operator).
- **Saved answers.** A session can save only answers it asked itself (404 otherwise).
- **Supplementary source** cannot be reached through normal scope parameters, only by explicit selection, and a
  textbook edition id passed as supplementary is ignored.
- **Term list** (`data/glossary/en_gu_terms.json`) is static project data; no translation service is called.
- No new external network calls, no new secrets. `.env`, private registry files and PDFs remain ignored by git.
- Still open from before: no HTTPS termination, rate limit by direct IP only, single admin token, no audit log.

## Phase 3 release audit (2026-11-13)

| Area | Finding | Action | Test |
|---|---|---|---|
| Admin token | Any non-empty value was accepted, including `dev-admin-token` used in development | Well-known or short tokens (under 24 characters, or fewer than 8 distinct characters) are refused unless `GRANTH_ALLOW_WEAK_ADMIN_TOKEN=1`; 10 wrong tokens from one address lock the admin API for 5 minutes | `test_admin_refuses_development_token_unless_explicitly_allowed`, `test_repeated_wrong_admin_tokens_are_throttled` |
| Session isolation | History, saved items and notes are keyed by a session id held in the browser | Id is now always generated with a cryptographic random source; no change to the model | `test_delete_session_data_erases_one_session_only` |
| Private notes | Owner-only, never cached, never in the catalogue or offline packages | No change; deletion verified at database level | `test_deleted_personal_text_is_gone_from_the_database` |
| Cache separation | Key includes engine version, corpus versions, edition ids, chapter, mode, marks; personal sources bypass the cache | Engine version bumped to 1.2, so no 1.1 answer is served | existing cache tests |
| API credentials | Read from environment only; `.env` ignored by Git; none configured | Secret scanner added | `test_no_secrets_in_tracked_files` |
| Migrations | 001 and 002 apply on an empty database; no schema change in Phase 3 | None needed | existing migration tests |
| User data deletion | Only personal notes could be deleted | `DELETE /api/session-data?session=…` erases questions, answers, evidence log, feedback, saved answers, saved words and notes of that session; button on the history page | API and browser tests |
| Error logging | Request log omits query strings and bodies; 500 responses carry no internals | No change | `test_errors_do_not_leak_internals_and_logs_hide_queries` |
| Secret scanning | No tool existed | `scripts/secret_scan.py --history`: 109 tracked files and all commits clean | same test |

Still open:

- There are no accounts. Anyone who obtains a session id can read and erase that session's data.
- No HTTPS termination in the app itself (must come from the host). The general rate limit is per address, in memory.
- The admin lockout is per address and in memory; it resets on restart and is weak behind a shared proxy.
- Answers saved for offline use stay on the device until the user clears site data.
- The preview server of this work session runs without an admin token, so its admin API is disabled. `GRANTH_ALLOW_WEAK_ADMIN_TOKEN=1` must never be set on a public deployment.
- The shared answer cache and usage counters hold no session id and are not touched by "erase my data".

## Phase 4 review (2026-11-13)

| Item | State | Evidence |
|---|---|---|
| Session id | Random id created in the browser, at least 8 characters required by the API; it is an identifier, not a login. Anyone who obtains it can read that session's history. | `tests/test_security_phase3.py` |
| Notes isolation | Personal notes are searchable only by the session that added them. | pytest (isolation test) |
| Saved answers, history deletion | `DELETE /api/session-data` removes history, saved answers, saved words and notes for the session. Known weakness unchanged: note deletion matches with `answer_json LIKE`. | pytest + e2e step "erase all my data" |
| Admin access | Disabled unless `GRANTH_ADMIN_TOKEN` is set; weak or well-known values refused; constant-time compare; 10 wrong tokens in 5 minutes per IP → 429. | pytest |
| Token expiry / rotation | **New:** `GRANTH_ADMIN_TOKEN_EXPIRES=YYYY-MM-DD`; after that date, or if the value is not a date, admin access is refused. Rotation is still manual: set a new token and date, restart. No per-user tokens. | `tests/test_phase4.py` (2 tests) |
| Cache separation | Answer cache key = question + scope + engine version; holds no session id and no personal notes. | pytest |
| Local database | One SQLite file under `var/`, ignored by git, not encrypted. Protect it with file permissions and disk encryption on the host. | – |
| Error logs | Request log drops query strings; stack traces are not sent to clients. | pytest |
| Secret scan | `scripts/secret_scan.py` clean on the working tree. | run before each commit |
| Public deployment | The live preview runs **without** an admin token, so the admin API is disabled there. No HTTPS termination in the app itself – put it behind a reverse proxy. | – |

Not done: user accounts, automatic token rotation, database encryption, penetration test, review by a second person.

## Phase 5 review (2026-11-14)

No new vulnerability was found in the application code. No penetration test and no second-person review has been done, so this is a self-review.

Phase 5 changed only the answer engine, word lists, the result page and tests. It added no route, no stored field and no dependency.

| Area | State | Evidence |
|---|---|---|
| Token expiry | `GRANTH_ADMIN_TOKEN_EXPIRES` date; expired or unreadable date refuses admin access | pytest (Phase 4 tests, still passing) |
| Token rotation | Manual: set a new token and date, restart. No automatic rotation, no per-user tokens. | not automated |
| Authentication | Students have no accounts. Admin uses one shared token; weak or well-known values refused; 10 wrong tokens in 5 minutes gives 429. | pytest |
| Session isolation | Notes and history are tied to a random session id. The id is not a login: anyone who obtains it can read that history. | pytest |
| Data deletion | `DELETE /api/session-data` removes history, saved answers, saved words and notes for the session | pytest and browser test |
| Uploads | Photos are read by OCR in the browser and are not uploaded. Request bodies are limited to 64 KB, questions to 500 characters. | pytest |
| File validation | PDF ingestion is a command-line step for the operator, with a permission status required per edition. There is no public upload route for books. | code review |
| Logging | Request log drops query strings. Questions are stored in the local database for history until the session is erased. | pytest |
| Error handling | Clients get a short message; stack traces are not sent | pytest |
| Secrets | `scripts/secret_scan.py` on the working tree and on all 35 commits: CLEAN | run 2026-11-14 |
| Rate limiting | 240 requests per minute per IP. In the Phase 5 load run, 89 of 256 requests at 32 parallel clients from one address got 429, as designed. | `benchmarks/results/phase5/phase5_performance.json` |
| External AI | Off by default (`GRANTH_GENERATIVE=off`). Every benchmark answer in Phase 5 records 0 external calls. No student question or note leaves the server. | benchmark output |
| New Phase 5 fields | `term_matches`, `did_you_mean`, `premise` contain only words from the question and quoted book text; all are HTML-escaped in the page | code review, browser test passes |

Dependency audit, first run in this project:

| Tool | Result |
|---|---|
| `npm audit` (all packages, including test-only ones) | 0 vulnerabilities |
| `pip-audit` on the virtual environment | 21 advisories, all in `pip 23.0.1` and `setuptools 66.1.1`, the packaging tools that come with the system Python. None in PyMuPDF, pytest, fonttools or brotli. |

Action from the audit: upgrade `pip` and `setuptools` in any deployment environment. They are not imported by the running app.

Open risks, unchanged: no HTTPS in the built-in server, one shared admin token, unauthenticated session ids, unencrypted SQLite file, in-memory rate limiter that trusts the socket address, browser speech recognition may send audio to the browser vendor.

| | |
|---|---|
| Implemented | controls in the table |
| Automatically tested | token, session isolation, deletion, limits, error handling, secret scan, dependency audits |
| Manually tested | none in Phase 5 |
| Not tested | penetration test, deployment behind a proxy, multi-user abuse |
| Blocked | none |
| Requires human review | second-person security review before any real student use |
