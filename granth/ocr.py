"""OCR adapter interface.

Selected engine (after measuring real Gujarati output, see docs/GUJARATI_OCR_REPORT.md):
tesseract.js (Tesseract LSTM compiled to WebAssembly) with the ``guj`` + ``eng`` models. The same engine
and the same model files run (a) in Node for PDF ingestion and (b) in the student's browser for camera questions,
so no image ever needs to leave the device.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT


@dataclass
class OcrResult:
    text: str
    confidence: float      # 0..1 as reported by the engine
    engine: str


class OcrUnavailable(RuntimeError):
    pass


class OcrAdapter:
    name = "abstract"

    def available(self) -> tuple[bool, str]:
        raise NotImplementedError

    def recognize(self, image_paths: list[str], langs: str = "guj+eng") -> list[OcrResult]:
        raise NotImplementedError


class TesseractJsAdapter(OcrAdapter):
    """Runs scripts/ocr_cli.mjs (tesseract.js) in a Node subprocess. Fully local."""
    name = "tesseract.js"

    def __init__(self, root: Path = ROOT, timeout: int = 600):
        self.root, self.timeout = Path(root), timeout
        self.cli = self.root / "scripts" / "ocr_cli.mjs"
        self.langdir = self.root / "web" / "vendor" / "tessdata"

    def available(self):
        if not shutil.which("node"):
            return False, "node executable not found"
        if not (self.root / "node_modules" / "tesseract.js").exists():
            return False, "tesseract.js not installed (run: npm install)"
        if not (self.langdir / "guj.traineddata.gz").exists():
            return False, "Gujarati model missing (run: python scripts/setup_vendor.py)"
        return True, "ok"

    def recognize(self, image_paths, langs="guj+eng"):
        ok, why = self.available()
        if not ok:
            raise OcrUnavailable(why)
        proc = subprocess.run(["node", str(self.cli), "--langs", langs, "--langpath", str(self.langdir), *image_paths],
                              capture_output=True, text=True, timeout=self.timeout, cwd=str(self.root))
        if proc.returncode != 0:
            raise OcrUnavailable(f"ocr_cli failed ({proc.returncode}): {proc.stderr.strip()[:300]}")
        data = json.loads(proc.stdout)
        return [OcrResult(r["text"], float(r["confidence"]) / 100.0, self.name) for r in data["results"]]


class TesseractCliAdapter(OcrAdapter):
    """Native ``tesseract`` binary, if the host has it with the Gujarati model. Not installed in the build sandbox."""
    name = "tesseract-cli"

    def available(self):
        exe = shutil.which("tesseract")
        if not exe:
            return False, "tesseract binary not found"
        try:
            langs = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20).stdout
        except Exception as e:  # pragma: no cover
            return False, str(e)
        return ("guj" in langs.split(), "ok" if "guj" in langs.split() else "guj language pack missing")

    def recognize(self, image_paths, langs="guj+eng"):
        ok, why = self.available()
        if not ok:
            raise OcrUnavailable(why)
        out = []
        for p in image_paths:
            proc = subprocess.run(["tesseract", p, "stdout", "-l", langs], capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                raise OcrUnavailable(proc.stderr[:300])
            out.append(OcrResult(proc.stdout, 0.0, self.name))  # CLI text mode gives no confidence
        return out


def get_default_adapter() -> OcrAdapter | None:
    for a in (TesseractJsAdapter(), TesseractCliAdapter()):
        if a.available()[0]:
            return a
    return None


def adapter_status() -> list[dict]:
    return [{"engine": a.name, "available": a.available()[0], "detail": a.available()[1]}
            for a in (TesseractJsAdapter(), TesseractCliAdapter())]
