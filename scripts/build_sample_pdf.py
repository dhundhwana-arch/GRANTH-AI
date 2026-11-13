#!/usr/bin/env python3
"""Render a project-authored sample book (content.txt) to a real PDF with shaped Gujarati text.

The PDF is a *test fixture* for the PDF/OCR ingestion route: one source page -> one PDF page, so the
verified source text is page-aligned ground truth for extraction-accuracy / CER measurement.
PDFs are written to var/sample_pdfs/ and are never committed.
"""
import html
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from granth.structure import split_marked_pages, CHAPTER_RE, SECTION_RE  # noqa: E402

CSS = """
@font-face{font-family:guj;src:url(NotoSansGujarati-400.ttf);}
@font-face{font-family:guj;font-weight:bold;src:url(NotoSansGujarati-700.ttf);}
body{font-family:guj;font-size:11.5pt;line-height:1.5}
h1{font-size:18pt;margin:0 0 8pt 0} h2{font-size:14pt;margin:10pt 0 4pt 0}
p{margin:0 0 8pt 0} table{border-collapse:collapse;margin:4pt 0 8pt 0}
td{border:1px solid #333;padding:3pt 8pt}
"""


def page_html(text: str) -> str:
    out, rows = [], []

    def flush_rows():
        if rows:
            out.append("<table>" + "".join(
                "<tr>" + "".join(f"<td>{html.escape(c.strip())}</td>" for c in r.strip().strip("|").split("|")) + "</tr>"
                for r in rows) + "</table>")
            rows.clear()

    for block in text.split("\n\n"):
        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("|"):
                rows.append(line)
                continue
            flush_rows()
            if CHAPTER_RE.match(line):
                out.append(f"<h1>{html.escape(line)}</h1>")
            elif SECTION_RE.match(line) and not line.endswith("."):
                out.append(f"<h2>{html.escape(line)}</h2>")
            elif line == "શબ્દાર્થ":
                out.append(f"<h2>{html.escape(line)}</h2>")
            else:
                out.append(f"<p>{html.escape(line)}</p>")
        flush_rows()
        out.append("<p>&#160;</p>" if False else "")
    return "".join(out)


def build(book_dir: Path, out_path: Path) -> Path:
    pages = split_marked_pages((book_dir / "content.txt").read_text(encoding="utf-8"))
    arch = pymupdf.Archive(str(ROOT / "web" / "fonts"))
    doc = pymupdf.open()
    for no, text in pages:
        page = doc.new_page(width=595, height=842)
        spare, scale = page.insert_htmlbox(pymupdf.Rect(56, 50, 539, 780), page_html(text), css=CSS, archive=arch)
        if spare < 0:
            raise RuntimeError(f"page {no} content does not fit")
        page.insert_text((290, 815), str(no), fontsize=10)
    doc.set_metadata({"title": book_dir.name, "author": "GRANTH-AI sample material (CC BY 4.0)"})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path


if __name__ == "__main__":
    out_dir = ROOT / "var" / "sample_pdfs"
    for d in sorted((ROOT / "data" / "sample").iterdir()):
        if (d / "content.txt").exists():
            print(build(d, out_dir / f"{d.name}.pdf"))
