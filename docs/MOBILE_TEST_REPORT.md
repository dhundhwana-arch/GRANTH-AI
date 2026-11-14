# Mobile test report

Date: 2026-11-13.

## What was tested

**No physical phone was used.** Everything below ran in headless Chromium with an emulated phone viewport
(touch enabled), driven by `tests/e2e/run_e2e.mjs`. Results: `benchmarks/results/e2e_browser.json` (31 of 31).

| Check | Result |
|---|---|
| No horizontal scrolling at 360 px and 390 px on 11 screens (home, selection, ask, chapters, exam, dictionary, library, history, saved, notes, about) | Pass |
| Buttons, tabs and selects at least 40 px high on those screens | Pass |
| Large question box, answer card sections, clickable "પૃષ્ઠ N ખોલો" source button, separate supplementary block | Pass; also inspected by screenshot at 390 px |
| Typed Gujarati and English questions | Pass |
| Voice input: transcript goes into the editable box, is not auto-submitted; permission denial message | Pass **with a simulated recogniser** |
| Camera/gallery: image → on-device OCR → editable text → answer | Pass **with a computer-rendered image of printed text** |
| Offline: app reloads, downloaded book opens and is searchable, saved answer reused with the network cut | Pass (emulated offline) |
| Saved answers, personal notes | Pass |

## Not tested — do not rely on these yet

- Real Android or iOS devices, real browsers other than Chromium, slow networks, low-memory phones.
- Real Gujarati speech recognition (depends on the phone's browser and an internet connection on most Android phones).
- Camera photos of real textbook pages; **handwriting is unsupported and untested**.
- Installing the app to the home screen; behaviour with the on-screen Gujarati keyboard open.
- Screen readers.

## Seen during inspection

- Emoji icons on buttons showed as empty boxes in the test browser (it has no emoji font). Real phones normally
  have one; unconfirmed.
- Wide tables in answers now scroll sideways inside the card instead of widening the page.

## Suggested device test (about 20 minutes)

Open the site on two Android phones (Chrome) and one iPhone (Safari): select the demo book, ask one typed, one
spoken and one photographed question, open a cited page, download the book, switch on flight mode and reopen it.
Record what fails here.
