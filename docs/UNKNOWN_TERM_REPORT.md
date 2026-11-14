# Unknown and look-alike term report (Phase 5, defect 2)

**Status: fixed for the reproduced case; 13 of 14 frozen questions handled, 0 wrong.** The cost is that some real misspellings are now refused.

## Defect reproduced

Phase 4 frozen question Z41 asked about વૉટમીટર (wattmeter). The book only has વોલ્ટમીટર (voltmeter). The fuzzy matcher replaced one with the other and answered about the voltmeter.

## What was built (`granth/retrieval.py`, `granth/answer.py`, `web/js/app.js`)

- Spelling normalisation and word substitution are separate. Two words with the same folded form (vowel length, anusvara, nukta, virama variants) are the same word. Anything else is a guess.
- A guess is accepted only if every differing letter is a known Gujarati spelling confusion, the confidence is at least 0.75, the leftover is not itself a different book word, and the guessed word appears in the book next to another firm word from the question.
- If a guess fails, the student's word is kept as unknown. The nearest book word is offered as "did you mean", and is never used to answer.
- Every answer lists "your word → book word" with the kind of match. An answer that used a synonym or a guessed spelling is labelled Partial, never Verified.

## Evidence

| Check | Result |
|---|---|
| વૉટમીટર, wattmeter, invented words (ઝેનોમીટર, ક્વાર્ટોફિલ, zenometer) refused | pass (unit tests) |
| Spelling variants answered and shown (વિધુતપ્રવાહ, હરીતદ્રવ્ય, પ્રકાશસંશ્લેશણ) | pass |
| Transliteration (voltmeter) and genuine synonym (વીજપ્રવાહ) still answered, synonym labelled Partial | pass |
| Frozen set, unknown-term category | 13/14, 0 wrong |

Frozen failure: P030 "તટસ્થિકરણની પ્રક્રિયામાં કઈ ઊર્જા મુક્ત થાય છે?" was refused by the premise check, not by term matching.

Known cost: "જળચક્ઠ" (S17, a typo of જળચક્ર with an unusual letter swap) is refused. This is listed as an incorrect refusal in the regression results.

## Status

| | |
|---|---|
| Implemented | conservative matching, confidence, context check, did-you-mean, match display |
| Automatically tested | yes |
| Manually tested | developer probes only |
| Not tested | real student typing, phonetic keyboard errors, OCR-produced errors |
| Blocked | none |
| Requires human review | the confusable-letter table should be checked by a Gujarati language teacher |
