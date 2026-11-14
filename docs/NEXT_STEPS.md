# Next steps (after Phase 5)

GRANTH-AI is a demo. It is not ready for real students. The order below is the order of importance.

## Needs a person outside the project

| # | Action | Who | Material ready |
|---|---|---|---|
| 1 | Send the permission request to the Gujarat State Board of School Textbooks and keep the written reply | Project owner | `docs/templates/PUBLISHER_PERMISSION_REQUEST.md` |
| 2 | Ask a Gujarati-medium teacher to write about 100 questions and review the answers | Project owner and a teacher | `docs/TEACHER_REVIEW_TEMPLATE.md`, `docs/templates/teacher_questions_template.csv` |
| 3 | Run the 30-minute test on an Android phone and a tablet | Any tester with a device | `docs/REAL_DEVICE_TEST_REPORT.md` |
| 4 | Try the app with a few students, with school or parent consent, and collect the form | Teacher | `docs/STUDENT_FEEDBACK_TEMPLATE.md` |
| 5 | Have a second person review security before any public use | Reviewer | `docs/SECURITY_REPORT.md` |

## Engine work (needs engine 1.5 and a new frozen set)

| # | Defect | Evidence |
|---|---|---|
| 1 | Too many refusals from unknown everyday words (દાખલ, ઉત્પન્ન, સુધારવા, પરિણામ; English body, added, pure) | 14 of the 19 frozen refusals |
| 2 | Premise check refuses some true questions | P006, P030, P061 |
| 3 | Attribute not found although the sentence exists | P130, P131, Z03, Z52 |
| 4 | Explanation gloss ignores context (અંગ shown as "organ" for parts of a map) | P132 |
| 5 | Explanations annotate more than they simplify; lines get longer | `docs/EXPLANATION_QUALITY_REPORT.md` |
| 6 | Edition conflict missed when the question has an unknown word | P111, P113, D105 |
| 7 | Older open items: S17, F07, N18, N20, N28, Z20; "વિદ્યુતપ્રવાહનું સૂત્ર લખો" returns Ohm's law; a malformed either/or question is answered | regression results |

The safest way to cut refusals is a larger reviewed word list, ideally built from teacher-written questions. Loosening the validator is not safe: two attempts in Phase 5 produced wrong answers and were withdrawn.

## Evaluation work

- Evaluate a multilingual embedding model for retrieval when weights can be obtained through an approved route. Keep it optional.
- Build a larger permitted corpus. A 14-page demo cannot show how the engine behaves on a real book.
- Add a browser test step for the edition-conflict display.
- Upgrade `pip` and `setuptools` in deployment environments.
