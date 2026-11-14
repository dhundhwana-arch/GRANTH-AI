# Edition conflict report (Phase 5, defect 5)

**Status: works when the question uses known words; 3 of 5 frozen conflict questions shown, 2 refused, none answered with a single winner.**

The two editions are self-written demo fixtures (synthetic). The 2026 edition says 220 volts for the household supply and the 2027 edition says 230 volts. No real textbook editions were compared.

## Behaviour

- Each selected edition is searched and validated on its own.
- If the validated answers differ, the result status is `edition_conflict`. Both answers are shown, each with its edition label and page citation.
- The engine does not choose between them and the result is not labelled Verified.
- If both editions give the same answer, one answer is shown.

## Evidence

| Check | Result |
|---|---|
| Exact wording, Gujarati paraphrase, changed word order, English, mixed | pass (unit tests, 5 wordings) |
| Development set (seen) | 6 of 7; D105 "ઘરમાં વપરાતી વીજળી ..." refused |
| Frozen set | 3 of 5 shown; P111 (unknown word લીધું) and P113 (unknown word "examples") refused |
| Same-answer control question (P115) | answered once, correctly |

Phase 4 frozen result for this category was 0 of 1.

## Status

| | |
|---|---|
| Implemented | per-edition search, comparison, both shown with citations |
| Automatically tested | yes, on synthetic editions |
| Manually tested | developer probes only; the browser test does not have a step for the conflict display |
| Not tested | real editions, more than two editions, conflicts in tables or formulas |
| Blocked | real edition comparison (no permitted real textbooks) |
| Requires external permission | publisher permission for any real edition |
