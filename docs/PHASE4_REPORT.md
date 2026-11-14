# GRANTH-AI Phase 4 report

Idea contributor: Bhaveshbhai Solanki · Founder & project developer: Divyesh Bambhaniya

Branch `arena/b93bc898-granth-ai`, starting from `3717484`. Engine `extractive-1.3`.

## Headline

On a frozen set of 70 new questions, run once: **55 handled correctly, 4 wrong answers, 1 wrong answer labelled Verified.** The previous engine on the same questions: 43 correct, 17 wrong, 8 wrong-and-Verified. Phase 4 made the engine wrong less often. It did not make it reliable enough for students: about one question in five is still mishandled, mostly by refusing a question the book can answer. Tested only on a 14-page demo book. **Not production ready.**

## Status by area

| Area | Status |
|---|---|
| A. Question understanding | **Implemented**: rule-based intent classification (19 intents), concept/attribute split, verb handling, larger glossaries. **Not done**: embedding-based retrieval (blocked – model download not possible here), real morphological analysis, negation. |
| B. Answer-evidence validation | **Implemented and tested automatically.** Per-sentence check of concept + attribute; no padding; Verified / Partial / Insufficient rules. Four failures found by the frozen test and left unfixed (listed in `EVIDENCE_VALIDATION_REPORT.md`). |
| C. Independent testing | **Done.** Development / validation / frozen sets; frozen set committed before its single run. Results in `FROZEN_BENCHMARK_REPORT.md`. |
| D. Explanation quality | **Small change only.** The answer card now says how the question was understood and which words were checked. The Phase 3 rule-based explanation is unchanged: on the frozen set, of 33 answers, 17 got simplified lines, 29 got glossary meanings, 2 got a book example, and 16 showed "a safe simplified explanation could not be made – read the source text". Short and detailed formats, step-by-step and formula modes exist from Phase 3 and were not improved. |
| E. Sources | **Blocked.** No licence could be read from this environment. Register rewritten; nothing new approved. |
| F. Real device | **Not tested.** Checklist prepared in `REAL_DEVICE_TEST_REPORT.md`; every row is "Not tested". |
| G. Security and privacy | Reviewed; admin-token expiry date added (`GRANTH_ADMIN_TOKEN_EXPIRES`). See `SECURITY_REPORT.md`. |
| H. Performance | Measured on the server only. See `PERFORMANCE_REPORT.md`. |
| I. Checkpoints | Commits `bcbc78d`, `b7bc20f`, `da67186`, `b76ae46` (frozen result) and the final commit; each pushed and verified; no force push; `main` untouched. |

## Tests run for this report

| Suite | Result |
|---|---|
| `pytest` | 173 passed |
| `npm test` | 18 passed |
| Browser end-to-end (headless Chromium) | 33 / 33 |
| Secret scan | clean |
| In-house benchmark (48) | 48 / 48 |
| Independent-format checks | 92 / 92 |
| Development sets | 184 / 186, 40 / 40, 35 / 35 |
| Validation set | 54 / 70 first run; 67 / 70 after tuning |
| Frozen set | 55 / 70, single run |

Behaviour changes that needed existing tests to be edited: answers are no longer padded with "key points", so two tests (one pytest, one e2e step) stopped requiring that section.

## What is still wrong

1. Negation ("ન હોય") is ignored – produced a false Verified.
2. An unknown word that looks like a known one can be answered for the wrong thing (વૉટમીટર → વોલ્ટમીટર).
3. Some false premises are answered with loosely related definitions.
4. New verb phrasings lead to refusal (11 of 49 answerable frozen questions).
5. English questions: 2 of 5.
6. A paraphrased edition-conflict question was refused instead of showing both editions.
7. Older: "વિદ્યુતપ્રવાહનું સૂત્ર લખો" returns Ohm's law; two development questions (P19, F07) refused.
