import json

import pytest

from granth import answer, db, ingest, structure
from conftest import SAMPLE, ROOT


def test_structure_preserves_pages_chapters_sections(con, ids):
    chs = con.execute("SELECT number, title, page_start, page_end FROM chapters WHERE edition_id=? ORDER BY number",
                      (ids["sci"],)).fetchall()
    assert [(c["number"], c["page_start"], c["page_end"]) for c in chs] == [(1, 1, 2), (2, 3, 4), (3, 5, 6), (4, 7, 8), (5, 9, 10)]
    assert chs[0]["title"] == "સજીવોમાં પોષણ"
    kinds = {r[0] for r in con.execute("SELECT DISTINCT kind FROM text_chunks WHERE edition_id=?", (ids["sci"],))}
    assert {"paragraph", "table", "formula", "figure", "glossary", "example"} <= kinds


def test_every_chunk_is_self_describing_and_on_its_source_page(con, ids):
    pages = dict(structure.split_marked_pages((SAMPLE / "granth_vigyan_10_2026" / "content.txt").read_text(encoding="utf-8")))
    rows = con.execute("SELECT * FROM text_chunks WHERE edition_id=?", (ids["sci"],)).fetchall()
    assert len(rows) > 50
    for r in rows:
        for col in ("board", "medium", "standard", "subject", "book_title", "edition", "chapter_title", "page_number",
                    "source_url", "permission_status", "text", "extraction_confidence"):
            assert r[col] not in (None, ""), col
        first_line = r["text"].split("\n")[0].strip("| ")
        flat = " ".join(pages[r["page_number"]].split())
        assert " ".join(first_line.split()) in flat      # chunk text really is on the page it cites


def test_formula_and_table_text_preserved_exactly(con, ids):
    texts = [r[0] for r in con.execute("SELECT text FROM text_chunks WHERE edition_id=? AND kind='formula'", (ids["sci"],))]
    assert "સૂત્ર: V = I × R" in texts and "સૂત્ર: 6CO2 + 6H2O → C6H12O6 + 6O2" in texts
    t = con.execute("SELECT text FROM text_chunks WHERE edition_id=? AND kind='table' AND page_number=3", (ids["sci"],)).fetchone()[0]
    assert t.startswith("કોષ્ટક 2.1") and "| ઑક્સિજન | જરૂરી છે | જરૂરી નથી |" in t


def test_duplicate_source_is_detected(con):
    out = ingest.ingest_text_source(con, SAMPLE / "granth_vigyan_10_2026")
    assert out["status"] == "duplicate"
    assert con.execute("SELECT status FROM ingestion_jobs ORDER BY id DESC LIMIT 1").fetchone()[0] == "duplicate"


def test_unknown_permission_is_never_ingested(tmp_path):
    c = db.connect(tmp_path / "p.sqlite3")
    book = tmp_path / "book"
    book.mkdir()
    meta = json.loads((SAMPLE / "granth_vigyan_10_2026" / "book.json").read_text(encoding="utf-8"))
    meta.update(slug="unknown_perm", permission_status="UNKNOWN", source_name="Some Board", title="X")
    (book / "book.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (book / "content.txt").write_text((SAMPLE / "granth_vigyan_10_2026" / "content.txt").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ingest.IngestionRefused):
        ingest.ingest_text_source(c, book)
    assert c.execute("SELECT COUNT(*) FROM text_chunks").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 0
    assert c.execute("SELECT status FROM ingestion_jobs").fetchone()[0] == "refused"


def test_unapproved_edition_is_not_searchable(con, ids):
    con.execute("UPDATE textbook_editions SET review_status='pending' WHERE id=?", (ids["sci"],))
    con.commit()
    r = answer.ask(con, "પ્રકાશસંશ્લેષણ શું છે?", {"edition_id": ids["sci"]})
    assert r["status"] == "abstained" and r["reason"] == "no_authorized_textbook_in_scope"


def test_pdf_integrity_checks(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf" * 20)
    with pytest.raises(ingest.IngestionRefused):
        ingest.check_pdf_integrity(bad)
    with pytest.raises(ingest.IngestionRefused):
        ingest.check_pdf_integrity(tmp_path / "missing.pdf")
    import pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "hello")
    enc = tmp_path / "enc.pdf"
    doc.save(str(enc), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")
    with pytest.raises(ingest.IngestionRefused, match="password"):
        ingest.check_pdf_integrity(enc)


def test_reingestion_bumps_corpus_version_and_invalidates_cache(con, ids):
    scope = {"edition_id": ids["sci"]}
    assert answer.ask(con, "પ્રકાશસંશ્લેષણ શું છે?", scope)["cache"]["hit"] is False
    assert answer.ask(con, "પ્રકાશસંશ્લેષણ શું છે?", scope)["cache"]["hit"] is True
    v0 = con.execute("SELECT corpus_version FROM textbook_editions WHERE id=?", (ids["sci"],)).fetchone()[0]
    out = ingest.ingest_text_source(con, SAMPLE / "granth_vigyan_10_2026", force=True, auto_approve=True)
    assert out["cache_entries_invalidated"] >= 1
    assert con.execute("SELECT corpus_version FROM textbook_editions WHERE id=?", (ids["sci"],)).fetchone()[0] == v0 + 1
    r = answer.ask(con, "પ્રકાશસંશ્લેષણ શું છે?", scope)
    assert r["cache"]["hit"] is False and r["status"] == "answered"


def test_migrations_are_portable_sql():
    for f in sorted((ROOT / "granth" / "migrations").glob("*.sql")):
        raw = f.read_text(encoding="utf-8")
        sql = "\n".join(line.split("--")[0] for line in raw.splitlines()).upper()
        for sqlite_only in ("AUTOINCREMENT", "VIRTUAL TABLE", "WITHOUT ROWID", "PRAGMA"):
            assert sqlite_only not in sql, (f.name, sqlite_only)


def test_migration_002_upgrades_an_existing_database(tmp_path):
    """A database created by the first release (AUTHORIZED / PROHIBITED vocabulary) is upgraded without data loss."""
    import sqlite3
    from granth import db
    p = tmp_path / "old.sqlite3"
    c = sqlite3.connect(p)
    c.executescript((ROOT / "granth" / "migrations" / "001_initial.sql").read_text(encoding="utf-8"))
    c.execute("CREATE TABLE schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    c.execute("INSERT INTO schema_migrations VALUES ('001_initial.sql', 'x')")
    c.execute("INSERT INTO textbook_sources(id, name, base_url, kind) VALUES (1, 's', 'u', 'k')")
    c.execute("INSERT INTO source_permissions(source_id, status) VALUES (1, 'PROHIBITED')")
    c.execute("INSERT INTO subjects(id, name_gu) VALUES (1, 'વિજ્ઞાન')")
    c.execute("INSERT INTO textbooks(id, source_id, board, medium, standard, subject_id, title, language) VALUES (1,1,'b','m',10,1,'t','gu')")
    c.execute("INSERT INTO textbook_editions(id, textbook_id, slug, edition_label, source_url, permission_status, review_status, page_count)"
              " VALUES (5, 1, 'old', '2026', 'u', 'AUTHORIZED', 'approved', 3)")
    c.commit(); c.close()
    con = db.connect(p)
    ed = con.execute("SELECT * FROM textbook_editions WHERE id=5").fetchone()
    assert (ed["permission_status"], ed["review_status"], ed["page_count"], ed["role"]) == ("APPROVED", "approved", 3, "textbook")
    assert con.execute("SELECT status FROM source_permissions").fetchone()[0] == "DENIED"
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    con.close()
