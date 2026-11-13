# Benchmark report

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
