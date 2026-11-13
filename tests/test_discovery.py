from granth import db, discovery

# Synthetic catalogue HTML written for this test. It is NOT a copy of any real portal page.
FIXTURE = """
<html><body>
 <a href="/assets/std10/science_guj.pdf">ધોરણ 10 વિજ્ઞાન (ગુજરાતી માધ્યમ) 2025-26</a>
 <a href="files/Std-9 Maths Gujarati Medium.pdf">Std-9 Mathematics Gujarati Medium</a>
 <a href="/about.html">About</a>
 <a href="javascript:void(0)">menu</a>
 <a href="/assets/std10/science_guj.pdf">duplicate link</a>
 <a href="https://other.example/x.PDF">ધોરણ ૧૨ રસાયણવિજ્ઞાન</a>
</body></html>
"""


def test_parse_catalogue_extracts_pdf_links_with_guessed_metadata():
    books = discovery.parse_catalogue(FIXTURE, "https://portal.example/Home/Std9to12")
    assert [b["url"] for b in books] == ["https://portal.example/assets/std10/science_guj.pdf",
                                         "https://portal.example/Home/files/Std-9 Maths Gujarati Medium.pdf",
                                         "https://other.example/x.PDF"]
    assert (books[0]["standard"], books[0]["subject"], books[0]["medium"], books[0]["academic_year"]) == (10, "વિજ્ઞાન", "ગુજરાતી", "2025-26")
    assert (books[1]["standard"], books[1]["subject"], books[1]["medium"]) == (9, "ગણિત", "ગુજરાતી")
    assert (books[2]["standard"], books[2]["subject"]) == (12, "રસાયણવિજ્ઞાન")
    assert all(b["metadata_is_guess"] for b in books)


def test_discovered_books_inherit_permission_and_are_never_downloaded(tmp_path):
    con = db.connect(tmp_path / "d.sqlite3")
    src = [{"id": "x", "name": "Example Board", "catalogue_urls": ["https://portal.example/c"],
            "permission_status": "UNKNOWN", "permission_basis": "test"}]
    rep = discovery.run_discovery(con, fetch=lambda url: FIXTURE, write=False, sources=src)
    books = rep["sources"][0]["books"]
    assert len(books) == 3 and all(b["permission_status"] == "UNKNOWN" and not b["downloaded"] and not b["ingested"] for b in books)
    row = con.execute("SELECT p.status FROM textbook_sources s JOIN source_permissions p ON p.source_id=s.id WHERE s.name='Example Board'").fetchone()
    assert row["status"] == "UNKNOWN"
    assert con.execute("SELECT COUNT(*) FROM text_chunks").fetchone()[0] == 0


def test_official_sources_have_conservative_permission_status():
    st = {s["id"]: s["permission_status"] for s in discovery.SOURCES}
    assert st == {"gsstb": "UNKNOWN", "ncert": "PROHIBITED", "diksha": "UNKNOWN"}


def test_unreachable_or_disallowed_robots_means_no_fetch(monkeypatch):
    monkeypatch.setattr(discovery, "robots_allows", lambda url, timeout=10: ("DISALLOWED", "robots.txt disallows this path"))
    rep = discovery.discover_source(discovery.SOURCES[0])
    assert rep["catalogues"][0]["fetch_status"] == "SKIPPED" and rep["books"] == []
