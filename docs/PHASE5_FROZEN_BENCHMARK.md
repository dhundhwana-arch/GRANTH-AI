# Phase 5 frozen benchmark

Result in one line: **83 of 102 handled as expected, 0 wrong answers, 19 incorrect refusals, 0 false "Verified" labels.** The engine no longer gives wrong answers on this set, but it refuses about one in four questions that the book can answer.

This is not independent validation. The developer of the engine wrote every question, and the corpus is a 14-page self-written demo, not a real textbook.

## Method

| Step | Evidence |
|---|---|
| Engine frozen as `extractive-1.4` | commit `d4f81cf` |
| Frozen set written from the book text, without asking the engine | `benchmarks/phase5/make_frozen_test.py` |
| Overlap with all earlier sets checked by program | first draft had 17 duplicates, all replaced; final file lists 0 |
| Set committed and pushed before the first run | commits `50c9f98`, then `c3ee08c` (one more duplicate replaced, still before any run) |
| Run once | `benchmarks/results/phase5/phase5_frozen_run1.json`, commit `fe309c2` |
| No engine change after the run | `git diff d4f81cf HEAD -- granth data web` is empty |

Hashes: set `141f26b986544973ef50414e4e9c846a37866deb7a048e17a6bba6c3e2f15de2`, result `35c1cb3e6a53283104fcfd0f467526768ea940d9edfa095debb7ff4aabb36a93`.

Reproduce: `PYTHONPATH=. python benchmarks/run_phase5.py --questions benchmarks/phase5/frozen_test.json --out /tmp/rerun.json`

The three benchmark groups are kept apart:

- A, regression: Phase 3 and Phase 4 sets, including the Phase 4 frozen set, which is now "seen" data. Results are in `benchmarks/results/phase5/regression_*_engine_1.4.json`.
- B, development: `benchmarks/phase5/dev.json` (76 questions), tuned on freely.
- C, frozen: `benchmarks/phase5/frozen_test.json` (102 questions), reported here.

## Results (C, frozen, single run)

| Measure | Result |
|---|---|
| Total questions | 102 |
| Expected: answer / refuse / either accepted / edition conflict | 59 / 34 / 4 / 5 |
| Correct answers (of the 59 that must be answered) | 42 |
| Wrong answers | 0 |
| Correct refusals (of the 34 that must be refused) | 34 |
| Incorrect refusals | 19 (17 answerable questions, 2 edition-conflict questions) |
| False "Verified" | 0 of 27 Verified answers |
| Lead citation correct | 43 of 43 answers |
| Edition conflict shown | 3 of 5 |

| Category | Questions | As expected | Wrong | Incorrect refusals |
|---|---|---|---|---|
| Negation | 14 | 9 | 0 | 5 |
| Unknown or look-alike term | 14 | 13 | 0 | 1 |
| False premise | 14 | 14 | 0 | 0 |
| Gujarati paraphrase | 26 | 21 | 0 | 5 |
| English | 10 | 7 | 0 | 3 |
| Mixed Gujarati-English | 6 | 5 | 0 | 1 |
| Edition conflict (synthetic editions) | 6 | 4 | 0 | 2 |
| Unsupported | 8 | 8 | 0 | 0 |
| Direct | 4 | 2 | 0 | 2 |

| Language | Questions | As expected |
|---|---|---|
| Gujarati | 73 | 62 |
| English | 20 | 13 |
| Mixed | 9 | 8 |

Confusion matrix (expected behaviour against actual behaviour):

| Expected | Answered correctly | Answered wrongly | Refused | Showed both editions |
|---|---|---|---|---|
| Answer (59) | 42 | 0 | 17 | 0 |
| Refuse (34) | 0 | 0 | 34 | 0 |
| Either (4) | 1 | 0 | 3 | 0 |
| Edition conflict (5) | 0 | 0 | 2 | 3 |

Paraphrase groups: 5 of 9 groups had every wording handled (yeast 1/3, CO2 entry 2/3, starch 3/3, lungs 3/3, soil 2/3, power 4/4, muscle pain 3/3, chlorophyll 2/2, groundwater 1/2).

## The 19 incorrect refusals

| Cause | Questions |
|---|---|
| A Gujarati word the engine does not know (દાખલ, ઉત્પન્ન, સુધારવા, વાપરવાથી, પરિણામ, લીધું, અભાવમાં, નામ) | P001, P003, P062, P064, P074, P085, P111 |
| An English word missing from the glossary (available, body, added, basic, pure, acidic, form, examples, Name) | P005, P007, P091, P094, P097, P104, P113 |
| The premise check was too strict on a true question | P006, P030, P061 |
| The validator found the topic but not the asked attribute | P130, P131 |

The common factor is vocabulary. The engine refuses when it meets a word it cannot map to the book, which is the intended safe behaviour, but the word lists are too small for ordinary student wording.

## Limits

- Developer-written questions only. No teacher or student wrote or reviewed any of them.
- About 470 earlier development questions already cover the same 45 or so facts, so the frozen questions are new wordings of facts the engine was tuned on.
- The Phase 4 frozen result (55/70) used a different set, so the two percentages cannot be compared directly. On the Phase 4 set, engine 1.4 scores 67/70 with 0 wrong, but that set was used during Phase 5 development and counts as regression data only.
- A fix for any of the 19 refusals needs a new engine version and a new frozen set. This result stays unchanged.
