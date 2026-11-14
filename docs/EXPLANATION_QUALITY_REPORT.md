# Explanation quality report (Phase 5, defect 6)

**Status: the explanation is safe by construction but is mostly annotation, not simplification, and one wrong English gloss was found.** No teacher has reviewed it, and nothing here is teacher-approved.

## What the explanation does (`granth/explain.py`)

- Splits a definition into a naming line and a "who is called X" line, or splits at a semicolon.
- Adds an everyday Gujarati word in square brackets after a formal word.
- New in Phase 5: adds the English term in round brackets after a Gujarati technical term, from GRANTH-AI's own word list. The UI states that these words are not textbook text.
- Shows the meaning of hard words copied from the same book, and an example only if the book prints one in the same section.
- A check rejects any line that adds or drops a content word. New in Phase 5: it also rejects any change to a number.
- The quotation and the explanation are shown in separate blocks. Every line links to its source sentence and page.
- If no rule applies, the fallback text tells the student to read the original passage.

## Automatic checks (frozen set, 43 answers)

| Check | Result |
|---|---|
| Explanation lines produced | 40 of 43 (3 fallback) |
| Lines traceable to the quoted sentence | 40 of 40 |
| No new content words | 40 of 40 |
| Numbers and formula values unchanged | 40 of 40 |
| English terms shown | 40 of 43 |

In Phase 4 the fallback rate on its frozen set was 16 of 33. The drop to 3 of 43 comes almost entirely from the English brackets, not from new simplification rules.

## Developer reading of the 28 distinct explanations in the frozen run

This is the developer's own judgement, not a teacher review.

| Criterion | Finding |
|---|---|
| Factual consistency | 28 of 28: no fact added or changed in the Gujarati text |
| Meaning preservation | 27 of 28. In P132 the word અંગો ("parts" of a map) is glossed as "organ". The word list is not context-aware. |
| Readability | Not improved in most cases. Lines are longer than the source because of the brackets (for example 6 words become 15). |
| Terminology | English terms were correct in 27 of 28 |
| Traceability | 28 of 28 |

## Open defects

- Context-blind glosses: a word with two meanings gets the wrong English term (અંગ). The engine is frozen, so this is not fixed in 1.4.
- Only two real simplification rules exist. Long sentences without a definition pattern are shown unchanged with brackets.
- Bracket density is high and may make sentences harder to read.

## Status

| | |
|---|---|
| Implemented | split rules, everyday words, English terms, number check, fallback |
| Automatically tested | traceability, added words, numbers |
| Manually tested | developer reading of 28 explanations |
| Not tested | whether students understand better; readability with real learners |
| Blocked | none |
| Requires human review | teacher review of meaning, wording and both word lists |
