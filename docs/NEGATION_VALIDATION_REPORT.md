# Negation validation report (Phase 5, defect 1)

**Status: the reproduced defect is fixed; negation in less common wording is often refused.** Frozen set: 9 of 14 negation questions handled, 0 wrong, 5 incorrect refusals.

## Defect reproduced

Phase 4 frozen question Z17, "ઑક્સિજન ન હોય ત્યારે થતા શ્વસનને શું કહે છે?", was answered with the sentence about aerobic respiration (ઑક્સિજનની હાજરીમાં). Negation words were treated as stop words and dropped.

## What was built (`granth/polarity.py`, `granth/validate.py`, `granth/lang.py`)

- `negated()` reads the raw question or sentence and finds the content word each negation applies to. It knows વગર, વિના, સિવાય, ગેરહાજર, અભાવ, અછત, રહિત, and ન / નથી / નહીં after a word.
- A term the question negates must be negated in the evidence sentence, and a term the question does not negate must not be negated there. Otherwise the sentence is rejected.
- If no sentence has the right polarity, the answer is refused with reason `polarity_not_supported`. A polarity conflict can never be labelled Verified because the sentence is rejected before labelling.
- English "without X", "no X", "not X", "absence of X" are rewritten to "X વગર" before retrieval.
- Yes/no questions are exempt, because a negated sentence is a valid answer to them.
- No list of questions or topics is used. The rules mention only negation words.

## Evidence

| Check | Result |
|---|---|
| Unit tests, negation in 7 positions and wordings, Gujarati and English | pass (`tests/test_phase5.py`) |
| Positive question never gets the negated fact | pass |
| Negation the book never states is refused | pass |
| Development set (seen), negation category | all pass |
| Frozen set, negation category | 9/14, 0 wrong |

Frozen refusals: P001 (હાજર ન હોય તેવા ... નામ), P003 (અભાવમાં ... નામ અપાયું), P005 (not available), P006 (does not need), P007 (Name the ... when oxygen is present). In each case the polarity logic did not run because another word in the question was unknown, or the premise check rejected it.

## Status

| | |
|---|---|
| Implemented | polarity detection, validation, refusal reason, English rewrite |
| Automatically tested | yes, unit tests and benchmarks above |
| Manually tested | developer probes only |
| Not tested | double negation, negation across two sentences, real textbook text |
| Blocked | none |
| Requires human review | a Gujarati teacher should check the negation word list |
