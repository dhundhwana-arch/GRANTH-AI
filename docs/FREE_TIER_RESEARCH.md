# Free-tier research

Checked 2026-11-13 through web search. **Limits change often and several figures come from third-party
summaries, not from the provider's own page. Verify on the official link before relying on any number.**
No account was created and no key was used.

| Option | Free allowance (as found) | Card needed | Caveat | Official page |
|---|---|---|---|---|
| Google Gemini API (Flash / Flash-Lite) | roughly 5–15 requests/min, 500–1,500/day, per project | No | Free-tier data may be used to improve Google products; HTTP 429 over limit | ai.google.dev/gemini-api/docs/rate-limits |
| Hugging Face Inference Providers | small monthly credit (under $0.10 for free users) | No | Blocked when credit is used up | huggingface.co/docs/api-inference/en/pricing |
| Groq | about 30 requests/min, 1,000/day per model | No | Token-per-minute caps | console.groq.com/docs/rate-limits |
| OpenRouter free models | 20 requests/min, 50/day | No | 1,000/day after a one-time $10 purchase | openrouter.ai/docs |
| Local model (Ollama / llama.cpp server) | unlimited | No | Needs a capable machine; Gujarati quality unverified | — |
| GitHub Actions | free minutes for public repositories | No | Suitable for running the test suites | docs.github.com/actions |

## Decision

GRANTH-AI answers without any of them. The extractive engine plus the shared cache is the product; a generative
provider is an optional rewording layer that must pass verification. This keeps cost at zero, keeps student
questions on the server, and removes rate limits as a failure mode.

If generative rewording is wanted later: Gemini Flash first (largest free allowance), Groq second, both behind
`GRANTH_MAX_EXTERNAL_CALLS_PER_DAY` (default 50). The cache means a question is sent out at most once per corpus
version.

## Hosting

The app is one Python process and one SQLite file. Any small VM or free container tier that allows a persistent
disk will run it; static-only hosts (GitHub Pages) will not, because the API is required. No host was tested.
