"""PDF route: real PDF with shaped Gujarati -> broken text layer detected -> OCR fallback -> measured CER.
Also Feature 2 (camera question): an image of a printed question -> OCR -> same retrieval engine."""
import json
import subprocess
import sys

import pytest

from granth import answer, db, gujarati as g, ingest, ocr, structure
from conftest import ROOT, SAMPLE, needs_ocr

SOC = SAMPLE / "granth_samajik_10_2026"


@pytest.fixture(scope="module")
def soc_pdf(tmp_path_factory):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_sample_pdf
    return build_sample_pdf.build(SOC, tmp_path_factory.mktemp("pdf") / "soc.pdf")


def meta(slug):
    m = json.loads((SOC / "book.json").read_text(encoding="utf-8"))
    m.update(slug=slug, edition_label="PDF/OCR route test")
    return m


def test_pdf_text_layer_of_shaped_gujarati_is_rejected(soc_pdf):
    recs = ingest.extract_pdf_pages(soc_pdf, ocr=None)
    assert len(recs) == 2
    for r in recs:
        assert r["text_layer_quality"]["passed"] is False and r["method"] == "failed" and r["text"] == ""


def test_without_ocr_nothing_unreliable_is_stored(soc_pdf, tmp_path):
    con = db.connect(tmp_path / "x.sqlite3")
    out = ingest.ingest_pdf(con, soc_pdf, meta("soc_pdf_noocr"), ocr=None)
    assert out["status"] == "failed" and out["pages_failed"] == [1, 2]
    assert con.execute("SELECT COUNT(*) FROM text_chunks").fetchone()[0] == 0


@needs_ocr
def test_ocr_fallback_ingests_pdf_with_page_numbers_and_measured_cer(soc_pdf, tmp_path):
    con = db.connect(tmp_path / "y.sqlite3")
    out = ingest.ingest_pdf(con, soc_pdf, meta("soc_pdf_ocr"), ocr=ocr.get_default_adapter())
    assert out["status"] == "completed" and out["methods"] == {"ocr:tesseract.js": 2}
    truth = dict(structure.split_marked_pages((SOC / "content.txt").read_text(encoding="utf-8")))
    pages = {r["page_number"]: r for r in con.execute("SELECT * FROM pages")}
    assert set(pages) == {1, 2}
    for no, row in pages.items():
        ref = truth[no].replace("|", " ")
        cer = g.cer(ref, row["text"])
        assert cer < 0.15, (no, cer)                      # measured values are in docs/GUJARATI_OCR_REPORT.md
        assert row["extraction_method"] == "ocr:tesseract.js" and 0.5 < row["confidence"] <= 1.0
    # OCR editions are NOT searchable until an administrator approves them
    eid = out["edition_id"]
    assert answer.ask(con, "જળસંચય એટલે શું?", {"edition_id": eid})["reason"] == "no_authorized_textbook_in_scope"
    con.execute("UPDATE textbook_editions SET review_status='approved' WHERE id=?", (eid,))
    con.commit()
    r = answer.ask(con, "જળસંચય એટલે શું?", {"edition_id": eid})
    assert r["status"] == "answered" and r["citations"][0]["page_number"] == 1 and r["evidence"][0]["extraction_confidence"] < 1.0
    assert r["citations"][0]["section_title"].startswith("1.2")           # section heading recovered from OCR text
    # Observed OCR error: the defining sentence of "જળચક્ર" is mis-read ("જળચક્ઠ"). The engine must then abstain
    # (or answer with a verified quote) - it must never repair or invent the sentence.
    r2 = answer.ask(con, "જળચક્ર એટલે શું?", {"edition_id": eid})
    assert r2["status"] == "abstained" or r2["verification"]["verified"]
    # duplicate detection by file hash
    assert ingest.ingest_pdf(con, soc_pdf, meta("soc_pdf_ocr_again"), ocr=ocr.get_default_adapter())["status"] == "duplicate"


def _render_question_png(text, path, rotate=0):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=120)
    css = "@font-face{font-family:guj;src:url(NotoSansGujarati-400.ttf);} body{font-family:guj;font-size:16pt}"
    page.insert_htmlbox(pymupdf.Rect(15, 15, 405, 110), f"<p>{text}</p>", css=css, archive=pymupdf.Archive(str(ROOT / "web" / "fonts")))
    if rotate:
        page.set_rotation(rotate)
    page.get_pixmap(dpi=200).save(str(path))


@needs_ocr
def test_camera_question_printed_gujarati_goes_through_same_engine(con, ids, tmp_path):
    img = tmp_path / "q.png"
    _render_question_png("હરિતદ્રવ્ય કોને કહે છે?", img)
    res = ocr.get_default_adapter().recognize([str(img)])[0]
    extracted = g.normalize_text(res.text)
    assert g.cer("હરિતદ્રવ્ય કોને કહે છે?", extracted) <= 0.1
    r = answer.ask(con, extracted, {"edition_id": ids["sci"]}, input_method="camera")
    assert r["status"] == "answered" and "હરિતદ્રવ્ય કહે છે" in r["answer"]["text"] and r["citations"][0]["page_number"] == 2
    assert con.execute("SELECT input_method FROM questions WHERE id=?", (r["question_id"],)).fetchone()[0] == "camera"


@needs_ocr
def test_camera_question_mixed_gujarati_english(con, ids, tmp_path):
    img = tmp_path / "q2.png"
    _render_question_png("pH માપક્રમ એટલે શું?", img)
    extracted = g.normalize_text(ocr.get_default_adapter().recognize([str(img)])[0].text)
    assert "ph" in extracted.lower() and "માપક્રમ" in extracted      # observed: OCR returns "PH" (case error)
    r = answer.ask(con, extracted, {"edition_id": ids["sci"]}, input_method="camera")
    assert r["status"] == "answered" and r["citations"][0]["page_number"] == 9


@needs_ocr
def test_bad_ocr_text_cannot_produce_an_answer_and_correction_fixes_it(con, ids):
    """OCR correction workflow: garbage OCR -> abstain (never answered directly) -> student edits -> answered."""
    garbage = "હરિતદ્રત્ય ક્રોતે ક્હે છૅ ?"          # typical mis-recognition, edited by hand for the test
    bad = answer.ask(con, garbage, {"edition_id": ids["sci"]}, input_method="camera")
    fixed = answer.ask(con, "હરિતદ્રવ્ય કોને કહે છે?", {"edition_id": ids["sci"]}, input_method="camera")
    assert fixed["status"] == "answered"
    if bad["status"] == "answered":      # only acceptable if fuzzy matching recovered the *same* verified textbook quote
        assert bad["answer"]["text"] == fixed["answer"]["text"] and bad["verification"]["verified"]


def test_ocr_adapter_reports_missing_dependency(tmp_path):
    a = ocr.TesseractJsAdapter(root=tmp_path)
    ok, why = a.available()
    assert ok is False and why
    with pytest.raises(ocr.OcrUnavailable):
        a.recognize(["x.png"])
