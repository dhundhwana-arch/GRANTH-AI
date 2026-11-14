"""Phase 3 release audit: admin token strength, deletion of a session's data, isolation, secret scan."""
import subprocess
import sys
from pathlib import Path

from granth import api, ingest

from test_api import server  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parent.parent
NOTES = "મારી નોંધ. ચુંબકના બે ધ્રુવ હોય છે: ઉત્તર ધ્રુવ અને દક્ષિણ ધ્રુવ. સમાન ધ્રુવો વચ્ચે અપાકર્ષણ થાય છે તે ઘટનાને ચુંબકીય અપાકર્ષણ કહે છે."


def test_weak_or_development_admin_tokens_are_recognised():
    for t in ("dev-admin-token", "e2e-admin", "admin", "changeme", "short-token", "aaaaaaaaaaaaaaaaaaaaaaaaaaaa"):
        assert api.weak_admin_token(t)
    assert not api.weak_admin_token("Zk3v9Qm1-Lp7xT2eWs8Rb4Yc6Nd0Ha5J")


def test_admin_refuses_development_token_unless_explicitly_allowed(server, monkeypatch):  # noqa: F811
    call, ids = server
    hdr = {"X-Admin-Token": "test-admin-token"}
    assert call("GET", "/api/admin/editions", headers=hdr)[0] == 200             # allowed in the test environment only
    monkeypatch.delenv("GRANTH_ALLOW_WEAK_ADMIN_TOKEN")
    st, body, _ = call("GET", "/api/admin/editions", headers=hdr)
    assert st == 403 and "weak" in body["error"]
    monkeypatch.setenv("GRANTH_ADMIN_TOKEN", "Zk3v9Qm1-Lp7xT2eWs8Rb4Yc6Nd0Ha5J")
    assert call("GET", "/api/admin/editions", headers={"X-Admin-Token": "Zk3v9Qm1-Lp7xT2eWs8Rb4Yc6Nd0Ha5J"})[0] == 200
    assert call("GET", "/api/admin/editions", headers=hdr)[0] == 401


def test_repeated_wrong_admin_tokens_are_throttled(server):  # noqa: F811
    call, ids = server
    api._admin_failures.clear()
    codes = [call("GET", "/api/admin/editions", headers={"X-Admin-Token": f"wrong-{i}"})[0] for i in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]
    assert call("GET", "/api/admin/editions", headers={"X-Admin-Token": "test-admin-token"})[0] == 429   # locked out for a while
    api._admin_failures.clear()


def test_delete_session_data_erases_one_session_only(server):  # noqa: F811
    call, ids = server
    e = ids["granth_vigyan_10_2026"]
    a, b = "session-aaaa-1111", "session-bbbb-2222"
    for s in (a, b):
        st, r, _ = call("POST", "/api/ask", {"question": "પ્રકાશસંશ્લેષણ એટલે શું?", "edition_id": e, "session_id": s})
        assert st == 200
        call("POST", "/api/saved-answers", {"answer_id": r["answer_id"], "session_id": s})
    st, n, _ = call("POST", "/api/personal-notes", {"session_id": a, "title": "મારી નોંધ", "text": NOTES, "rights_confirmed": True})
    assert st == 200
    assert call("GET", f"/api/personal-notes?session={b}")[1]["notes"] == []                 # B never sees A's notes
    st, d, _ = call("DELETE", f"/api/session-data?session={a}")
    assert st == 200 and d["deleted"] and d["questions"] == 1 and d["personal_notes"] == 1 and d["saved_answers"] >= 0
    assert call("GET", f"/api/history?session={a}")[1]["history"] == []
    assert call("GET", f"/api/saved-answers?session={a}")[1]["saved"] == []
    assert call("GET", f"/api/personal-notes?session={a}")[1]["notes"] == []
    assert len(call("GET", f"/api/history?session={b}")[1]["history"]) == 1                  # the other session is untouched
    assert len(call("GET", f"/api/saved-answers?session={b}")[1]["saved"]) == 1
    assert call("DELETE", "/api/session-data?session=anonymous")[0] == 400
    assert call("DELETE", "/api/session-data?session=x")[0] == 400


def test_deleted_personal_text_is_gone_from_the_database(con):
    r = ingest.add_personal_notes(con, "session-cccc-3333", "મારી નોંધ", NOTES, True)
    assert con.execute("SELECT COUNT(*) FROM text_chunks WHERE text LIKE '%ચુંબકીય અપાકર્ષણ%'").fetchone()[0] >= 1
    ingest.delete_session_data(con, "session-cccc-3333")
    for table, col in (("text_chunks", "text"), ("pages", "text"), ("vocabulary", "context"), ("generated_answers", "answer_json")):
        assert con.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE '%ચુંબકીય અપાકર્ષણ%'").fetchone()[0] == 0, table
    assert r


def test_no_secrets_in_tracked_files():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "secret_scan.py")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert ".env" not in tracked and not any(f.startswith("PRIVATE_API") for f in tracked)
    assert ".env.example" in tracked
    for line in (ROOT / ".env.example").read_text().splitlines():
        if "=" in line and not line.startswith("#") and any(k in line for k in ("KEY", "TOKEN")) and "ALLOW" not in line:
            assert line.split("=", 1)[1].strip() == "", line


def test_errors_do_not_leak_internals_and_logs_hide_queries(server):  # noqa: F811
    call, ids = server
    st, body, _ = call("POST", "/api/ask", {"question": "x" * 600, "edition_id": 1})
    assert st == 400 and "Traceback" not in str(body)
    st, body, _ = call("GET", "/api/page/abc/1")
    assert st in (400, 404) and "Traceback" not in str(body) and "sqlite" not in str(body).lower()
    src = (ROOT / "granth" / "api.py").read_text(encoding="utf-8")
    assert "self.path.split('?')[0]" in src                      # request log drops the query string (session ids, questions)
