# Phase 0 — Repository and Environment Baseline

Audit performed 2026-11-13 (UTC) before any change was made.

| Item | Finding |
|---|---|
| Remote | `origin` → `https://github.com/dhundhwana-arch/GRANTH-AI.git` |
| Branches | `main` (remote default), working branch `arena/b93bc898-granth-ai` |
| History | one commit: `5544487 Initial commit` |
| Tracked files | `LICENSE` (MIT), `README.md` (2 lines) — nothing else |
| Existing backend / frontend | none |
| Existing database schema | none |
| Existing AI integrations | none |
| Existing tests | none |
| PDF libraries pre-installed | none (`PyMuPDF` installed into a local `.venv` during this mission) |
| OCR binaries | no `tesseract` binary; OCR provided by `tesseract.js` (npm, WebAssembly) |
| Runtimes | Python 3.11.2 (SQLite 3.40.1), Node 22.22 |
| Workspace | writable |
| Network from the build sandbox | only github.com, registry.npmjs.org, pypi.org are reachable. `gsstb.gujarat.gov.in`, `ncert.nic.in`, `diksha.gov.in` and all AI-provider hosts are **not reachable** from here |

## Consequences that shaped the build

1. **Branch name.** The mission asked for `feature/granth-ai-textbook-engine`. The execution platform pins this session
   to the branch `arena/b93bc898-granth-ai`; creating or pushing another branch is not permitted here. All work is
   committed to that branch (never to `main`). It can be renamed/merged by the owner afterwards.
2. **No official textbook could be fetched or ingested.** The portals are unreachable from the sandbox, and independent
   of that their reuse permission is not established (GSSTB: UNKNOWN, NCERT: DENIED for software use). The vertical
   slice therefore runs on **original sample material written for this project** (CC BY 4.0), clearly labelled as
   *not* a GSEB/NCERT textbook.
3. **No provider API key exists**, so every external-provider integration is implemented but recorded as NOT TESTED
   against the live service.
4. Nothing pre-existing had to be preserved besides `LICENSE`, `README.md` and the Git history; none was removed.
