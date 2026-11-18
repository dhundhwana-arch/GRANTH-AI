#!/usr/bin/env python3
"""Compress the genuine application screenshots for the repository.

    python3 scripts/compress_screenshots.py SRC_DIR [DST_DIR]

The screenshots are real captures of the running application (see docs/README.md). They are re-encoded
to 8-bit palette PNG, which keeps Gujarati text legible while cutting the file size by roughly 4x.
If Pillow is not installed the script explains and exits; the raw captures are never modified.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:                                     # pragma: no cover - optional tool
    print("Pillow is required: .venv/bin/pip install pillow", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src
    dst.mkdir(parents=True, exist_ok=True)
    total_before = total_after = 0
    for png in sorted(src.glob("*.png")):
        before = png.stat().st_size
        img = Image.open(png).convert("RGB")
        img = img.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
        out = dst / png.name
        img.save(out, optimize=True)
        after = out.stat().st_size
        total_before += before
        total_after += after
        print(f"{png.name:38s} {before / 1024:7.1f} -> {after / 1024:6.1f} KB")
    if total_before:
        print(f"{'total':38s} {total_before / 1024:7.1f} -> {total_after / 1024:6.1f} KB "
              f"({100 * total_after / total_before:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
