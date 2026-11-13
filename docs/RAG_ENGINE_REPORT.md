# RAG engine report

Engine version `extractive-1.0`. Results below come from `benchmarks/results/qa_benchmark.json`.

## Retrieval

- **Keyword leg:** BM25 over stemmed Gujarati terms (k1 1.4, b 0.75), built in memory from authorized, approved chunks.
- **"Semantic" leg:** TF-IDF cosine over character trigrams. This is *not* a neural embedding. It gives tolerance to
  inflection and spelling; it does not understand synonyms or English equivalents.
- **Term resolution:** exact → joined compound (“વિદ્યુત પ્રવાહ” → “વિદ્યુતપ્રવાહ”) → small-edit fuzzy match
  (“ઓહમ” → “ઓહ્મ”, “હરીતદ્રવ્ય” → “હરિતદ્રવ્ય”).
- **Score:** 0.55 × weighted term coverage + 0.25 × BM25 + 0.20 × trigram cosine; duplicates removed by text hash.
- **Filter:** selected edition(s) and optional chapter are applied before scoring, so other books cannot leak in.

## Answering

Deterministic and extractive: sentences, tables and formulas are copied, never rewritten. Modes: one-line,
definition, short, detailed, point-wise, difference (textbook table, or two definitions side by side with a note),
formula. Marks 1–5 map to 1, 2, 3, 5, 6 points; a shortfall is stated, not padded.

## Abstention

The engine refuses when: no authorized book is in scope; no content words; no evidence; low term coverage;
definition / formula / difference not present; a "why" premise is not in any single textbook sentence; or
verification fails. Abstained and unverified results are never cached.

## Generative layer

`providers.py` has adapters for Gemini and OpenAI-compatible endpoints (Hugging Face router, Groq, OpenRouter, a
local server) behind one router with a daily call limit. It is **off by default and was never called with a real
key**. Its logic is tested with fake providers: output is accepted only if every sentence is supported by the
retrieved evidence, otherwise the extractive answer is used.

## Measured quality (48 questions, demo books)

| Metric | Value |
|---|---|
| End-to-end success | 46 / 48 (95.8%) |
| Precision@1 / Recall@3 / MRR | 0.971 / 1.000 / 0.985 |
| Faithfulness (verbatim in selected book) | 1.000 |
| Abstention accuracy (17 must-refuse questions) | 1.000 |
| Answers given where refusal was required | 0 |
| Median latency, uncached | 0.7 ms |

## Limitations

- **Tiny corpus.** 90 chunks. Thresholds were tuned on it and will need re-tuning on real books; speed at
  thousands of pages is unmeasured (the index is in memory and scans linearly).
- No synonym or cross-language matching: “photosynthesis એટલે શું?” and “pH scale એટલે શું?” are refused.
- Short mode can add a loosely related sentence (benchmark H2 pulled in a sentence about reflection because of the
  shared word “નિયમ”).
- False-premise detection is lexical. It catches the tested cases; a premise that reuses the textbook's own words
  in one sentence with the opposite meaning would get through.
- The stemmer strips endings aggressively; collisions between unrelated words have not been audited.
