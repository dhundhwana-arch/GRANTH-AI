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

## Phase 3 status (2026-11-13)

**No physical-device test has been run.** No phone is attached to the build environment. The browser suite now has
33 steps and still runs in headless Chromium with a simulated speech recogniser and a computer-rendered photo.
Nothing below is claimed as passed.

## Manual real-device procedure

Tester needs: an Android phone with Chrome, a second device with a clearly different screen (small phone about
360 px wide, and a tablet or a phone in landscape), a printed page of Gujarati text, and the HTTPS address of the
app. Microphone and camera work only over HTTPS or `localhost`.

Server for the test (strong token, demo data):

```bash
.venv/bin/python -m granth seed-samples
GRANTH_ADMIN_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')" \
  .venv/bin/python -m granth serve --host 0.0.0.0 --port 8000     # put an HTTPS proxy or tunnel in front
```

Record for every run: date, tester, phone model, Android version, Chrome version, keyboard app, network type,
commit hash (`git rev-parse --short HEAD`). Write Pass / Fail / Not run and a screenshot for each failure.

| No. | Area | Steps | Expected |
|---|---|---|---|
| 1 | Open and select | Open the address in Chrome. Choose the demo board, standard, subject "વિજ્ઞાન", edition 2026. | Gujarati text is sharp, no boxes for letters or conjuncts; no sideways scrolling; the demo label is visible. |
| 2 | Gujarati keyboard | Tap the question box. With Gboard Gujarati type `અંતર્ગોળ અરીસાની કેન્દ્રલંબાઈ એટલે શું?` and send. | The box and the send button stay visible above the keyboard; conjuncts (ર્ગ, ન્દ્ર) are stored correctly; the answer is the focal-length sentence, page 6, "Partially supported". |
| 3 | Transliteration keyboard | Repeat with the "Gujarati (transliteration)" layout, and once with a deliberate slip: `પરાવતન એટલે શું?` | Same answer quality; the slip is answered as પરાવર્તન with a note naming the assumed word. |
| 4 | Mixed and English | Ask `concave mirror નું focal length એટલે શું?` and `How do plants make their food?` | Focal-length definition (not the mirror definition); photosynthesis passage, page 1. |
| 5 | Refusal | Ask `ન્યૂટનનો બીજો નિયમ એટલે શું?` | The fixed "not enough support in this textbook" message; no answer text. |
| 6 | Microphone permission, allow | Tap the microphone, choose "Allow", say a question in Gujarati. | Recognised text appears in the box, is editable, and is **not** sent automatically. Note the words recognised wrongly. |
| 7 | Microphone permission, deny | In Chrome site settings set Microphone to "Block". Tap the microphone. | A Gujarati message explains that permission is off; typing still works; the app does not freeze. |
| 8 | Voice without network | Switch on flight mode, tap the microphone. | A clear message; no endless spinner. |
| 9 | Camera permission, allow | Tap the camera button, allow, photograph a printed Gujarati question in good light. | Photo is read on the phone; extracted text is shown for editing before sending. Record seconds taken and wrong characters. |
| 10 | Camera permission, deny | Block Camera in site settings, tap the camera button. | Message shown; gallery choice still works. |
| 11 | Photo extraction quality | Repeat step 9 with: a photo from the gallery; a tilted page; dim light; a handwritten line. | Printed text mostly correct. Tilted and dim photos may be poor. Handwriting is unsupported: confirm the app does not present garbage as a confident question. |
| 12 | Page citation | In any answer tap "પૃષ્ઠ N ખોલો". | The book opens on that page and the quoted sentence is found there, word for word. |
| 13 | Edition conflict | Select both editions of વિજ્ઞાન and ask `ઘરમાં આવતી વીજળીનું વોલ્ટેજ કેટલું ગણવામાં આવ્યું છે?` | Two blocks side by side or stacked, 220 વોલ્ટ (2026) and 230 વોલ્ટ (2027), each with its own page; no single merged answer. |
| 14 | Simple explanation | Ask `પ્રકાશસંશ્લેષણ એટલે શું?` | The quotation and the "સરળ સમજૂતી" block are visibly separate; the block says it is not a quotation. |
| 15 | Offline library, download | Library → download the demo book. Note the storage figure. | Download completes and is listed. |
| 16 | Offline library, use | Flight mode on. Close Chrome fully, reopen the address. Open the book, turn pages, search a word. Ask a question answered earlier, then a new one. | App opens; book readable and searchable; earlier answer is shown from the device; the new question gives search results labelled as not an answer. |
| 17 | Install | Chrome menu → "Add to Home screen". Open from the icon, online and offline. | Opens full-screen; offline behaviour as in step 16. |
| 18 | Small screen | On the 360 px phone visit every tab: home, ask, chapters, exam, dictionary, library, history, saved, notes, about. Also set Android font size to largest. | No sideways scrolling; no clipped buttons; all buttons easy to tap. |
| 19 | Large screen and rotation | Repeat step 18 on the tablet or in landscape; rotate while an answer is shown. | Layout uses the width sensibly; the answer is not lost on rotation. |
| 20 | Erase my data | History → "મારો બધો ડેટા ભૂંસો". Reload. | History, saved answers and notes are empty. |
| 21 | Slow phone and network | On the weakest phone available, with mobile data, repeat steps 2, 9 and 15. | Record the time to first answer, the photo-reading time and the download time. |

Report back in this file under a new heading "Device run <date>" with the table filled in. Until such a section
exists, the status of real-device testing is: **not done**.
