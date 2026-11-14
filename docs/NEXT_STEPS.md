# Next steps

In priority order.

1. **Permission (blocker for all real content).** Write to the Gujarat State Board of School Textbooks for
   permission to store, quote and offer offline the Gujarati-medium Std 9–12 books. Until then no board, standard
   or subject is supported. NCERT is DENIED unless it grants written permission.
2. **Finish the terms review:** read the DIKSHA content-licence clause and per-item licences; re-try the GSSTB
   portal from a normal connection (`python -m granth discover`).
3. **Real-device test** following `docs/MOBILE_TEST_REPORT.md`: voice, camera, offline, install.
4. **Paraphrase understanding** — the main quality gap (5 of 9 independent failures). Options: a synonym list
   built by teachers, or a small multilingual embedding model run locally. Keep word-for-word validation.
5. **Fix the wrong-definition case** (MX04): when a definition question names two terms, pick the head term or
   mark the answer Partially supported.
6. **Spelling tolerance** for short words ("ઓમ" / "ઓહ્મ", "પરાવતન").
7. **Edition conflict on paraphrased questions** (CE01b).
8. **Teacher review** of the supplementary notes and of the English–Gujarati term list; a teacher-written test set.
9. **Hindi- and English-medium text processing** (stop-words, stemming) before adding such sources.
10. **Accounts** (so notes and saved answers survive a browser reset and are not tied to a bare session id),
    HTTPS deployment, backups, audit log.
11. **CI** running the four test commands on every push.
12. OCR for formulas and tables; handwriting stays unsupported until measured.
