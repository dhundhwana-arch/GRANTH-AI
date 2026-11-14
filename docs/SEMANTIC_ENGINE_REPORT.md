# Semantic engine report (Phase 4)

## What was investigated and what was done

| Topic | Outcome |
|---|---|
| Intent classification | **Implemented** (`granth/intent.py`), rule-based, 19 intents: either/or, unit, which-quantity-for-a-unit, instrument, organ, naming, reason, use, source (where from), place (where), relation, between, from–to, how many, types, function, process, example, plain fact. Definition, formula, difference and steps were already separate modes in 1.2. |
| Concept + attribute extraction | **Implemented**: hard terms = concept; intent = attribute; verbs and generic words = soft (`validate.plan`). |
| Morphological normalisation | **Partly**: existing stemmer; added grammar-based verb detection, case-suffix detection that requires at least two letter clusters before the suffix, participles treated as soft words. No real morphological analyser. |
| Spelling variants | Existing spelling/fuzzy matcher kept. Changed order: a listed everyday synonym now wins over a merely similar-looking word. A fuzzy match can never be Verified. It still produced one wrong answer in the frozen test (વૉટમીટર → વોલ્ટમીટર). |
| Gujarati–English term mapping | Glossary `data/glossary/en_gu_terms.json` extended (verbs such as released, stored, absorb, measure). Retrieval aid only. |
| Synonym / concept dictionary | `data/glossary/gu_synonyms.json` extended with a few everyday words. Retrieval aid only; an answer found through it is Partial at best. |
| Keyword + semantic retrieval | Retrieval is unchanged: BM25 + character-trigram cosine + term coverage. |
| Local embedding models | **Not evaluated – blocked.** This build environment can reach only GitHub, npm and PyPI; model weights (for example multilingual-e5-small, about 120 MB quantised / 470 MB full) could not be downloaded. No claim is made about whether embeddings would help. |
| Paid APIs | None used. |

Query expansion (glossary, synonyms, spelling) only widens the search. Evidence is judged afterwards on the book's own sentence by `validate.py`, and every expanded match lowers the status to Partial.

## Limits found by the frozen test

* The engine understands question *shape*, not meaning. New phrasing of a verb or a function word it has not seen leads to refusal: "છૂટો પડે છે" (for મુક્ત થાય છે), "રહેલો છે", "ખેંચે છે", "ગણાય છે", "જોડીએ તો", "દવા", "ઘરે આવતા". 11 of 49 answerable frozen questions were refused for this kind of reason.
* English questions are the weakest group: 2 of 5 correct in the frozen test.
* Negation is not handled (one false Verified).
* The dictionaries were written by the developer around a 14-page demo book. They will not cover a real textbook without substantial work.

The honest summary: this is a careful rule-based matcher, not semantic understanding. It is stricter than 1.2 and therefore wrong less often, at the cost of refusing more paraphrases.
