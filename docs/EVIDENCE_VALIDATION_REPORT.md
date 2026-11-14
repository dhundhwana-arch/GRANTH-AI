# Evidence validation report (Phase 4, engine `extractive-1.3`)

Code: `granth/intent.py` (what is being asked) and `granth/validate.py` (does this sentence answer it). Tests: `tests/test_phase4.py`.

## What changed

Up to engine 1.2 an answer was "the best-matching passage, cut to length". A passage that shared words with the question could be shown even when it answered a different question, and extra sentences were added to fill the length.

In 1.3 every non-definition question goes through four steps:

1. **Intent** – the question is classified (see `SEMANTIC_ENGINE_REPORT.md`).
2. **Plan** – question words are split into *hard* terms (the concept: must be in the sentence), *soft* words (verbs and generic words: may be missing, but then the answer cannot be Verified) and *unknown* words (not in the book at all → refuse).
3. **Check, sentence by sentence** – a sentence is accepted only if it contains every hard term **and** carries the mark of the requested attribute:

| Asked for | The sentence must contain |
|---|---|
| unit (X નો એકમ) | "એકમ", with X as the thing whose unit it is |
| which quantity a unit belongs to (X શેનો એકમ) | "એકમ" with X in the unit position |
| either/or (A કે B) | exactly one of the two options |
| where / where from | a place-marked or source-marked word (…માં, …માંથી, દ્વારા) that is not the topic itself |
| why | a cause mark (કારણે, તેથી, …થી, માટે) |
| organ, instrument, use, types, how many, from–to | the corresponding word or a number |
| definition | the book's own "…ને X કહે છે" sentence for exactly X |

4. **Status** – *Verified* only if all hard terms matched exactly, no verb of the question is missing, nothing was matched through a synonym or spelling guess, the evidence is not a worked example and not found only through a section heading. Otherwise *Partial* with the reason written in Gujarati. If nothing passes: the fixed refusal sentence.

No sentence is added to fill space. A following sentence is included only when it begins with a pronoun that refers to the same topic.

## The eight examples from the brief (demo science book, 2026 edition)

| Question | Result | Status |
|---|---|---|
| ચૂનાનું પાણી ઍસિડિક છે કે બેઇઝિક? | "સાબુનું દ્રાવણ અને ચૂનાનું પાણી બેઇઝિક હોય છે." (only this) | Verified |
| માણસ શ્વાસ કયા અંગથી લે છે? | "મનુષ્યમાં શ્વસન માટેનું મુખ્ય અંગ ફેફસાં છે." | Partial (matched through synonyms) |
| ઍમ્પિયર શેનો એકમ છે? | "વિદ્યુતપ્રવાહનો એકમ ઍમ્પિયર છે." | Verified |
| ઝાડ પાણી ક્યાંથી મેળવે છે? | "વનસ્પતિ મૂળ દ્વારા જમીનમાંથી પાણીનું શોષણ કરે છે." | Partial (synonyms) |
| Why do we need lungs? | the lungs sentence | Partial (the book does not state a reason in those words) |
| Concave mirror નું focal length એટલે શું? | the book's definition of કેન્દ્રલંબાઈ (for spherical mirrors) | Partial (the book has no separate definition for a concave mirror) |
| અવરોધનો એકમ કયો છે? | "અવરોધનો એકમ ઓહ્મ છે." – no table, no extra sentence | Verified |
| અરીસો એટલે શું? | refused – the book defines ગોળીય / અંતર્ગોળ / બહિર્ગોળ અરીસો but not "અરીસો" | Insufficient |

These eight are development examples: the validator was built with them in view. They are regression tests, not evidence of accuracy.

## Known failures of the validator (from the frozen test, not fixed)

| Question | What happened | Why |
|---|---|---|
| ઑક્સિજન **ન હોય** ત્યારે થતા શ્વસનને શું કહે છે? | answered with the definition of **જારક** શ્વસન, labelled **Verified** | Negation is not understood. "ન હોય" is dropped as a function word, and the book's wording is "ગેરહાજરીમાં". This is a false Verified. |
| વૉટમીટર કેવી રીતે જોડાય છે? | answered with the voltmeter sentence (Partial) | "વૉટમીટર" is not in the book; the spelling matcher took it for "વોલ્ટમીટર". The answer says so, but it is still a wrong answer. |
| અંતર્ગોળ અરીસો વાહનોમાં શા માટે વપરાય છે? | showed mirror definitions (Partial) | False premise (the book says convex mirrors are used in vehicles) was not detected. |
| In which unit is potential difference measured? | showed the whole units table (Partial) | English phrasing "measured" was read as an instrument question; the table fallback then matched. |

So the rule "a related word is not evidence" holds for the cases that were designed for, and fails for negation, near-spelled unknown terms and some false premises. See `FROZEN_BENCHMARK_REPORT.md` for the numbers.
