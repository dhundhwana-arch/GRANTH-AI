"""Turn page texts into chapters / sections / typed chunks, preserving page numbers.

The same structurer is used for every extraction route (verified source text, PDF text layer, OCR),
so page references are produced by exactly one piece of code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .gujarati import normalize_text, split_sentences

CHAPTER_RE = re.compile(r"^(?:#\s*)?પ્રકરણ\s*[:\-]?\s*(\d+)\s*[:.\-–—]\s*(\S.*)$")
SECTION_RE = re.compile(r"^(\d{1,2}\.\d{1,2})\s+(\S.{0,90})$")
TABLE_CAPTION_RE = re.compile(r"^કોષ્ટક\s*\d+(\.\d+)?")
FORMULA_RE = re.compile(r"^સૂત્ર\s*[:\-]\s*(\S.*)$")
FIGURE_RE = re.compile(r"^\[?\s*આકૃતિ\s*\d+(\.\d+)?\s*[:\-]?.*$")
EXAMPLE_RE = re.compile(r"^ઉદાહરણ\s*[:\-]")
GLOSSARY_HEAD_RE = re.compile(r"^શબ્દાર્થ\s*:?$")
GLOSSARY_LINE_RE = re.compile(r"^(\S.{0,40}?)\s+[—–\-:]\s+(\S.*)$")
PAGE_MARK_RE = re.compile(r"^===\s*પૃષ્ઠ\s*(\d+)\s*===\s*$", re.M)
MAX_CHUNK_CHARS = 700


@dataclass
class Chunk:
    page: int
    kind: str
    text: str
    chapter: int | None = None
    section: str | None = None


@dataclass
class Section:
    number: str
    title: str
    page_start: int


@dataclass
class Chapter:
    number: int
    title: str
    page_start: int
    page_end: int
    sections: list[Section] = field(default_factory=list)


@dataclass
class Structure:
    chapters: list[Chapter]
    chunks: list[Chunk]


def split_marked_pages(text: str) -> list[tuple[int, str]]:
    """Split a verified source text on '=== પૃષ્ઠ N ===' markers."""
    parts = PAGE_MARK_RE.split(text)
    pages = []
    for i in range(1, len(parts), 2):
        pages.append((int(parts[i]), normalize_text(parts[i + 1])))
    if not pages:
        raise ValueError("no page markers found")
    nums = [n for n, _ in pages]
    if len(set(nums)) != len(nums):
        raise ValueError("duplicate page numbers in source")
    return pages


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    out, buf = [], ""
    for s in split_sentences(text):
        if buf and len(buf) + len(s) + 1 > MAX_CHUNK_CHARS:
            out.append(buf)
            buf = s
        else:
            buf = (buf + " " + s).strip()
    if buf:
        out.append(buf)
    return out


def structure_pages(pages: list[tuple[int, str]]) -> Structure:
    chapters: list[Chapter] = []
    chunks: list[Chunk] = []
    cur_ch: Chapter | None = None
    cur_sec: Section | None = None

    def emit(page, kind, text):
        text = normalize_text(text)
        if text:
            chunks.append(Chunk(page, kind, text, cur_ch.number if cur_ch else None,
                                cur_sec.number if cur_sec else None))

    for page_no, text in pages:
        lines = normalize_text(text).split("\n")
        para: list[str] = []
        table: list[str] = []
        in_glossary = False

        def flush():
            nonlocal para, table
            if table:
                emit(page_no, "table", "\n".join(table))
                table = []
            if para:
                joined = " ".join(para)
                kind = "example" if EXAMPLE_RE.match(joined) else "paragraph"
                for piece in _split_long(joined):
                    emit(page_no, kind, piece)
                para = []

        for raw in lines:
            line = raw.strip()
            if not line:
                flush()
                in_glossary = False
                continue
            m = CHAPTER_RE.match(line)
            if m:
                flush()
                if cur_ch:
                    cur_ch.page_end = max(cur_ch.page_end, page_no - 1 if page_no > cur_ch.page_start else page_no)
                cur_ch = Chapter(int(m.group(1)), m.group(2).strip(), page_no, page_no)
                chapters.append(cur_ch)
                cur_sec = None
                continue
            m = SECTION_RE.match(line)
            # (a heading may directly follow prose when OCR drops blank lines, so we do not require an empty buffer)
            if m and len(line) <= 70 and not line.endswith((".", "।", ",", ":")) and (cur_ch is None or m.group(1).split(".")[0] == str(cur_ch.number)):
                flush()
                cur_sec = Section(m.group(1), m.group(2).strip(), page_no)
                if cur_ch:
                    cur_ch.sections.append(cur_sec)
                continue
            if GLOSSARY_HEAD_RE.match(line):
                flush()
                in_glossary = True
                continue
            if in_glossary:
                if GLOSSARY_LINE_RE.match(line):
                    emit(page_no, "glossary", line)
                    continue
                in_glossary = False
            if line.startswith("|"):
                if para and TABLE_CAPTION_RE.match(para[-1]):
                    table.append(para.pop())
                    if para:
                        keep, para = table, para
                        table = []
                        flush()
                        table = keep
                elif para:
                    flush()
                table.append(line)
                continue
            if table:
                flush()
            if FORMULA_RE.match(line):
                flush()
                emit(page_no, "formula", line)
                continue
            if FIGURE_RE.match(line):
                flush()
                emit(page_no, "figure", line.strip("[] "))
                continue
            para.append(line)
        flush()
        if cur_ch:
            cur_ch.page_end = max(cur_ch.page_end, page_no)
    return Structure(chapters, chunks)
