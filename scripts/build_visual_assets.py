#!/usr/bin/env python3
"""Build the GRANTH-AI visual identity assets (SVG) from one design system.

    python3 scripts/build_visual_assets.py            # writes docs/assets/*.svg
    python3 scripts/build_visual_assets.py --check    # verify the files are up to date

The four assets are original artwork released under the repository's MIT licence. They contain no
third-party logo, brand mark or traced typeface. Text in the diagrams is Latin script only, because
GitHub renders SVG inside <img>, where the page's Gujarati webfont is not available: a Gujarati
string would fall back to whatever font the viewer happens to have, or to empty boxes. Gujarati
words are therefore referenced by name ("fixed Gujarati refusal sentence") instead of being set
in the diagram.

Colours are the ones the application itself uses (web/styles.css :root), so the diagrams and the
running app look like one project.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets"

# ---------------------------------------------------------------- design system (mirrors web/styles.css)
BG = "#fff8ef"
CARD = "#ffffff"
INK = "#2a1a12"
MUTED = "#6b5a50"
BRAND = "#7a2e0e"
BRAND_D = "#67240b"
AMBER = "#c9792b"
AMBER_L = "#f6e7d5"
OK = "#1d6b3a"
WARN = "#8a5a00"
BAD = "#9b1c1c"
LINE = "#ead9c6"
SUPP = "#5b4bb5"

SANS = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', monospace"


class Svg:
    def __init__(self, width: int, height: int, title: str, desc: str):
        self.w, self.h = width, height
        self.parts: list[str] = []
        self.title, self.desc = title, desc

    # -------------------------------------------------- primitives
    def rect(self, x, y, w, h, fill=CARD, stroke=LINE, rx=16, sw=1.5, extra=""):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}" {extra}/>')

    def card(self, x, y, w, h, accent=None, fill=CARD):
        """White card with an optional coloured left edge (the app's answer-card idiom)."""
        self.rect(x, y, w, h, fill=fill)
        if accent:
            self.parts.append(
                f'<rect x="{x}" y="{y}" width="7" height="{h}" rx="3.5" fill="{accent}"/>')

    def text(self, x, y, s, size=16, fill=INK, weight="400", anchor="start", family=SANS,
             opacity=None, spacing=None, style=""):
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        sp = f' letter-spacing="{spacing}"' if spacing is not None else ""
        st = f' font-style="{style}"' if style else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}"{a}{o}{sp}{st}>{escape(s)}</text>')

    def lines(self, x, y, rows, size=16, fill=MUTED, weight="400", lh=24, anchor="start"):
        for i, row in enumerate(rows):
            self.text(x, y + i * lh, row, size=size, fill=fill, weight=weight, anchor=anchor)

    def pill(self, x, y, label, fill, text_fill="#ffffff", size=13, pad=15, h=27, weight="600"):
        # upper-case / bold labels are wider per character than normal text; keep a safe margin
        factor = 0.68 if size <= 14 else 0.60
        w = int(len(label) * size * factor) + pad * 2
        self.rect(x, y, w, h, fill=fill, stroke=fill, rx=h / 2, sw=1)
        self.text(x + w / 2, y + h / 2 + size * 0.36, label, size=size, fill=text_fill,
                  weight=weight, anchor="middle")
        return w

    def circle(self, cx, cy, r, fill, stroke=None, sw=0):
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{s}/>')

    def arrow(self, x1, y1, x2, y2, color=AMBER, sw=2.5, dashed=False, marker="arrow"):
        d = ' stroke-dasharray="7 6"' if dashed else ""
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" '
            f'marker-end="url(#{marker})" stroke-linecap="round"{d}/>')

    def path(self, d, stroke=AMBER, sw=2.5, fill="none", marker=None, dashed=False, join="round"):
        m = f' marker-end="url(#{marker})"' if marker else ""
        ds = ' stroke-dasharray="7 6"' if dashed else ""
        self.parts.append(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="{join}" '
            f'stroke-linecap="round"{m}{ds}/>')

    def render(self, defs: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            f'width="{self.w}" height="{self.h}" role="img" aria-labelledby="t d">\n'
            f'  <title id="t">{escape(self.title)}</title>\n'
            f'  <desc id="d">{escape(self.desc)}</desc>\n'
            f'  <defs>{defs}</defs>\n  '
            + "\n  ".join(self.parts)
            + "\n</svg>\n"
        )


DEFS = (
    f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{AMBER}"/></marker>'
    f'<marker id="arrow-ok" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{OK}"/></marker>'
    f'<marker id="arrow-bad" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{BAD}"/></marker>'
    f'<marker id="arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{MUTED}"/></marker>'
    f'<linearGradient id="brand" x1="0" y1="0" x2="1" y2="1">'
    f'<stop offset="0" stop-color="#8d3a13"/><stop offset="1" stop-color="{BRAND_D}"/></linearGradient>'
    f'<linearGradient id="amber" x1="0" y1="0" x2="0" y2="1">'
    f'<stop offset="0" stop-color="#e9a457"/><stop offset="1" stop-color="{AMBER}"/></linearGradient>'
)


def header(s: Svg, title: str, subtitle: str, width: int) -> None:
    s.rect(0, 0, width, s.h, fill=BG, stroke=BG, rx=0, sw=0)
    s.rect(0, 0, width, 8, fill=BRAND, stroke=BRAND, rx=0, sw=0)
    s.text(56, 76, title, size=34, fill=BRAND, weight="700")
    s.text(56, 110, subtitle, size=17, fill=MUTED)


# ---------------------------------------------------------------- 1. architecture
def architecture() -> str:
    W, H = 1240, 1672
    s = Svg(W, H, "GRANTH-AI architecture",
            "One question from the browser to a cited answer: language and intent, edition scope, hybrid "
            "retrieval, evidence validation, then either an answer taken word for word from the textbook "
            "or an explicit refusal.")
    header(s, "GRANTH-AI · Evidence Pipeline",
           "One question, end to end · engine extractive-1.4 · deterministic, no language model, "
           "no external API call", W)

    # status chips
    x = 56
    for label, col in (("DEMO / RESEARCH PROTOTYPE", WARN), ("0 external calls", OK), ("cit. 43/43 (frozen)", MUTED)):
        x += s.pill(x, 128, label, col, size=12) + 8

    rows = [
        ("Student asks", BRAND,
         ["Typed question, voice transcript, or a photo of a printed line.",
          "Language may be Gujarati, English, or a mixture of both."],
         "web/js/app.js · voice.mjs · imageprep.mjs"),
        ("Language and intent", AMBER,
         ["Words are resolved to the book's own vocabulary (synonym, spelling, transliteration).",
          "Question form is read: definition, unit, place, cause, difference, formula, steps.",
          "Negation and the assumed premise are checked before anything is searched."],
         "granth/lang.py · intent.py · gujarati.py\npolarity.py · premise.py"),
        ("Edition scope", BRAND,
         ["Only sources that are APPROVED and admin-approved are searchable.",
          "Editions are searched separately and are never merged into one answer."],
         "granth/answer.py (resolve_scope) · db.py"),
        ("Hybrid retrieval", AMBER,
         ["BM25 keyword score + character-trigram TF-IDF cosine + term coverage,",
          "restricted to the chosen edition and chapter."],
         "granth/retrieval.py"),
        ("Evidence validation", BRAND,
         ["Each sentence must contain the asked concept AND the asked aspect.",
          "Any number in the answer must exist in the source; polarity must agree.",
          "A look-alike or unknown technical word is never silently substituted."],
         "granth/validate.py · concepts.py"),
        ("Answer or refusal", AMBER,
         ["Answer: source sentences, word for word, with chapter and page and a trust label.",
          "Refusal: one fixed Gujarati sentence when the evidence is not sufficient."],
         "granth/answer.py (ask)"),
        ("Citation and display", BRAND,
         ["Citation card, page viewer, the quoted evidence, and a rule-based explanation",
          "in a separate block labelled as NOT a quotation."],
         "web/js/app.js · granth/explain.py"),
    ]
    y0, rh, gap = 178, 150, 20
    for i, (title, accent, body, files) in enumerate(rows):
        y = y0 + i * (rh + gap)
        s.card(150, y, 934, rh, accent=accent)
        s.circle(104, y + rh / 2, 24, accent)
        s.text(104, y + rh / 2 + 7, str(i + 1), size=20, fill="#ffffff", weight="700", anchor="middle")
        s.text(182, y + 40, title, size=21, fill=BRAND, weight="700")
        s.lines(182, y + 68, body, size=15, lh=23)
        fl = files.split("\n")
        s.lines(1052, y + rh - 22 - (len(fl) - 1) * 18, fl, size=12.5, fill=MUTED, lh=18,
                anchor="end")
        if i < len(rows) - 1:
            s.arrow(104, y + rh + 2, 104, y + rh + gap - 3, color=BRAND, sw=2.5)

    # bottom band: parallel paths that reuse the same stages
    by = y0 + len(rows) * (rh + gap) + 4
    s.text(56, by + 6, "Parallel paths that reuse the same stages", size=17, fill=BRAND, weight="700")
    cards = [
        ("Edition comparison", AMBER,
         ["The same question is put to each selected",
          "edition separately. When the values differ,",
          "both are shown with their own page citations."]),
        ("Shared answer cache", OK,
         ["An identical question to the same edition",
          "reuses the stored verified answer.",
          "A new answer is never invented from it."]),
        ("Supplementary source", SUPP,
         ["Optional self-written notes, shown in their",
          "own labelled block. Never mixed into the",
          "textbook answer."]),
    ]
    cw, cg = 366, 15
    for i, (t, accent, body) in enumerate(cards):
        cx = 56 + i * (cw + cg)
        s.card(cx, by + 24, cw, 128, accent=accent)
        s.text(cx + 26, by + 58, t, size=16, fill=BRAND, weight="700")
        s.lines(cx + 26, by + 84, body, size=13, lh=19)

    # data + runtime footer
    fy = by + 178
    s.rect(56, fy, 1128, 104, fill=AMBER_L, stroke=LINE, rx=14)
    s.text(84, fy + 34, "Data", size=14, fill=BRAND, weight="700")
    s.text(148, fy + 34, "SQLite · text_chunks, vocabulary, textbook_editions, answer_cache, usage_events",
           size=14, fill=INK)
    s.text(84, fy + 62, "Runtime", size=14, fill=BRAND, weight="700")
    s.text(168, fy + 62, "one Python process, standard library only (http.server) · browser is a plain PWA shell",
           size=14, fill=INK)
    s.text(84, fy + 88, "Boundary", size=14, fill=BRAND, weight="700")
    s.text(176, fy + 88, "the textbook text is read-only at answer time; nothing is generated from outside it",
           size=14, fill=INK)
    return s.render(DEFS)


# ---------------------------------------------------------------- 2. workflow / outcomes
def workflow() -> str:
    W, H = 1240, 1104
    s = Svg(W, H, "GRANTH-AI question lifecycle and outcomes",
            "How one question flows through validation and which of four visible outcomes the student gets: "
            "a verified answer, a partially supported answer, a refusal, or an edition conflict.")
    header(s, "GRANTH-AI · One Question, Four Honest Outcomes",
           "The same pipeline can only end in one of these states — a guess is not one of them.", W)

    steps = [
        ("1  Question", ["typed · voice · photo"]),
        ("2  Understand", ["language, words, question form", "negation, assumed premise"]),
        ("3  Retrieve", ["BM25 + trigram + coverage", "inside the chosen edition"]),
        ("4  Validate", ["concept + aspect + numbers", "polarity must agree"]),
    ]
    cw, gapx, top = 250, 40, 172
    for i, (t, body) in enumerate(steps):
        cx = 56 + i * (cw + gapx)
        s.card(cx, top, cw, 112, accent=AMBER if i % 2 else BRAND)
        s.text(cx + 22, top + 38, t, size=19, fill=BRAND, weight="700")
        s.lines(cx + 22, top + 66, body, size=13, lh=19)
        if i < 3:
            s.arrow(cx + cw + 6, top + 56, cx + cw + gapx - 8, top + 56)
    s.arrow(616, top + 116, 616, top + 140, color=BRAND)

    # decision node
    dy = top + 144
    s.rect(56, dy, 1128, 74, fill="#fff7e6", stroke=AMBER, rx=14, sw=2)
    s.text(84, dy + 46, "Decision", size=18, fill=BRAND, weight="700")
    s.text(200, dy + 46, "Is there a sentence in this edition that answers exactly what was asked, "
                         "and is it safe to show it?", size=16, fill=INK)

    outs = [
        ("Verified against source", OK, "answer",
         ["The sentence contains the asked concept and the asked aspect.",
          "Numbers and units match the printed page. The student sees the",
          "quotation itself with the chapter, the page and a link to it."]),
        ("Partially supported", WARN, "answer",
         ["The answer rests on a word that had to be matched loosely — a",
          "synonym, a spelling variant or a transliteration. The card names",
          "the book word that was used instead of the student's word."]),
        ("Insufficient evidence", BAD, "refusal",
         ["One fixed Gujarati refusal sentence, no invented content and no",
          "page citation. The app reports which words were not found and",
          "suggests checking the spelling, chapter or textbook."]),
        ("Edition conflict", SUPP, "conflict",
         ["Two selected editions disagree (for example 220 V and 230 V).",
          "Both values are shown side by side, each with its own page",
          "citation. The app does not decide which edition is right."]),
    ]
    # one arrow into the outcomes group, so no connector ever crosses a card
    s.arrow(620, dy + 76, 620, dy + 96, color=BRAND)
    s.rect(452, dy + 98, 336, 30, fill=BRAND, stroke=BRAND, rx=15)
    s.text(620, dy + 118, "FOUR POSSIBLE OUTCOMES · status field", size=12.5, fill="#ffffff",
           weight="700", anchor="middle", spacing="0.6")

    ow, oh, gx, gy = 552, 168, 24, 22
    oy = dy + 146
    for i, (t, col, kind, body) in enumerate(outs):
        ox = 56 + (i % 2) * (ow + gx)
        cy = oy + (i // 2) * (oh + gy)
        s.card(ox, cy, ow, oh, accent=col)
        s.text(ox + 26, cy + 40, t, size=19, fill=col, weight="700")
        s.lines(ox + 26, cy + 70, body, size=14, lh=22)
        s.rect(ox + 26, cy + oh - 48, 214, 30, fill="#ffffff", stroke=col, rx=9, sw=1.2)
        s.text(ox + 40, cy + oh - 27, f'status = "{kind}"', size=13, fill=col, family=MONO)

    ly = oy + 2 * oh + gy + 30
    s.rect(56, ly, 1128, 162, fill="#fdf3f3", stroke="#e7c6c6", rx=14)
    s.text(84, ly + 40, "What is deliberately not produced", size=18, fill=BAD, weight="700")
    s.lines(84, ly + 70, [
        "No answer assembled from world knowledge. No percentage \"confidence\" score.",
        "No paraphrase presented as textbook wording. No silent replacement of an unknown technical word.",
        "An answer that cannot be traced to one sentence of the selected edition is refused, not guessed —",
        "0 wrong answers and 0 false \"Verified\" labels on the frozen evaluation set.",
    ], size=14, lh=24, fill=INK)
    return s.render(DEFS)


# ---------------------------------------------------------------- 3. social preview
def social() -> str:
    W, H = 1280, 640
    s = Svg(W, H, "GRANTH-AI — Textbook-Grounded AI Learning Assistant",
            "GRANTH-AI learns from the textbook: ask naturally in Gujarati, English or mixed language and "
            "get an answer taken from the book with a chapter and page citation, or an explicit refusal.")
    s.rect(0, 0, W, H, fill="url(#brand)", stroke=BRAND_D, rx=0, sw=0)
    # soft rings, knowledge pathways
    s.parts.append(
        f'<circle cx="1090" cy="120" r="230" fill="none" stroke="#ffffff" stroke-opacity="0.10" stroke-width="2"/>'
        f'<circle cx="1090" cy="120" r="330" fill="none" stroke="#ffffff" stroke-opacity="0.07" stroke-width="2"/>'
        f'<circle cx="1090" cy="120" r="430" fill="none" stroke="#ffffff" stroke-opacity="0.05" stroke-width="2"/>')
    # mark (same geometry as granth-ai-logo.svg, scaled into place)
    s.parts.append('<g transform="translate(72 132) scale(0.62)">')
    s.parts.append('<rect x="0" y="0" width="512" height="512" rx="104" fill="#fffaf3" fill-opacity="0.13"/>')
    s.parts.append('<path d="M92 190c46-22 96-22 138 6v176c-42-28-92-28-138-6z" fill="#fffaf3"/>')
    s.parts.append('<path d="M420 190c-46-22-96-22-138 6v176c42-28 92-28 138-6z" fill="#fff6ea"/>')
    s.parts.append(f'<path d="M256 196v176" stroke="{BRAND_D}" stroke-width="10" stroke-linecap="round"/>')
    s.parts.append(f'<g stroke="{AMBER}" stroke-width="11" stroke-linecap="round"><path d="M122 234h80"/>'
                   f'<path d="M122 264h80"/><path d="M122 294h62"/></g>')
    s.parts.append(f'<path d="M300 322c24 0 26-44 52-44s26-48 50-48" fill="none" stroke="{AMBER}" '
                   f'stroke-width="10" stroke-linecap="round" stroke-dasharray="1 20"/>')
    s.parts.append(f'<circle cx="300" cy="322" r="16" fill="#fff6ea" stroke="{AMBER}" stroke-width="9"/>')
    s.parts.append(f'<circle cx="348" cy="278" r="13" fill="{AMBER}"/>')
    s.parts.append(f'<circle cx="398" cy="232" r="25" fill="url(#amber)" stroke="#fff6ea" stroke-width="6"/>')
    s.parts.append('<path d="M386 232l9 10 17-19" fill="none" stroke="#fffaf3" stroke-width="10" '
                   'stroke-linecap="round" stroke-linejoin="round"/>')
    s.parts.append('</g>')

    s.text(430, 208, "GRANTH-AI", size=72, fill="#ffffff", weight="700", spacing="1")
    s.text(434, 256, "Textbook-Grounded AI Learning Assistant", size=27, fill="#f6d9bd", weight="500")
    s.text(434, 336, "Learn from textbooks.", size=25, fill="#ffffff", weight="600")
    s.text(434, 372, "Ask naturally.", size=25, fill="#ffffff", weight="600")
    s.text(434, 408, "Understand with evidence.", size=25, fill="#ffffff", weight="600")
    s.parts.append(f'<rect x="434" y="446" width="120" height="4" rx="2" fill="{AMBER}"/>')
    s.text(434, 500, "DIVYESH BAMBHANIYA", size=22, fill="#ffffff", weight="700", spacing="2.2")
    s.text(434, 526, "Founder & Project Developer", size=15, fill="#f6d9bd")
    s.text(434, 560, "Idea contributor: Bhaveshbhai Solanki", size=15, fill="#f6d9bd")
    s.parts.append('<rect x="0" y="596" width="1280" height="44" fill="#000000" fill-opacity="0.22"/>')
    s.text(72, 624, "DEMO / RESEARCH PROTOTYPE · answers only from the approved textbook · "
                    "refuses when evidence is insufficient", size=14, fill="#ffe9d2")
    return s.render(DEFS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed files differ")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    targets = {
        "granth-ai-architecture.svg": architecture(),
        "granth-ai-workflow.svg": workflow(),
        "granth-ai-social-preview.svg": social(),
    }
    stale = []
    for name, svg in targets.items():
        path = OUT / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != svg:
                stale.append(name)
        else:
            path.write_text(svg, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)} ({len(svg)} bytes)")
    if args.check and stale:
        print("out of date: " + ", ".join(stale), file=sys.stderr)
        return 1
    if args.check:
        print("visual assets up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
