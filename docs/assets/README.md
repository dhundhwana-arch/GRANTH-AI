# GRANTH-AI visual assets

All artwork here is original, drawn with plain SVG paths and released under the repository's MIT licence.
No third-party logo, brand mark, icon or traced typeface is used, and no third-party text appears in any
diagram.

| File | Size | Purpose | How it is made |
|---|---|---|---|
| `granth-ai-logo.svg` | 512 × 512 | Project mark: an open book whose right page becomes a pathway of three evidence nodes, the last carrying a check mark | hand-written paths |
| `granth-ai-architecture.svg` | 1240 × 1672 | The seven stages of the answer pipeline, with the real module names and the parallel paths | `scripts/build_visual_assets.py` |
| `granth-ai-workflow.svg` | 1240 × 1104 | One question through validation, and the four outcomes it can produce, with the `status` value the API returns | `scripts/build_visual_assets.py` |
| `granth-ai-social-preview.svg` | 1280 × 640 | GitHub / social preview card | `scripts/build_visual_assets.py` |
| `screenshots/*.png` | 390 px wide, 2× | Real captures of the running demo (see below) | headless Chromium, then `scripts/compress_screenshots.py` |

## Regenerating the diagrams

```bash
python3 scripts/build_visual_assets.py            # write the three generated SVGs
python3 scripts/build_visual_assets.py --check    # fail if a committed SVG is out of date
```

The colours are the application's own (`web/styles.css` `:root`), so the diagrams and the running app look
like one product.

## The Gujarati text in the diagrams

The diagrams deliberately contain **no Gujarati text**. GitHub serves an `<img>`-embedded SVG without the
page's web font, so a Gujarati string would be rendered by whatever font the viewer happens to have — often
as empty boxes. Gujarati strings are therefore referred to in English ("one fixed Gujarati refusal
sentence") instead of being set in the artwork.

## Screenshots

`screenshots/` holds real captures of the application running at this commit (headless Chromium, 390 × 844
viewport at 2× device pixel ratio), taken after selecting the demo textbook *ગ્રંથ વિજ્ઞાન નમૂના પાઠમાળા*,
edition 2026:

| File | Shows |
|---|---|
| `01-home.png` | Home screen, permanent credits, the demo-material notice |
| `02-select-textbook.png` | Board → medium → standard → subject → edition → chapter, plus the edition-comparison toggle |
| `04-answer-verified.png` / `-detail.png` | A verified answer: quotation label, answer sentence, harder words, English terms, the separate explanation panel |
| `05-refusal.png` / `-detail.png` | The refusal state: one fixed sentence, no citation, no answer |
| `06-english-question.png` / `-detail.png` | An English question answered from the Gujarati page, with the word-mapping note |
| `07-exam.png` | Exam-preparation screen |
| `11-edition-conflict.png` / `-detail.png` | The 220 V / 230 V edition conflict, each value with its own page |

They are genuine screenshots, not mock-ups. The figures on screen come from the demo corpus; no dashboard
metric was ever staged for a screenshot.

## Social preview — how to set it on GitHub

There is no API for uploading a repository social preview, so it must be set by hand (an administrator of
the repository can do this in about a minute, using GitHub's own documentation for setting a repository's
social preview image):

1. Open the file `docs/assets/granth-ai-social-preview.svg` and export it to PNG at **1280 × 640**
   (GitHub's documented social-preview size), or open it in a browser and take a 1280 × 640 screenshot.
2. On GitHub: **Settings → General → Social preview → Upload an image**, and choose that PNG.

The SVG is the source of truth; any PNG is a derivative of it.
