# False premise report (Phase 5, defect 3)

**Status: 14 of 14 frozen false-premise questions handled, 0 wrong.** The check is also the cause of 3 incorrect refusals on true questions in other categories.

## Defect reproduced

Phase 4 frozen question Z45 asked why something is so when the book says otherwise. The engine returned a loosely related definition.

## What was built (`granth/premise.py`, `granth/validate.py`)

Pipeline: question → concepts → assumptions → evidence → check assumptions → validate → answer or refuse.

- `bindings` finds pairs of question concepts that the question ties together.
- A sentence about a sibling concept (voltmeter when the question says ammeter) cannot support the answer.
- If no single book statement holds all the question's concepts, the engine refuses with reason `premise_not_supported`.
- It may then show the book sentences that hold all concepts but one, with page citations, under the label "this is not the answer to your question; check the question". These are quotations.
- The engine never writes a correction and never states that the premise is false. It only reports that the book does not support it.

## Evidence

| Check | Result |
|---|---|
| Gujarati and English false-premise questions refused with cited context | pass (unit tests) |
| True question on the same topic still answered | pass |
| Frozen set, false-premise category (12 false, 2 true) | 14/14 |
| Frozen set, true questions refused by this check | P006, P030, P061 |

## Status

| | |
|---|---|
| Implemented | assumption extraction, sibling check, cited context, refusal reason, UI block |
| Automatically tested | yes |
| Manually tested | developer probes only |
| Not tested | premises spread across several sentences, numeric premises beyond one value, real textbooks |
| Blocked | none |
| Requires human review | whether the "book says" context helps or confuses students |
