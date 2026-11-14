# GRANTH-AI Phase 5 report

IDEA CONTRIBUTOR: BHAVESHBHAI SOLANKI

FOUNDER & PROJECT DEVELOPER: DIVYESH BAMBHANIYA

Date: 2026-11-14. Branch: `arena/b93bc898-granth-ai`. Engine: `extractive-1.4`.

## Summary

Engine 1.4 gave **no wrong answer and no false "Verified" label** on a frozen set of 102 new questions, and refused 19 questions it should have answered. Phase 4's engine gave 4 wrong answers on its frozen set of 70. The engine has moved from sometimes wrong to often over-cautious.

**GRANTH-AI is not production-ready.** The questions were written by the developer, the corpus is a 14-page self-written demo, no teacher has reviewed anything, no real device has been used, and no publisher permission exists.

## Baseline preservation

| Item | State |
|---|---|
| Phase 4 final commit | `48bf73e2346374a1a0081c0c95e6aa021bc6ab2a`, untouched |
| Phase 4 frozen set and result files | unchanged; hashes recorded in `docs/PHASE4_BASELINE.md` |
| Phase 4 result reproduced on the Phase 4 engine | identical, 55/70 (`benchmarks/phase5/reproduce_phase4_baseline.sh`), re-run after the engine freeze |
| Phase 5 material | stored separately in `benchmarks/phase5/` and `benchmarks/results/phase5/` |
| Git | no reset, no force push, no history rewrite; `main` not modified |

One Phase 3 test was edited: `tests/test_phase3.py` compared an explanation line exactly, and the line now carries an English term in brackets. The test compares the line with brackets removed. No Phase 4 test, question, expected answer, scoring rule or result was changed.

## Defects and outcome

| # | Defect | Reproduced on | Outcome in engine 1.4 | Frozen result |
|---|---|---|---|---|
| 1 | Negation ignored | Z17 answered with the opposite fact | Polarity is checked; Z17 now answers અજારક શ્વસન | 9/14, 0 wrong, 5 refused |
| 2 | Look-alike word substituted | Z41 વૉટમીટર answered as વોલ્ટમીટર | Refused, with "did you mean"; matched book word is shown | 13/14, 0 wrong |
| 3 | False premise answered | Z45 got a loosely related definition | Refused; book sentences shown as context only | 14/14 |
| 4 | Gujarati wordings refused | 11 refusals in the Phase 4 frozen set | 8 of those 11 now answered; new wordings still refused often | paraphrase 21/26, English 7/10, mixed 5/6 |
| 5 | Edition conflict missed | 0 of 1 in the Phase 4 frozen set | Both editions shown with citations when the words are known | 3/5, 2 refused |
| 6 | Explanations mostly fallback | 16 of 33 fallback | English terms in brackets, number check; fallback 3 of 43. One wrong gloss found; readability not improved | see explanation report |

Partly fixed means: defects 1, 4, 5 and 6 still fail on some frozen questions. Details are in the six defect reports.

## Tests

| Suite | Result |
|---|---|
| pytest | 216 passed, 0 failed (173 earlier tests and 43 new in `tests/test_phase5.py`) |
| Browser-module tests (`npm test`) | 18 passed, 0 failed |
| Headless browser run | 33 of 33 steps |
| Secret scan, tree and history | CLEAN |
| `npm audit` | 0 vulnerabilities |
| `pip-audit` | 21 advisories in `pip` and `setuptools` only |

## Benchmarks

Development and frozen results are kept apart.

| Set | Role | Engine 1.4 | Wrong | False Verified |
|---|---|---|---|---|
| Phase 3 questions (186) | regression | 184 | 0 | 0 |
| Phase 3 held-out (40) | regression | 40 | 0 | 0 |
| Phase 3 held-out 2 (35) | regression | 35 | 0 | 0 |
| Phase 4 validation (70) | regression | 67 | 0 | 0 |
| Phase 4 frozen set (70), now seen | regression | 67 | 0 | 0 |
| Phase 5 development set (76) | development | 75 | 0 | 0 |
| **Phase 5 frozen set (102)** | **frozen, single run** | **83** | **0** | **0 of 27** |

Frozen set detail: 42 of 59 answerable questions answered correctly, 34 of 34 refusals correct, 19 incorrect refusals, lead citation correct in 43 of 43 answers, Gujarati 62/73, English 13/20, mixed 8/9. Method, tables and the list of failures: `docs/PHASE5_FROZEN_BENCHMARK.md`.

During development two fallbacks produced 4 wrong answers on regression sets. They were narrowed before the freeze, and tests cover them.

## Other work

| Area | State | Document |
|---|---|---|
| Teacher review | Template, CSV sheet and converter ready. **No teacher has reviewed anything.** | `TEACHER_REVIEW_TEMPLATE.md` |
| Student feedback | Form ready, no personal data. **Not used.** | `STUDENT_FEEDBACK_TEMPLATE.md` |
| Android | 30-minute procedure, 15 areas. **NOT TESTED on any device.** | `REAL_DEVICE_TEST_REPORT.md` |
| Security | Self-review; first dependency audit; no new finding in app code; open risks unchanged | `SECURITY_REPORT.md` |
| Permissions | No status changed: GSSTB UNKNOWN, DIKSHA UNKNOWN, NCERT DENIED, demo APPROVED. Request template written, not sent. | `SOURCE_PERMISSION_REGISTER.md` |
| Performance | Server only: question median 2.7 ms; 8 parallel clients fine; rate limit engages at 32 from one address. No Android figures. | `PERFORMANCE_REPORT.md` |
| Embeddings | Not evaluated; no weights available. Not required by the app. | `GUJARATI_LANGUAGE_REPORT.md` |
| External AI | Off by default; 0 external calls in every run | `SECURITY_REPORT.md` |

## Status by kind of evidence

| | |
|---|---|
| Implemented | polarity validation, conservative term matching, premise check, Gujarati question forms, per-edition comparison, explanation brackets and number check, Phase 5 runner, templates |
| Automatically tested | all of the above, on the demo corpus with developer-written questions |
| Manually tested | developer reading of 28 explanations; developer probes |
| Not tested | physical devices, real textbooks, teacher-written questions, students, embeddings |
| Blocked | publisher sites and model weights unreachable from the build environment; no device |
| Requires external permission or human review | publisher permission, teacher review, device tester, second-person security review |

## Remaining defects

Listed with evidence in `docs/NEXT_STEPS.md`. The main ones: refusals caused by everyday words outside the word lists, the premise check refusing some true questions, a context-blind English gloss, and explanations that annotate more than they simplify.

## Commits

| Commit | Content |
|---|---|
| `3831b65` | Phase 4 baseline preserved |
| `2c3f130` | negation, unknown terms, false premise |
| `4cee29c` | Gujarati question understanding, runner, development set |
| `d4f81cf` | explanations, Phase 5 tests, engine frozen as 1.4 |
| `50c9f98`, `c3ee08c` | frozen set committed before its run |
| `fe309c2` | frozen run result |
| final commit | documentation, templates, performance and regression results |
