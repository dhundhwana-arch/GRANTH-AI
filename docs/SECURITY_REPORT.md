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
