#!/usr/bin/env python3
"""Copy browser OCR assets from node_modules into web/vendor (git-ignored, ~25 MB).

Run after ``npm install``. Nothing is downloaded from the network by this script.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NM = ROOT / "node_modules"
OUT = ROOT / "web" / "vendor"

FILES = [
    ("tesseract.js/dist/tesseract.min.js", "tesseract/tesseract.min.js"),
    ("tesseract.js/dist/worker.min.js", "tesseract/worker.min.js"),
    ("tesseract.js-core/tesseract-core-lstm.wasm.js", "tesseract/core/tesseract-core-lstm.wasm.js"),
    ("tesseract.js-core/tesseract-core-simd-lstm.wasm.js", "tesseract/core/tesseract-core-simd-lstm.wasm.js"),
    ("tesseract.js-core/tesseract-core-relaxedsimd-lstm.wasm.js", "tesseract/core/tesseract-core-relaxedsimd-lstm.wasm.js"),
    ("@tesseract.js-data/guj/4.0.0_best_int/guj.traineddata.gz", "tessdata/guj.traineddata.gz"),
    ("@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz", "tessdata/eng.traineddata.gz"),
]


def main() -> int:
    if not NM.exists():
        print("node_modules missing - run `npm install` first", file=sys.stderr)
        return 1
    missing = 0
    for src, dst in FILES:
        s, d = NM / src, OUT / dst
        if not s.exists():
            if "relaxedsimd" in src:
                continue
            print(f"MISSING {src}", file=sys.stderr)
            missing += 1
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, d)
        print(f"ok {dst} ({d.stat().st_size // 1024} KB)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
