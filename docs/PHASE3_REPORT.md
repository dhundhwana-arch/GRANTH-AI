# Phase 3 report — accuracy and understanding (engine `extractive-1.2`)

Date: 2026-11-13. Started from commit `a52e409`. Corpus: the self-authored **demo** books only (not GSEB, not NCERT).
The system is **not production-ready**: see "What still fails" and `docs/MOBILE_TEST_REPORT.md`.

## 1. The reported wrong answer

Question: `concave mirror નું focal length એટલે શું?`

| | Engine 1.1 (`a52e409`) | Engine 1.2 |
|---|---|---|
| Answer shown | "જે ગોળીય અરીસાની પરાવર્તક સપાટી અંદરની તરફ વળેલી હોય તેને **અંતર્ગોળ અરીસો** કહે છે." (page 5) — the definition of the mirror | "ગોળીય અરીસાના ધ્રુવથી મુખ્ય કેન્દ્ર સુધીના અંતરને **કેન્દ્રલંબાઈ** કહે છે." (page 6) |
| Status label | Partially supported | Partially supported, with the note that the book defines focal length for spherical mirrors in general and has no separate definition for a concave mirror |

Correction to the earlier report: for this exact question engine 1.1 showed "Partially supported", not "Verified".
The same fault did produce wrong answers labelled **Verified** for other questions, for example
`અવરોધનો એકમ કયો છે?`, `અરીસો એટલે શું?` and `ઓહ્મ એટલે શું?`. On the 186-question set engine 1.1 gave 19 wrong answers, 11 of them labelled Verified.

Cause: a definition was accepted when its term shared half of the question's words. "અંતર્ગોળ અરીસો" shares two of the
three words of "અંતર્ગોળ અરીસાની કેન્દ્રલંબાઈ", so it won over the concept actually asked about.

Fix (`granth/concepts.py`, `granth/answer.py`):

- The question is split into the **head concept** and its qualifiers. Gujarati puts the head last
  ("અંતર્ગોળ અરીસા**ની કેન્દ્રલંબાઈ**"); English "X of Y" is reordered before mapping.
- A defining sentence is used only if the term it defines **is** the head concept. A sentence defining a different
  term is rejected however many words it shares.
- If the book defines the head concept only in general, that definition is shown as "Partially supported" and the
  missing qualifier is named. If the definition mentions none of the student's qualifiers, the engine refuses.
- A narrower concept never replaces a general one ("શ્વસન" is not answered with "જારક શ્વસન"), and a generic word
  ("નિયમ") is not answered with a specific law.
- Questions about one aspect (એકમ, ઉપયોગ, પ્રકાર, કાર્ય …) need a passage that names both the thing and the aspect.
  The definition of the thing is not accepted.
- Numbers written in the question must be printed in the passage shown. This stops a new numerical problem from being
  "answered" with a similar worked example.
- "Verified against source" now requires all of: every sentence copied from the cited page; no assumed word
  (synonym, typo guess, word-form guess, topic alias); and, for short answers, one passage carrying every question word.

## 2. Regression results before and after

Same question files, run on a checkout of `a52e409` and on the current code (`benchmarks/run_phase3.py --engine-root`).

| Set | Questions | Engine 1.1 pass | Engine 1.1 wrong answers | Engine 1.2 pass | Engine 1.2 wrong answers |
|---|---|---|---|---|---|
| Development set | 186 | 140 | 19 (11 Verified) | 179 | 1 (0 Verified) |
| Held-out set 1, first run | 40 | 33 | 4 (3 Verified) | 36 | 2 (2 Verified) |
| Held-out set 2, first run | 35 | 30 | 3 (2 Verified) | 32 | 1 (1 Verified) |
| Earlier 92-check independent set | 92 | 83 | 1 | 91 | 0 |
| In-house 48-question set | 48 | 48 | 0 | 48 | 0 |

The development-set score for 1.2 is after tuning on that set (its first run scored 169). The held-out rows are
single first runs on questions written after the engine was frozen; they are the fairest numbers here.
`tests/test_phase3.py` (33 tests) pins the reported bug and its variants.

## 3. Paraphrase, mixed language and spelling

Layer added (retrieval aid only; it never supplies answer text):

| Step | Example | Label on the answer |
|---|---|---|
| Vowel-length and Unicode folding | હરીતદ્રવ્ય → હરિતદ્રવ્ય | Verified possible |
| Missing virama, split compound | ઓહમ → ઓહ્મ, "વિદ્યુત પ્રવાહ" → વિદ્યુતપ્રવાહ | Verified possible, with a spelling note |
| One or two letters wrong; two equally close words = no match | પરાવતન → પરાવર્તન | Partial |
| Short word, accepted only next to another matched word | ઓમ (+ નિયમ) → ઓહ્મ | Partial |
| Everyday word → textbook word (69 entries) | છોડ → વનસ્પતિ, વીજળી → વિદ્યુત | Partial |
| Another grammatical form of the same word | ઉમેરાય → ઉમેરવામાં | Partial |
| English term → Gujarati term (150 entries) | focal length → કેન્દ્રલંબાઈ | Verified possible |
| Topic described in everyday words → named concept (10 entries), only if the defining passage carries most of the student's words | — | Partial |

The vocabulary used for matching is limited to the selected edition(s), so a word from another book is never offered.

The four questions named in the task:

| Question | Engine 1.1 | Engine 1.2 |
|---|---|---|
| છોડ પોતાનો ખોરાક કેવી રીતે બનાવે છે? | wrong answer (Partial) | photosynthesis passage, page 1, Partial (છોડ → વનસ્પતિ) |
| How do plants make their food? | refused | photosynthesis passage, page 1 |
| ઓમનો નિયમ | refused | Ohm's law, page 7, Partial (ઓમ → ઓહ્મ) |
| પરાવતન | refused | reflection, page 5, Partial (પરાવતન → પરાવર્તન) |

Development set, engine 1.2: paraphrase 19 of 24, English 18 of 18, mixed 12 of 13, misspelling 18 of 18.
The paraphrase failures are four refusals and one answer whose first sentence is from the wrong page.
Paraphrase remains the weakest area: matching is by words, not by meaning.

## 4. Editions

- When a book has more than one edition in scope, each edition is searched and answered on its own.
- The response carries `edition_results`: one entry per edition with its own answer, evidence and citations, or the
  message that this edition has no sufficient evidence. `editions_missing_evidence` names those editions.
- Different answers → `edition_conflict`: both shown side by side, no merged answer, status Partial.
- Evidence from one edition is never used for another. Asking the 2027 edition about a chapter it lacks is refused.

Results: the 220 / 230 volt conflict is detected for all four wordings in the development set (direct, paraphrase
"ઘરમાં આવતી વીજળીનું વોલ્ટેજ…", English, mixed) and for the held-out wording. Engine 1.1 detected one of four.
Limit: the two demo editions differ in exactly one fact, so this measures one conflict asked five ways.

## 5. Simple explanation (`granth/explain.py`)

Rule-based; no AI model and no external API. Shown in its own block labelled "અવતરણ નથી", below the quotation.

Allowed operations:

1. Split a long definition at a fixed joint: "… બનાવે છે **તે પ્રક્રિયાને** X કહે છે" becomes two sentences.
2. Turn "<વર્ણન>ને X કહે છે" into "‘X’ એ એક નામ છે." and "કોને ‘X’ કહે છે? — <વર્ણન>ને."
3. Put an everyday word in square brackets after a formal word (26-entry list, labelled as not from the book).
4. List meanings of technical terms, copied from the same edition's glossary or defining sentence, with page.
5. Show an example only if the same section of the book prints one.

Each line stores the exact source words it was built from, the chunk and the page. `explain.verify` rejects the
explanation if any piece is not in the quoted sentence, or if a content word was added or dropped. When nothing safe
can be done (formulas, worked examples, tables, plain facts) the block says so and only the source passage is shown.

Honest limits: this restructures and glosses; it does not rewrite text in freer, simpler language, and it creates no
new examples. Simplification depth is therefore modest.

## 6. Tests run on the final code

| Suite | Result |
|---|---|
| `pytest` | 141 passed |
| `npm test` | 18 passed |
| Browser suite, headless Chromium, phone viewport | 33 of 33 steps |
| In-house benchmark + acceptance | 48 of 48, acceptance pass |
| Independent set | 91 of 92 |
| Phase 3 development set | 179 of 186 |
| Held-out 1 / 2, first runs | 36 of 40 / 32 of 35 |
| Secret scan, tracked files and all commits | clean |

## 7. What still fails

- **Wrong answers still occur and can carry the Verified label.** First runs on unseen questions: 3 wrong answers in
  75, all 3 labelled Verified (3 of 44 Verified answers). Two were fixed afterwards; the rule for Verified was then
  tightened, which removes the third label but not the wrong first sentence.
- `ચૂનાનું પાણી ઍસિડિક છે કે બેઇઝિક?` — the answer opens with a sentence from the wrong passage (now Partial).
- `માણસ શ્વાસ કયા અંગથી લે છે?` — same kind of error (Partial).
- Refused although the book has the answer (10 across the three sets, plus one in the older independent set), for example `ઝાડ પાણી ક્યાંથી મેળવે છે?`,
  `ખૂબ કસરત કર્યા પછી સ્નાયુ કેમ દુખે છે?`, `હરિતદ્રવ્ય શેનું શોષણ કરે છે?`, `ઍમ્પિયર શેનો એકમ છે?`,
  `chlorophyll નું કામ શું છે?`, `Why do we need lungs?`.
- The head/qualifier split uses suffix rules and an exception list. Unusual word order or a word ending in ની / નો /
  નું that is not a genitive can be split wrongly.
- All numbers come from 14 pages of demo text and developer-written questions. They do not predict behaviour on a
  real textbook.
