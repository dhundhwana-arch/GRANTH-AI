# Gujarati language report (Phase 5, defect 4)

**Status: improved on the wordings that were targeted; ordinary vocabulary outside the word lists is still refused.** Frozen set: Gujarati 62/73, English 13/20, mixed 8/9, paraphrase category 21/26. No wrong answers in any language.

## What was built

- Question forms recognised by rule: કેવી રીતે, કઈ રીતે, શા માટે, શેના કારણે, ક્યાંથી, ક્યાં મળે છે, કયા અંગથી, શું કામ કરે છે, શેના વડે / દ્વારા, સમજાવો, વર્ણવો, વ્યાખ્યા આપો, કોને કહે છે.
- More verb endings and participle forms are reduced to their root. A word that looks like a participle is checked against the book's vocabulary before being treated as a verb, so nouns such as વનસ્પતિ are not misread.
- A filler noun beside a real topic word (ક્રિયા, પદાર્થ) is not required in the evidence.
- English and mixed questions: about 100 more glossary words and two more question patterns (naming, which).
- Word lists (`data/glossary/`) are retrieval aids only. They map a question word to a book word. They never add a sentence or a fact to an answer.
- Two fallbacks added during development gave wrong answers on regression sets (C21, C23, H33, G28). Both were narrowed before the engine was frozen, and tests now cover those cases.

## Embeddings

Not evaluated. No model weights are present and the sandbox cannot download any. Retrieval remains lexical: BM25, character trigram cosine and term coverage, with rule-based intent. No model download is needed to run the app.

## Evidence

| Check | Result |
|---|---|
| Paraphrase groups reach the same lead sentence (4 groups) | pass (unit tests) |
| Development set (seen) | 75/76 |
| Frozen set, paraphrase groups fully handled | 5 of 9 |
| Frozen set, English | 7/10 in the English category; 13/20 over all English-language questions |

Refused frozen wordings show the gap: દાખલ થાય, ઉત્પન્ન થાય, સુધારવા, વાપરવાથી, પરિણામ, and English "body", "added", "pure", "acidic".

## Status

| | |
|---|---|
| Implemented | question-form rules, verb forms, participle check, glossary additions |
| Automatically tested | yes |
| Manually tested | developer probes only |
| Not tested | dialect forms, student spelling habits, long multi-clause questions, embeddings |
| Blocked | embedding evaluation (no weights available) |
| Requires human review | Gujarati teacher review of the verb and synonym lists |
