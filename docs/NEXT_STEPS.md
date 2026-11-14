# Next steps (after Phase 4)

In order of importance.

1. **Get one real textbook with written permission.** Everything so far is measured on a 14-page demo. Until a real book is loaded, accuracy on real material is unknown. See `SOURCE_PERMISSION_REGISTER.md` for what the letter must cover.
2. **Run the device checklist** in `REAL_DEVICE_TEST_REPORT.md` on one Android tablet and one phone. About 30 minutes.
3. **Have a teacher write and judge questions.** All 331 questions so far were written by the developer. A teacher's 100 questions on a real chapter would be the first truly independent test.
4. **Fix the frozen-test failures, then write a new frozen set** (the current one is now seen):
   * negation ("ન હોય", "નથી", "વગર") must be matched against હાજરી / ગેરહાજરી or the question refused;
   * a spelling-guessed term must not replace a technical term when the two are different instruments or quantities – refuse instead;
   * false-premise detection for "why is X used in Y" questions;
   * do not refuse because of an unknown verb when the concept and attribute are both found – answer as Partial;
   * edition-conflict check should run before the unknown-word refusal.
5. **Evaluate a small multilingual embedding model** on a machine that can download it. Measure on the frozen-set style of test whether it reduces incorrect refusals without adding wrong answers; record size and speed on a phone-class device before adopting it.
6. **Explanations**: 16 of 33 frozen answers had no simplified explanation. Add safe rules for unit, place and cause sentences.
7. **Deployment**: HTTPS in front of the server, a strong admin token with an expiry date, backups of the SQLite file.
8. Smaller: formula lookup by quantity name ("વિદ્યુતપ્રવાહનું સૂત્ર"), English question coverage.
