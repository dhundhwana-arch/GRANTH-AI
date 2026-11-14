# Benchmark report

**Updated 2026-11-13 for engine `extractive-1.1`.** Two sets are reported. Raw output: `benchmarks/results/`.

## A. Independent test set — 83 of 92 checks pass, 9 fail

`benchmarks/independent/questions.json` + `benchmarks/run_independent.py`. The 62 questions were written the way a
student would ask about general syllabus topics, without reusing the demo books' wording; 30 further checks cover
editions, missing pages, unsupported scope, supplementary mode, cache, personal notes and offline packages.
Limit: the questions were written by the developer, not by a teacher, and the corpus is the small demo material.

| Category | Passed |
|---|---|
| Gujarati questions | 11 / 14 |
| English questions | 9 / 11 |
| Mixed Gujarati–English | 5 / 6 |
| Maths and formulas | 10 / 10 |
| Out-of-textbook (must refuse) | 8 / 8 |
| Incorrect or ambiguous (must refuse) | 7 / 7 |
| OCR / spelling errors in the question | 4 / 6 |
| Conflicting editions | 3 / 4 |
| Missing pages | 3 / 3 |
| Unsupported subject / board / standard / language | 5 / 5 |
| Supplementary mode separation | 5 / 5 |
| Cache correctness | 6 / 6 |
| Personal notes privacy | 5 / 5 |
| Offline packages | 2 / 2 |

Wrong answers given where a refusal was required: **0**. The 9 failures:

| Id | Question | What happened |
|---|---|---|
| GU03 | પાંદડાં લીલાં કેમ દેખાય છે? | Refused; the book explains it with other words |
| GU04 | માણસ શ્વાસ કયા અંગથી લે છે? | Refused (paraphrase) |
| GU11 | વરસાદનું પાણી કેવી રીતે સાચવી શકાય? | Refused (paraphrase) |
| EN08 | How do plants make their food? | Refused; words not in the term list |
| EN09 | Why do we need lungs? | Refused |
| MX04 | concave mirror નું focal length એટલે શું? | **Answered with the wrong definition** (concave mirror instead of focal length), marked Verified |
| OC05 | ઓમનો નિયમ લખો. | Refused; misspelling not matched |
| OC06 | પરાવતન એટલે શું? | Refused; misspelling not matched |
| CE01b | Paraphrased voltage question over two editions | Refused instead of showing the edition conflict (editions were not merged) |

One engine change was made because of this set: instruction words ("સ્પષ્ટ કરો", "ગણી બતાવો") were being treated as
topic words; after the fix two more questions pass. The other failures are left as they are.

## B. In-house 48-question set — 48 of 48 (was 46 of 48)

H1 and H2 now pass because of real engine changes (term list; formula lookup). **The gold answer of H4 was changed**:
"photosynthesis એટલે શું?" used to be expected to be refused; English terms are now supported, so it is expected to
be answered. Retrieval P@1 fell from 0.971 to 0.943 and R@3 from 1.0 to 0.971, MRR 0.957; citation correctness 1.0,
faithfulness 1.0, refusal accuracy 1.0, false refusals 0, median latency 1.6 ms, external API calls 0. This set
was written from the demo books, so it says little about real textbooks. The sections below are the original
report for engine 1.0.

Run 2026-11-13 with `python benchmarks/run_benchmarks.py --ocr`. Raw output: `benchmarks/results/`.
Corpus: the three demo books (14 pages). Questions and gold answers: `benchmarks/questions.json`, written by hand
by the developer of the engine — not an independent test set.

## Results by category

| | Category | Passed |
|---|---|---|
| A | Direct factual question | 4 / 4 |
| B | Definition | 4 / 4 |
| C | Explanation / multi-point | 4 / 4 |
| D | Formula | 4 / 4 |
| E | Table / difference | 4 / 4 |
| F | Worked example, numbers, units | 4 / 4 |
| G | Spelling, inflection, split compounds | 4 / 4 |
| H | Mixed Gujarati–English | **2 / 4** |
| I | Topic absent from the book (must refuse) | 4 / 4 |
| J | Content only in another book/chapter (must refuse) | 4 / 4 |
| K | Editions disagree | 4 / 4 |
| L | False premise / instruction injection (must refuse) | 4 / 4 |
| | **Total** | **46 / 48** |

A question passes only if status, cited page, verbatim faithfulness and required content are all correct (or, for
refusals, the exact refusal sentence with no citation).

## Metrics

| Metric | Value | Note |
|---|---|---|
| Precision@1 | 0.971 | top passage is on a gold page |
| Precision@3 | 0.716 | lower by construction when the gold page has fewer than 3 matching passages |
| Recall@3 | 1.000 | |
| MRR | 0.985 | |
| Citation correctness | 0.971 | one answer cited an extra, wrong page (H2) |
| Evidence coverage | 1.000 | every answer part is inside the shown evidence |
| Faithfulness | 1.000 | every answer part is verbatim in the selected book |
| Abstention accuracy | 1.000 | 17 of 17 |
| False refusals | 1 of 35 | H1 |
| Extraction accuracy (text route) | CER 0.000 | 14 pages |
| OCR CER (printed, rendered PDF) | mean 0.065, max 0.128 | 10 pages |
| Latency, uncached | median 0.7 ms, max 1.3 ms | in-process, 90 chunks |
| External API calls | 0 | |

## Failures

- **H1** “pH scale એટલે શું?” — refused; the English word “scale” is not in the book and there is no translation layer.
- **H2** “V = I × R કયો નિયમ છે?” — correct law returned, but an unrelated sentence about the laws of reflection
  was appended and its page cited.

## Changes made because of this benchmark

The first run scored 43 / 48. Three engine defects were fixed and are now covered by unit tests: a term containing
“તફાવત” was treated as a difference question (F1); “explain why Ohm's law is wrong” was answered (L4); and one gold
entry (K4) was widened to accept the worked-example page, which is a correct citation. H1 and H2 were left failing.

## Acceptance test (`benchmarks/results/acceptance.json`)

| Step | Result |
|---|---|
| Student A asks “પ્રકાશસંશ્લેષણ એટલે શું?” (Std 10 Science) | Answered, chapter “સજીવોમાં પોષણ”, page 1, verified, 10.7 ms |
| Student B asks the same | Served from cache, identical text, 0 external calls, 0.5 ms |
| Student C asks about volcanoes | Refused with the fixed sentence, no citation |
| All external APIs disconnected | “ઓહ્મનો નિયમ લખો” answered from local retrieval, pages 7–8, 0 external calls |

The same four steps also pass through the real web UI in the browser suite.

## How far these numbers generalise

Not far. The corpus is small, clean and written by the same person who wrote the questions. Treat the results as
proof that the pipeline and its safety rules work, not as a prediction of accuracy on real textbooks.
