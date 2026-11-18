#!/usr/bin/env python3
"""Check the documentation: relative links, in-page anchors, images, and that no frozen file is missing.

    python3 scripts/check_docs.py            # exit 0 when everything resolves
    python3 scripts/check_docs.py -v         # also list every link that was checked

Rules
  * every relative markdown link must point at a file that exists in the repository;
  * a link with a #fragment into another markdown file must match a heading in that file;
  * every <img src="..."> must exist;
  * the files the README cites as frozen must be present.

The script never touches the network: external http(s) links are counted, not fetched (a sandbox may have
no internet, and a link checker that fails offline is useless in CI).
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "node_modules", "vendor", "var", "__pycache__", ".pytest_cache"}
# label may contain one level of nested brackets (badges are [![alt](img)](link)),
# and a URL may contain balanced parentheses, as shields.io badge URLs do.
MD_LINK = re.compile(
    r"\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(([^()\s]*(?:\([^()\s]*\)[^()\s]*)*)(?:\s+\"[^\"]*\")?\)")
IMG_TAG = re.compile(r"<img\s+[^>]*src=[\"']([^\"']+)[\"']")
IMG_MD = re.compile(r"!\[[^\]]*\]\(([^()\s]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FROZEN = [
    "benchmarks/phase5/frozen_test.json",
    "benchmarks/phase4/frozen_test.json",
    "benchmarks/results/phase5/phase5_frozen_run1.json",
    "benchmarks/results/phase4_frozen_run1.json",
    "docs/PHASE5_REPORT.md",
    "docs/PHASE5_FROZEN_BENCHMARK.md",
    "docs/PHASE4_REPORT.md",
]


def github_slug(text: str) -> str:
    """Approximate GitHub's heading anchor: lower-case, drop markup and punctuation, spaces -> hyphens."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("*", "").replace("_", "")
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = "".join(ch for ch in text if ch.isalnum() or ch in " -_")
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = HEADING.match(line)
        if m:
            out.add(github_slug(m.group(2)))
    return out


def markdown_files() -> list[Path]:
    files = []
    for p in ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        files.append(p)
    return sorted(files)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    problems: list[str] = []
    checked = 0
    external = 0
    files = markdown_files()
    anchor_cache: dict[Path, set[str]] = {}

    for md in files:
        text = md.read_text(encoding="utf-8", errors="replace")
        targets = [(m.group(1), "link") for m in MD_LINK.finditer(text)]
        targets += [(m.group(1), "image") for m in IMG_TAG.finditer(text)]
        targets += [(m.group(1), "image") for m in IMG_MD.finditer(text)]
        for raw, kind in targets:
            target = unquote(raw.split("#", 1)[0])
            frag = raw.split("#", 1)[1] if "#" in raw else ""
            if raw.startswith(("http://", "https://", "mailto:", "tel:", "www.")) or "://" in raw:
                external += 1
                continue
            checked += 1
            if not target:                                   # pure in-page anchor
                dest = md
            else:
                dest = (md.parent / target).resolve()
                if not dest.exists():
                    problems.append(f"{md.relative_to(ROOT)}: {kind} -> missing file: {raw}")
                    continue
            if frag and dest.suffix.lower() == ".md":
                if dest not in anchor_cache:
                    anchor_cache[dest] = anchors(dest)
                if frag not in anchor_cache[dest]:
                    problems.append(f"{md.relative_to(ROOT)}: {kind} -> missing anchor: {raw}")
            elif args.verbose:
                print(f"ok {md.relative_to(ROOT)} -> {raw}")

    for rel in FROZEN:
        if not (ROOT / rel).exists():
            problems.append(f"frozen artefact missing: {rel}")

    print(f"markdown files: {len(files)}")
    print(f"relative links and images checked: {checked}")
    print(f"external links (not fetched): {external}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print("  - " + p)
        return 1
    print("all relative links, anchors and images resolve; frozen artefacts present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
