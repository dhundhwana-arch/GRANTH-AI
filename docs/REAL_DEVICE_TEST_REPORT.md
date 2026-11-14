# Real device test report (Phase 4)

**Status: no real-device test has been performed.** The developer agent has no phone, tablet, camera or microphone. Every row below is "Not tested" until a person fills it in. The automated browser test (headless Chromium, phone-size viewport, 33 steps, all passing) is not a substitute.

## How to run it

1. Start the server on a computer on the same Wi-Fi: `python -m granth serve --host 0.0.0.0 --port 8000`, or use a deployed HTTPS address. Camera and microphone need HTTPS (or `localhost`).
2. Open the address in Chrome on the device.
3. Do each step, write Pass / Fail and a note. Fill in the device line.

Device: ______  Android version: ______  Chrome version: ______  Date: ______  Tester: ______

| # | Step | Expected | Android tablet | Android phone | Chrome desktop |
|---|---|---|---|---|---|
| 1 | Open the home page | Gujarati text is readable, nothing cut off, no sideways scrolling | Not tested | Not tested | Not tested |
| 2 | Pick the demo science book and type "અવરોધનો એકમ કયો છે?" with the Gujarati keyboard | One sentence, source page, green "Verified" label | Not tested | Not tested | Not tested |
| 3 | Type "What is photosynthesis?" | Gujarati definition from page 1 | Not tested | Not tested | Not tested |
| 4 | Type "chlorophyll નું કામ શું છે?" | Sentence about હરિતદ્રવ્ય, yellow "Partial" label | Not tested | Not tested | Not tested |
| 5 | Type "હૃદયનું કાર્ય શું છે?" | The refusal sentence, no answer | Not tested | Not tested | Not tested |
| 6 | Rotate the device | Layout adjusts, nothing overlaps | Not tested | Not tested | n/a |
| 7 | Tap the camera button | Chrome asks for camera permission | Not tested | Not tested | Not tested |
| 8 | Photograph a printed Gujarati question | Recognised text appears in the box and can be corrected before asking | Not tested | Not tested | Not tested |
| 9 | Deny camera permission and tap again | A clear message, the app keeps working | Not tested | Not tested | Not tested |
| 10 | Tap the microphone button | Chrome asks for microphone permission | Not tested | Not tested | Not tested |
| 11 | Say a question in Gujarati | The spoken words appear as Gujarati text | Not tested | Not tested | Not tested |
| 12 | Save the demo book for offline use | Progress shown, then "saved" | Not tested | Not tested | Not tested |
| 13 | Turn on aeroplane mode and reopen the app | The app opens; the saved book can be read | Not tested | Not tested | Not tested |
| 14 | Open the PDF page of a citation; go to next and previous page | Correct page opens; navigation works; text is sharp | Not tested | Not tested | Not tested |
| 15 | Open history, then "erase all my data" | History is empty; reopening shows nothing from before | Not tested | Not tested | Not tested |
| 16 | Use the app for 10 minutes | No freezing, no noticeable heat or battery drain | Not tested | Not tested | n/a |

Known in advance: Gujarati speech recognition depends on the device's Google speech service and may be missing; on-device OCR downloads about 15 MB of language data on first use and is slow on low-end phones (not measured).

## Results

None recorded.
