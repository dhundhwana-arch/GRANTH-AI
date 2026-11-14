# Answer engine report — `extractive-1.1`

Code: `granth/answer.py`, `granth/lang.py`, `granth/retrieval.py`. Measured results: `docs/BENCHMARK_REPORT.md`.

## Pipeline (one engine for keyboard, voice, camera, exam mode)

| Step | What happens | Where |
|---|---|---|
| 1 Language detection | By script: Gujarati, English, mixed, Hindi, other | `lang.detect_language` |
| 2 Scope | Board / medium / standard / subject / book / edition / chapter → approved textbook editions only | `answer.resolve_scope` |
| 3 Normalisation | English and mixed questions are turned into a Gujarati working question with a curated 95-term list; Gujarati is normalised and stemmed | `lang.to_gujarati_query`, `gujarati.py` |
| 4 Retrieval | BM25 + character trigrams + term coverage over the selected editions | `retrieval.search` |
| 5 Evidence check | Enough question terms must be found; false premises and one-word ambiguous questions are refused | `check_sufficiency`, `_ambiguity` |
| 6 Answer building | Sentences, tables, formulas or a worked example are selected by question type | `_compose`, `_formula_lookup` |
| 7 Sentence-level validation | Every sentence is re-read from the database and must be word-for-word in an approved, in-scope edition; every citation must exist | `verify_extractive` |
| 8 Presentation | Question, simple answer, key points, source, reliability status | `_structure` |
| 9 Cache | Verified answers only; key = question + scope + corpus versions + engine version | `cache.py` |

## What "simple answer" means here

- **સરળ જવાબ** is the one or two sentences of the source that answer the question most directly. **મુખ્ય મુદ્દા** are
  the remaining supporting sentences. Both are the source's own words and are labelled "સીધું અવતરણ".
- Help for understanding is added beside the answer, each with its own label: meanings from the book's own
  શબ્દાર્થ list, and English technical terms in brackets (from the search term list, labelled as not textbook text).
- The engine **does not paraphrase by itself.** A rewritten explanation is only possible when an optional AI
  provider is configured; it is accepted only if every term and number is found in the evidence, and it is then
  labelled "સરળ સમજૂતી (પુરાવા પરથી બનાવેલી, અવતરણ નથી)". No provider is configured and that path has never run
  with a real key.
- Text from a supplementary source is shown only when the student selects that source, in a separate purple block
  headed "પૂરક સ્રોતમાંથી — પાઠ્યપુસ્તકનો ભાગ નથી", with its licence and attribution. It is never merged into the
  textbook answer; when the textbook has no answer, the textbook card still shows the refusal.

## Reliability status (no percentages)

| Status | Shown when |
|---|---|
| સ્રોત સાથે ચકાસેલું — Verified against source | Every sentence and citation passed validation and every question term appears in the shown evidence |
| આંશિક આધાર — Partially supported | Validation passed, but a question term is missing from the evidence, the requested marks could not be filled, a difference had to be shown as two separate definitions, or editions disagree |
| પૂરતો આધાર નથી — Insufficient source evidence | Refusal. The exact refusal sentence is shown with the reason |

## New in 1.1

English and mixed questions; Hindi detected and refused (no Hindi source); worked examples shown step by step
(copied from the book, never calculated); a formula typed in the question is looked up exactly and returned with
the statement printed before it; ambiguous one-word questions are refused with topic suggestions; supplementary
mode; personal notes; saved answers; instruction words such as "સ્પષ્ટ કરો", "ગણી બતાવો" no longer count as topic
words.

## Known weaknesses (all observed in the independent test set)

- **Paraphrases are refused.** "છોડ પોતાનો ખોરાક કેવી રીતે બનાવે છે?" works only when the book uses those words.
  5 of 9 independent failures are of this kind. Retrieval is word-based; it has no synonym or meaning model.
- **English outside the term list is not understood** ("How do plants make their food?"). The list has 95 terms and
  was written around school science; it does not cover a syllabus.
- **Compound definition picks the wrong term** once: "concave mirror નું focal length એટલે શું?" returned the
  definition of the concave mirror, not focal length, and still showed "Verified". The text is genuine but does not
  answer the question.
- **Spelling tolerance is limited**: "ઓમનો નિયમ" and "પરાવતન" were refused; "પ્રકાશસંશ્લેષન", "હરિતદ્રવય",
  "તટસ્થિકરણ", "જળચક્ઠ" were answered.
- **A paraphrased question across two editions** was refused instead of being reported as an edition conflict
  (it did not merge the editions).
- **No arithmetic.** A new numerical problem is refused; only examples printed in the source are shown.
- False-premise and ambiguity checks are word-based and can be fooled by wording not seen in tests.
