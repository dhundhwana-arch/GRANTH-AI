# Real device test report (Phase 5)

**Status: NOT TESTED. No physical Android device was available. No result below comes from a real phone or tablet.**

## Three kinds of evidence

| Kind | What it is | Status |
|---|---|---|
| Automated browser | Headless Chromium on a Linux server runs 33 scripted steps (`tests/e2e/run_e2e.mjs`) | 33 of 33 pass on 2026-11-14 |
| Simulated viewport | The same run sets a 390 × 800 touch viewport and checks other widths for sideways scrolling | passes; this is a desktop browser engine pretending to be a phone |
| Physical device | A person using a real Android phone or tablet | **NOT TESTED** |

The automated run cannot show how the app behaves with a real Gujarati keyboard, camera, microphone, battery, storage or mobile network.

## 30-minute procedure for a tester

Setup (3 minutes): start the server on a computer on the same Wi-Fi with `python -m granth serve --host 0.0.0.0 --port 8000`, or use an HTTPS address. Camera, microphone and offline mode need HTTPS. Open the address in Chrome on the device.

Fill in: Device ______ Android version ______ Chrome version ______ Date ______ Tester ______

| # | Area | Minutes | What to do | Expected | Result |
|---|---|---|---|---|---|
| 1 | First load | 1 | Open the home page | Loads within a few seconds; demo label visible | NOT TESTED |
| 2 | Gujarati rendering | 1 | Read headings and an answer | Conjuncts and vowel signs correct; nothing cut off | NOT TESTED |
| 3 | Layout | 2 | Scroll each screen; rotate the device | No sideways scrolling; nothing overlaps | NOT TESTED |
| 4 | Gujarati keyboard | 2 | Type "અવરોધનો એકમ કયો છે?" | One sentence, page citation, Verified label | NOT TESTED |
| 5 | English and mixed input | 2 | Type "What is photosynthesis?" and "chlorophyll નું કામ શું છે?" | Gujarati book sentence; Partial label on the second | NOT TESTED |
| 6 | Refusal | 1 | Type "મૂત્રપિંડનું કાર્ય શું છે?" | The refusal sentence only | NOT TESTED |
| 7 | Negation | 2 | Type "ઑક્સિજન વગર થતા શ્વસનને શું કહે છે?" | The sentence about અજારક શ્વસન | NOT TESTED |
| 8 | Unknown word | 2 | Type "વૉટમીટર શું માપે છે?" | Refusal and a "did you mean" line; no voltmeter answer | NOT TESTED |
| 9 | Edition conflict | 2 | Choose the demo science book so that both editions are searched (no single edition picked); ask "ઘરવપરાશના વિદ્યુતપુરવઠાનું વોલ્ટેજ કેટલું છે?" | 220 and 230 shown separately with edition and page | NOT TESTED |
| 10 | Simple explanation | 2 | Open the explanation under an answer | Separate block marked "not a quotation"; English terms in brackets | NOT TESTED |
| 11 | Camera and OCR | 3 | Tap the camera button; photograph a printed Gujarati question; then deny permission and retry | Permission prompt; text appears and can be edited; clear message when denied | NOT TESTED |
| 12 | Microphone | 2 | Tap the microphone button; speak a Gujarati question | Permission prompt; words appear as Gujarati text, or a clear "not available" message | NOT TESTED |
| 13 | Offline | 3 | Save the demo book; turn on aeroplane mode; reopen | App opens; saved book is readable | NOT TESTED |
| 14 | PDF page viewer | 1 | Open a citation page; go to next and previous page | Correct page; sharp text | NOT TESTED |
| 15 | Data deletion, heat and battery | 2 | Open history; tap "erase all my data"; note heat and battery after the session | History empty; no freezing, no unusual heat | NOT TESTED |

Record for every failed step: what was shown, a screenshot, and the exact text typed.

## Results

None recorded.

| | |
|---|---|
| Implemented | procedure and form |
| Automatically tested | headless browser, simulated viewport |
| Manually tested | none |
| Not tested | every physical-device step above |
| Blocked | no device available to the developer |
| Requires human | a tester with an Android phone or tablet |
