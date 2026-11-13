# Textbook source registry

Machine-readable copy: `data/registry/discovered.json` (written by `python -m granth discover` on 2026-11-13).

| Source | Catalogue URL | Reachable from build machine | Permission | Books ingested |
|---|---|---|---|---|
| Gujarat State Board of School Textbooks (GSSTB) | https://gsstb.gujarat.gov.in/Home/gsstb/Std9to12 | No (TLS connection closed) | UNKNOWN | 0 |
| NCERT | https://ncert.nic.in/textbook.php | No (TLS connection closed) | PROHIBITED without written permission | 0 |
| DIKSHA | https://diksha.gov.in/ | No | UNKNOWN (licence is per item) | 0 |
| GRANTH-AI Sample Board (demo – NOT GSEB) | `data/sample/` in this repository | n/a | AUTHORIZED (CC BY 4.0, self-written) | 3 editions |

## What the discovery engine does

- Reads `robots.txt` first and obeys it; identifies itself with a project user agent.
- Fetches catalogue pages only, extracts title / standard / medium / subject / PDF link as **metadata**.
- Never downloads a PDF. Each discovered book inherits the permission status of its source.
- Priority order: Gujarati medium Std 9, 10, 11, 12, then Std 1–8.

## What actually happened

The build sandbox could reach only GitHub, npm and PyPI. All three portals failed at the TLS handshake, so
**no catalogue page was fetched and no real book metadata was collected**. The parser is tested against a synthetic
HTML fixture (`tests/test_discovery.py`), not against the live portals. Running `python -m granth discover` from a
normal internet connection is the first open task.

## Bundled demo books

| Slug | Subject | Std | Edition | Pages | Chapters | Chunks |
|---|---|---|---|---|---|---|
| `granth_vigyan_10_2026` | વિજ્ઞાન | 10 | 2026 | 10 | 5 | 64 |
| `granth_vigyan_10_2027` | વિજ્ઞાન | 10 | 2027 (differs: 230 V instead of 220 V) | 2 | 1 | 15 |
| `granth_samajik_10_2026` | સામાજિક વિજ્ઞાન | 10 | 2026 | 2 | 2 | 11 |
