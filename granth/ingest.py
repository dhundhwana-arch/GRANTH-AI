"""Textbook ingestion: permission gate, integrity, hashing, duplicate detection, extraction
(verified source text / PDF text layer / OCR fallback), quality validation, structuring and storage."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from . import db, gujarati, structure
from .ocr import OcrAdapter, OcrUnavailable

OCR_DPI = 200


class IngestionRefused(Exception):
    """Raised when content may not be ingested (permission not APPROVED, failed integrity ...)."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def register_edition(con, meta: dict, discovery_status: str = "VERIFIED") -> int:
    """Idempotently create source / permission / subject / textbook / edition rows. Returns edition id."""
    status = meta.get("permission_status", "UNKNOWN")
    cur = con.execute("SELECT id FROM textbook_sources WHERE name=?", (meta["source_name"],)).fetchone()
    if cur:
        source_id = cur["id"]
    else:
        source_id = con.execute(
            "INSERT INTO textbook_sources(name, base_url, kind, robots_status, notes) VALUES (?,?,?,?,?)",
            (meta["source_name"], meta.get("source_base_url", meta["source_url"]),
             meta.get("source_kind", "project_sample"), "NOT_CHECKED", meta.get("permission_note"))).lastrowid
        con.execute(
            "INSERT INTO source_permissions(source_id, status, license, evidence_url, notes, reviewed_at) VALUES (?,?,?,?,?,?)",
            (source_id, status, meta.get("license"), meta.get("permission_evidence_url", meta["source_url"]),
             meta.get("permission_note"), db.now()))
    row = con.execute("SELECT id FROM subjects WHERE name_gu=?", (meta["subject"],)).fetchone()
    subject_id = row["id"] if row else con.execute(
        "INSERT INTO subjects(name_gu, name_en) VALUES (?,?)", (meta["subject"], meta.get("subject_en"))).lastrowid
    row = con.execute(
        "SELECT id FROM textbooks WHERE board=? AND medium=? AND standard=? AND subject_id=? AND title=?",
        (meta["board"], meta["medium"], meta["standard"], subject_id, meta["title"])).fetchone()
    textbook_id = row["id"] if row else con.execute(
        "INSERT INTO textbooks(source_id, board, medium, standard, subject_id, title, language) VALUES (?,?,?,?,?,?,?)",
        (source_id, meta["board"], meta["medium"], meta["standard"], subject_id, meta["title"],
         meta.get("language", "gu"))).lastrowid
    row = con.execute("SELECT id FROM textbook_editions WHERE slug=?", (meta["slug"],)).fetchone()
    if row:
        edition_id = row["id"]
    else:
        edition_id = con.execute(
            "INSERT INTO textbook_editions(textbook_id, slug, edition_label, academic_year, source_url, permission_status,"
            " license, discovery_status) VALUES (?,?,?,?,?,?,?,?)",
            (textbook_id, meta["slug"], meta["edition_label"], meta.get("academic_year"), meta["source_url"], status,
             meta.get("license"), discovery_status)).lastrowid
    con.commit()
    return edition_id


def _edition_row(con, edition_id):
    return con.execute(
        "SELECT e.*, t.board, t.medium, t.standard, t.title, s.name_gu AS subject FROM textbook_editions e "
        "JOIN textbooks t ON t.id=e.textbook_id JOIN subjects s ON s.id=t.subject_id WHERE e.id=?",
        (edition_id,)).fetchone()


def _require_authorized(con, edition_id):
    ed = _edition_row(con, edition_id)
    if ed is None:
        raise IngestionRefused("unknown edition")
    if ed["permission_status"] != "APPROVED":
        raise IngestionRefused(
            f"permission status is {ed['permission_status']} - content is not ingested until reuse permission is APPROVED")
    return ed


def store_pages(con, edition_id: int, pages: list[tuple[int, str]], method_by_page: dict, conf_by_page: dict) -> dict:
    """Replace the stored corpus of one edition atomically and bump its corpus version."""
    from . import study, cache  # local import: avoid cycles
    ed = _require_authorized(con, edition_id)
    st = structure.structure_pages(pages)
    with con:
        con.execute("DELETE FROM saved_words WHERE vocabulary_id IN (SELECT id FROM vocabulary WHERE edition_id=?)", (edition_id,))
        con.execute("DELETE FROM vocabulary WHERE edition_id=?", (edition_id,))
        con.execute("DELETE FROM text_chunks WHERE edition_id=?", (edition_id,))
        con.execute("DELETE FROM sections WHERE chapter_id IN (SELECT id FROM chapters WHERE edition_id=?)", (edition_id,))
        con.execute("DELETE FROM chapters WHERE edition_id=?", (edition_id,))
        con.execute("DELETE FROM pages WHERE edition_id=?", (edition_id,))
        for no, text in pages:
            con.execute("INSERT INTO pages(edition_id, page_number, text, extraction_method, confidence) VALUES (?,?,?,?,?)",
                        (edition_id, no, text, method_by_page[no], conf_by_page[no]))
        ch_ids, sec_ids, ch_titles, sec_titles = {}, {}, {}, {}
        for ch in st.chapters:
            cid = con.execute("INSERT INTO chapters(edition_id, number, title, page_start, page_end) VALUES (?,?,?,?,?)",
                              (edition_id, ch.number, ch.title, ch.page_start, ch.page_end)).lastrowid
            ch_ids[ch.number], ch_titles[ch.number] = cid, ch.title
            for sec in ch.sections:
                sid = con.execute("INSERT INTO sections(chapter_id, number, title, page_start) VALUES (?,?,?,?)",
                                  (cid, sec.number, sec.title, sec.page_start)).lastrowid
                sec_ids[(ch.number, sec.number)], sec_titles[(ch.number, sec.number)] = sid, f"{sec.number} {sec.title}"
        hasher = hashlib.sha256()
        for i, c in enumerate(st.chunks):
            hasher.update(c.text.encode("utf-8"))
            con.execute(
                "INSERT INTO text_chunks(edition_id, chapter_id, section_id, page_number, chunk_index, kind, text, text_sha256,"
                " extraction_confidence, board, medium, standard, subject, book_title, edition, chapter_number, chapter_title,"
                " section_title, source_url, permission_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (edition_id, ch_ids.get(c.chapter), sec_ids.get((c.chapter, c.section)), c.page, i, c.kind, c.text,
                 sha256_text(c.text), conf_by_page[c.page], ed["board"], ed["medium"], ed["standard"], ed["subject"],
                 ed["title"], ed["edition_label"], c.chapter, ch_titles.get(c.chapter),
                 sec_titles.get((c.chapter, c.section)), ed["source_url"], ed["permission_status"]))
        con.execute("UPDATE textbook_editions SET corpus_version=corpus_version+1, content_sha256=?, page_count=?, ingested_at=?"
                    " WHERE id=?", (hasher.hexdigest(), len(pages), db.now(), edition_id))
        vocab = study.build_vocabulary(con, edition_id)
        invalidated = cache.invalidate_edition(con, edition_id)
    from . import retrieval
    retrieval.invalidate_index()
    return {"pages": len(pages), "chapters": len(st.chapters), "sections": sum(len(c.sections) for c in st.chapters),
            "chunks": len(st.chunks), "vocabulary": vocab, "cache_entries_invalidated": invalidated}


def _start_job(con, edition_id, path, sha, method):
    jid = con.execute("INSERT INTO ingestion_jobs(edition_id, source_path, sha256, method, status, started_at) VALUES (?,?,?,?,?,?)",
                      (edition_id, str(path), sha, method, "running", db.now())).lastrowid
    con.commit()
    return jid


def _finish_job(con, jid, status, stats=None, error=None):
    con.execute("UPDATE ingestion_jobs SET status=?, finished_at=?, stats_json=?, error=? WHERE id=?",
                (status, db.now(), json.dumps(stats, ensure_ascii=False) if stats else None, error, jid))
    con.execute("INSERT INTO usage_events(ts, kind, detail) VALUES (?,?,?)", (db.now(), "ingestion", f"job {jid}: {status}"))
    con.commit()


def _is_duplicate(con, edition_id, sha, force):
    if force:
        return None
    return con.execute("SELECT id, slug FROM textbook_editions WHERE file_sha256=? AND ingested_at IS NOT NULL", (sha,)).fetchone()


def _record_quality(con, jid, edition_id, page_no, method, v, engine_conf, notes=None):
    con.execute(
        "INSERT INTO extraction_quality(job_id, edition_id, page_number, method, chars, gujarati_ratio, suspicious_ratio,"
        " orphan_ratio, engine_confidence, score, passed, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (jid, edition_id, page_no, method, v["chars"], v["gujarati_ratio"], v["suspicious_ratio"], v["orphan_ratio"],
         engine_conf, v["score"], int(v["passed"]), notes))


def ingest_text_source(con, book_dir: Path, force: bool = False, auto_approve: bool = False) -> dict:
    """Ingest a project-owned, human-verified text source (content.txt + book.json)."""
    book_dir = Path(book_dir)
    meta = json.loads((book_dir / "book.json").read_text(encoding="utf-8"))
    src = book_dir / "content.txt"
    edition_id = register_edition(con, meta)
    sha = sha256_file(src)
    jid = _start_job(con, edition_id, src, sha, "source-text")
    try:
        _require_authorized(con, edition_id)
        dup = _is_duplicate(con, edition_id, sha, force)
        if dup:
            _finish_job(con, jid, "duplicate", {"duplicate_of": dup["slug"]})
            return {"job_id": jid, "edition_id": edition_id, "status": "duplicate", "duplicate_of": dup["slug"]}
        pages = structure.split_marked_pages(src.read_text(encoding="utf-8"))
        methods, confs = {}, {}
        for no, text in pages:
            v = gujarati.validate_gujarati(text)
            _record_quality(con, jid, edition_id, no, "source-text", v, None)
            if not v["passed"]:
                raise IngestionRefused(f"page {no} failed Gujarati integrity validation: {v['reason']}")
            methods[no], confs[no] = "source-text", 1.0
        stats = store_pages(con, edition_id, pages, methods, confs)
        con.execute("UPDATE textbook_editions SET file_sha256=? WHERE id=?", (sha, edition_id))
        if auto_approve:
            con.execute("UPDATE textbook_editions SET review_status='approved', reviewed_by=?, reviewed_at=? WHERE id=?",
                        ("seed-script (project-authored sample material)", db.now(), edition_id))
        _finish_job(con, jid, "completed", stats)
        from . import retrieval
        retrieval.invalidate_index()
        return {"job_id": jid, "edition_id": edition_id, "status": "completed", **stats}
    except IngestionRefused as e:
        _finish_job(con, jid, "refused", error=str(e))
        raise
    except Exception as e:
        _finish_job(con, jid, "failed", error=repr(e))
        raise


def check_pdf_integrity(path: Path) -> dict:
    """Header / parse / encryption / page-count checks. Raises IngestionRefused when unusable."""
    import pymupdf
    path = Path(path)
    if not path.is_file() or path.stat().st_size < 100:
        raise IngestionRefused("file missing or too small to be a PDF")
    with open(path, "rb") as f:
        if not f.read(1024).lstrip().startswith(b"%PDF-"):
            raise IngestionRefused("not a PDF (missing %PDF- header)")
    try:
        doc = pymupdf.open(str(path))
    except Exception as e:
        raise IngestionRefused(f"PDF cannot be parsed: {e}") from e
    try:
        if doc.needs_pass:
            raise IngestionRefused("PDF is password protected - access controls are never bypassed")
        if doc.page_count == 0:
            raise IngestionRefused("PDF has no pages")
        return {"pages": doc.page_count, "size_bytes": path.stat().st_size, "metadata": doc.metadata or {}}
    finally:
        doc.close()


def extract_pdf_pages(path: Path, ocr: OcrAdapter | None, first_page_number: int = 1) -> list[dict]:
    """Per page: try the embedded text layer; if it fails Gujarati integrity validation, fall back to OCR."""
    import pymupdf
    doc = pymupdf.open(str(path))
    results, need_ocr = [], []
    try:
        for i, page in enumerate(doc):
            text = gujarati.normalize_text(page.get_text("text"))
            v = gujarati.validate_gujarati(text)
            rec = {"page": first_page_number + i, "text_layer": text, "text_layer_quality": v, "tables": 0,
                   "method": "pdf-text-layer", "text": text, "quality": v, "engine_confidence": None}
            try:
                rec["tables"] = len(page.find_tables().tables)
            except Exception:
                pass
            if not v["passed"]:
                need_ocr.append((i, rec))
            results.append(rec)
        if need_ocr:
            if ocr is None:
                for _, rec in need_ocr:
                    rec.update(method="failed", text="", notes="text layer rejected and no OCR engine available")
            else:
                with tempfile.TemporaryDirectory(prefix="granth-ocr-") as tmp:
                    paths = []
                    for i, _ in need_ocr:
                        p = Path(tmp) / f"p{i:04d}.png"
                        doc[i].get_pixmap(dpi=OCR_DPI).save(str(p))
                        paths.append(str(p))
                    try:
                        outs = ocr.recognize(paths)
                    except OcrUnavailable as e:
                        outs = None
                        for _, rec in need_ocr:
                            rec.update(method="failed", text="", notes=f"OCR failed: {e}")
                    if outs:
                        for (_, rec), o in zip(need_ocr, outs):
                            t = clean_ocr_text(o.text, rec["page"])
                            q = gujarati.validate_gujarati(t)
                            rec.update(method=f"ocr:{o.engine}", text=t, quality=q, engine_confidence=o.confidence)
                            if not q["passed"]:
                                rec["notes"] = "OCR output failed integrity validation"
    finally:
        doc.close()
    return results


def clean_ocr_text(text: str, page_number: int | None = None) -> str:
    """Remove a trailing bare page-number line and normalise."""
    lines = gujarati.normalize_text(text).split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and page_number is not None and lines[-1].strip() in (str(page_number), str(page_number).translate(
            {ord(str(i)): c for i, c in enumerate("૦૧૨૩૪૫૬૭૮૯")})):
        lines.pop()
    return "\n".join(lines).strip()


def ingest_pdf(con, pdf_path: Path, meta: dict, ocr: OcrAdapter | None = None, force: bool = False,
               min_confidence: float = 0.6) -> dict:
    """Full PDF route. Editions ingested from PDFs start as review_status='pending' (admin must approve)."""
    pdf_path = Path(pdf_path)
    sha = sha256_file(pdf_path) if pdf_path.is_file() else None
    if sha and not force:
        dup = _is_duplicate(con, None, sha, force)       # same file already ingested (under any slug)?
        if dup:
            jid = _start_job(con, None, pdf_path, sha, "pdf")
            _finish_job(con, jid, "duplicate", {"duplicate_of": dup["slug"]})
            return {"job_id": jid, "edition_id": dup["id"], "status": "duplicate", "duplicate_of": dup["slug"]}
    edition_id = register_edition(con, meta)
    jid = _start_job(con, edition_id, pdf_path, sha, "pdf")
    try:
        _require_authorized(con, edition_id)
        info = check_pdf_integrity(pdf_path)
        dup = _is_duplicate(con, edition_id, sha, force)
        if dup:
            _finish_job(con, jid, "duplicate", {"duplicate_of": dup["slug"]})
            return {"job_id": jid, "edition_id": edition_id, "status": "duplicate", "duplicate_of": dup["slug"]}
        recs = extract_pdf_pages(pdf_path, ocr)
        pages, methods, confs, failed = [], {}, {}, []
        for r in recs:
            conf = r["quality"]["score"] * (r["engine_confidence"] if r["engine_confidence"] is not None else 1.0)
            _record_quality(con, jid, edition_id, r["page"], r["method"], r["quality"], r["engine_confidence"], r.get("notes"))
            if r["method"] == "failed" or not r["quality"]["passed"] or conf < min_confidence:
                failed.append(r["page"])
                continue
            pages.append((r["page"], r["text"]))
            methods[r["page"]], confs[r["page"]] = r["method"], round(conf, 4)
        stats = {"pdf": info, "pages_total": len(recs), "pages_failed": failed,
                 "methods": {m: sum(1 for r in recs if r["method"] == m) for m in {r["method"] for r in recs}}}
        if failed:
            _finish_job(con, jid, "failed", stats, f"{len(failed)} page(s) could not be extracted reliably; nothing stored")
            return {"job_id": jid, "edition_id": edition_id, "status": "failed", **stats}
        stats.update(store_pages(con, edition_id, pages, methods, confs))
        con.execute("UPDATE textbook_editions SET file_sha256=? WHERE id=?", (sha, edition_id))
        _finish_job(con, jid, "completed", stats)
        return {"job_id": jid, "edition_id": edition_id, "status": "completed", **stats}
    except IngestionRefused as e:
        _finish_job(con, jid, "refused", error=str(e))
        raise
    except Exception as e:
        _finish_job(con, jid, "failed", error=repr(e))
        raise
