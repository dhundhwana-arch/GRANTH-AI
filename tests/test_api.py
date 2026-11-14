import json
import threading
import urllib.error
import urllib.request

import pytest

from granth import api, db
from granth.__main__ import seed_samples


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("GRANTH_ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("GRANTH_ALLOW_WEAK_ADMIN_TOKEN", "1")       # tests only; a public deployment needs a strong token
    path = tmp_path / "api.sqlite3"
    c = db.connect(path)
    seed_samples(c)
    ed = {r["slug"]: r["id"] for r in c.execute("SELECT slug, id FROM textbook_editions")}
    c.close()
    srv = api.make_server("127.0.0.1", 0, db_path=str(path), quiet=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, url, body=None, headers=None, raw=False):
        req = urllib.request.Request(base + url, method=method, headers={"Content-Type": "application/json", **(headers or {})},
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
                return r.status, (data if raw else json.loads(data)), dict(r.headers)
        except urllib.error.HTTPError as e:
            data = e.read()
            return e.code, (data if raw else json.loads(data or b"{}")), dict(e.headers)

    yield call, ed
    srv.shutdown()
    srv.server_close()


def test_catalog_and_selection_flow(server):
    call, ed = server
    st, cat, _ = call("GET", "/api/catalog")
    assert st == 200
    book = next(b for b in cat["textbooks"] if b["subject"] == "વિજ્ઞાન")
    assert book["standard"] == 10 and book["medium"] == "ગુજરાતી" and len(book["editions"]) == 2 and book["available"]
    st, chs, _ = call("GET", f"/api/editions/{ed['granth_vigyan_10_2026']}/chapters")
    assert [c["number"] for c in chs["chapters"]] == [1, 2, 3, 4, 5] and chs["chapters"][0]["sections"][0]["number"] == "1.1"


def test_ask_answer_evidence_page_viewer_history_feedback(server):
    call, ed = server
    e = ed["granth_vigyan_10_2026"]
    st, r, _ = call("POST", "/api/ask", {"question": "પ્રકાશસંશ્લેષણ શું છે?", "edition_id": e, "session_id": "u1"})
    assert st == 200 and r["status"] == "answered" and r["citations"][0]["page_number"] == 1
    st, pg, _ = call("GET", f"/api/editions/{e}/pages/{r['citations'][0]['page_number']}")
    assert st == 200 and r["answer"]["parts"][0]["text"] in pg["page"]["text"] and pg["chapter"]["number"] == 1
    st, r2, _ = call("POST", "/api/ask", {"question": "જ્વાળામુખી એટલે શું?", "edition_id": e, "session_id": "u1", "input_method": "voice"})
    assert r2["status"] == "abstained" and r2["message"].startswith("આ પસંદ કરેલા પાઠ્યપુસ્તકમાં")
    st, h, _ = call("GET", "/api/history?session=u1")
    assert [x["status"] for x in h["history"]] == ["abstained", "answered"]
    st, fb, _ = call("POST", "/api/feedback", {"kind": "incorrect_page", "question_id": r["question_id"], "answer_id": r["answer_id"], "comment": "x"})
    assert st == 200 and fb["status"] == "open"
    assert call("POST", "/api/feedback", {"kind": "nonsense"})[0] == 400


def test_study_and_dictionary_endpoints(server):
    call, ed = server
    e = ed["granth_vigyan_10_2026"]
    ch = call("GET", f"/api/editions/{e}/chapters")[1]["chapters"][0]["id"]
    assert call("GET", f"/api/chapters/{ch}/revision")[1]["definitions"]
    assert call("GET", f"/api/chapters/{ch}/practice")[1]["questions"]
    words = call("GET", f"/api/chapters/{ch}/vocabulary")[1]["words"]
    assert words
    from urllib.parse import quote
    found = call("GET", f"/api/vocabulary/search?q={quote('પર્ણરંધ્ર')}&edition={e}")[1]["words"]
    assert found and found[0]["page_number"] == 2
    assert call("POST", "/api/saved-words", {"vocabulary_id": words[0]["id"], "session_id": "u9"})[1]["saved"]
    assert len(call("GET", "/api/saved-words?session=u9")[1]["words"]) == 1
    call("DELETE", f"/api/saved-words/{words[0]['id']}?session=u9")
    assert call("GET", "/api/saved-words?session=u9")[1]["words"] == []
    assert call("GET", "/api/chapters/99999/revision")[0] == 404


def test_offline_package_only_for_authorized_editions(server):
    call, ed = server
    e = ed["granth_vigyan_10_2026"]
    st, pkg, _ = call("GET", f"/api/editions/{e}/package")
    assert st == 200 and pkg["format"] == "granth-offline-package/1" and len(pkg["pages"]) == 10 and pkg["edition"]["permission_status"] == "APPROVED"
    assert call("POST", f"/api/admin/editions/{e}/review", {"decision": "rejected"}, {"X-Admin-Token": "test-admin-token"})[0] == 200
    assert call("GET", f"/api/editions/{e}/package")[0] == 404
    assert call("GET", f"/api/editions/{e}/pages/1")[0] == 404
    assert call("POST", "/api/ask", {"question": "પ્રકાશસંશ્લેષણ શું છે?", "edition_id": e})[1]["status"] == "abstained"


def test_admin_requires_token_and_cannot_approve_unauthorized(server):
    call, ed = server
    assert call("GET", "/api/admin/editions")[0] == 401
    assert call("GET", "/api/admin/editions", headers={"X-Admin-Token": "wrong"})[0] == 401
    st, data, _ = call("GET", "/api/admin/editions", headers={"X-Admin-Token": "test-admin-token"})
    assert st == 200 and data["editions"][0]["quality"]
    assert call("GET", "/api/admin/feedback", headers={"X-Admin-Token": "test-admin-token"})[0] == 200


def test_admin_disabled_without_configured_token(server, monkeypatch):
    call, _ = server
    monkeypatch.delenv("GRANTH_ADMIN_TOKEN")
    assert call("GET", "/api/admin/editions", headers={"X-Admin-Token": ""})[0] == 403


def test_security_headers_traversal_limits(server):
    call, _ = server
    st, body, headers = call("GET", "/", raw=True)
    assert st == 200 and b"GRANTH-AI" in body
    assert headers["X-Content-Type-Options"] == "nosniff" and "default-src 'self'" in headers["Content-Security-Policy"]
    for path in ("/../.env", "/..%2f.env", "/%2e%2e/%2e%2e/etc/passwd", "/../granth/api.py"):
        st, body, _ = call("GET", path, raw=True)
        assert b"GEMINI_API_KEY" not in body and b"root:" not in body and b"ThreadingHTTPServer" not in body
    assert call("POST", "/api/ask", {"question": "ક" * 70000})[0] == 413
    assert call("POST", "/api/ask", {"question": "ક" * 600, "edition_id": 1})[0] == 400
    assert call("POST", "/api/ask", {"question": "x'; DROP TABLE text_chunks;--", "edition_id": 1})[0] == 200
    assert call("GET", "/api/health")[1]["chunks"] > 0
    assert call("GET", "/api/nope")[0] == 404


def test_about_carries_permanent_credits(server):
    call, _ = server
    a = call("GET", "/api/about")[1]
    assert a["credit_lines"] == ["IDEA CONTRIBUTOR: BHAVESHBHAI SOLANKI", "FOUNDER & PROJECT DEVELOPER: DIVYESH BAMBHANIYA"]
    assert "NOT GSEB" in a["sample_notice"]["en"]


def test_stats_and_providers(server):
    call, ed = server
    call("POST", "/api/ask", {"question": "શ્વસન એટલે શું?", "edition_id": ed["granth_vigyan_10_2026"]})
    s = call("GET", "/api/stats")[1]
    assert s["external_api_calls"] == 0 and s["local_retrievals"] >= 1
    p = call("GET", "/api/providers")[1]
    assert p["generative_enabled"] is False and any(x["name"] == "extractive" for x in p["providers"])
