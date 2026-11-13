import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from granth import db, ingest  # noqa: E402
from granth.__main__ import seed_samples  # noqa: E402

SAMPLE = ROOT / "data" / "sample"


@pytest.fixture()
def con(tmp_path):
    c = db.connect(tmp_path / "t.sqlite3")
    seed_samples(c)
    yield c
    c.close()


@pytest.fixture()
def ids(con):
    """Edition / chapter ids of the seeded sample books."""
    ed = {r["slug"]: r["id"] for r in con.execute("SELECT slug, id FROM textbook_editions")}
    sci = ed["granth_vigyan_10_2026"]
    ch = {r["number"]: r["id"] for r in con.execute("SELECT number, id FROM chapters WHERE edition_id=?", (sci,))}
    return {"sci": sci, "sci27": ed["granth_vigyan_10_2027"], "soc": ed["granth_samajik_10_2026"], "ch": ch}


def has_ocr() -> bool:
    from granth import ocr
    return ocr.TesseractJsAdapter().available()[0]


needs_ocr = pytest.mark.skipif(not (shutil.which("node") and has_ocr()),
                               reason="tesseract.js OCR not installed (npm install && python scripts/setup_vendor.py)")
