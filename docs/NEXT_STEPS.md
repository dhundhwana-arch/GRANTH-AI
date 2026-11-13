# Next steps

In priority order.

1. **Permission.** Write to the Gujarat State Board of School Textbooks for permission to store, quote and offer
   offline the Gujarati-medium Std 9–12 books. Nothing real can be ingested before this.
2. **Run discovery from a normal connection:** `python -m granth discover`, then review `data/registry/discovered.json`.
3. **Ingest one authorized real book** (Std 10 Science) and re-measure: text-layer usability, OCR CER, chapter
   detection, benchmark on 50+ questions written by a teacher, not the developer.
4. **Test on real Android phones:** voice recognition in Gujarati, camera photos of real pages, offline install.
5. **OCR quality:** recover formulas from the Latin text layer; try image pre-processing; evaluate handwriting
   honestly or state it is unsupported.
6. **Retrieval at scale:** persistent index (PostgreSQL full-text or SQLite FTS), optional multilingual embeddings
   for synonyms and English terms (fixes benchmark H1).
7. **Answer precision:** stop short answers from adding loosely related sentences (benchmark H2); audit stemmer
   collisions.
8. **Deployment:** HTTPS proxy, forwarded-IP rate limiting, backups, admin accounts with audit log.
9. **CI:** GitHub Actions workflow running the three test suites on every push.
10. **Std 1–8** after 9–12 are stable.
