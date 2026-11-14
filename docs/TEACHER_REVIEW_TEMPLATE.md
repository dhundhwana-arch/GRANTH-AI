# Teacher review workflow and template

**Status: no teacher has reviewed GRANTH-AI. No row below has been filled in by a teacher.** Every benchmark question so far was written by the developer.

## Why

The developer wrote both the engine and its tests. A teacher who has not seen the engine's behaviour gives the first independent check.

## Workflow

1. The teacher receives only the textbook (today: the demo books in `data/sample/`) and the blank sheet `docs/templates/teacher_questions_template.csv`. They do not see earlier questions or results.
2. The teacher writes about 100 questions in their own words, as students would ask them. Suggested mix: 60 the book can answer, 25 it cannot, 15 tricky (negation, wrong assumption, look-alike word, two editions).
3. The sheet is saved under `benchmarks/teacher/` and committed before the engine sees it.
4. Convert and run once:
   `python benchmarks/phase5/teacher_csv_to_set.py benchmarks/teacher/<file>.csv benchmarks/teacher/<file>.json`
   `PYTHONPATH=. python benchmarks/run_phase5.py --questions benchmarks/teacher/<file>.json --out benchmarks/results/teacher/<file>_run1.json`
5. The teacher reads every answer and fills in the review columns. The program's own judgement is not enough.
6. Results are reported separately from developer-written sets. Any engine change after this needs a new teacher set.

## Columns the teacher writes

| Column | Meaning |
|---|---|
| question | The question as a student would ask it |
| language | gu, en or mixed |
| standard | Class, for example 10 |
| subject | For example વિજ્ઞાન |
| chapter | Chapter number or name |
| expected_answer | The answer in the teacher's words, or the key phrase from the book |
| source_page | Page number in the book; empty if the book has no answer |
| supported | yes or no: does the book answer this? |
| expected_behaviour | answer, refuse, correct_premise or show_both_editions |
| comments | Anything the developer should know |

## Columns the teacher fills in after the run

| Column | Values |
|---|---|
| answer_correct | yes / partly / no |
| citation_correct | yes / no |
| label_appropriate | yes / no (was Verified or Partial fair?) |
| explanation_faithful | yes / no / not shown |
| explanation_easier | yes / same / harder |
| harmful_or_misleading | yes / no |
| reviewer_comment | free text |

The reviewer may give initials or stay anonymous. No other personal data is needed.

## Status

| | |
|---|---|
| Implemented | template, converter script, workflow |
| Automatically tested | the converter was run on the template (example row skipped) and on one developer-written test row, which is not a teacher question |
| Manually tested | none |
| Not tested | the whole workflow with a real teacher |
| Blocked | no teacher available to the developer |
| Requires human review | a Gujarati-medium teacher |
