"""HTTP API + static web app. Standard library only (ThreadingHTTPServer)."""
from __future__ import annotations

import hmac
import json
import mimetypes
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import CREDITS, ENGINE_VERSION, __version__, answer, cache, config, cost, db, ingest, ocr, providers, study
from .config import ROOT

WEB = ROOT / "web"
MAX_BODY = 64 * 1024
RATE_LIMIT, RATE_WINDOW = 240, 60.0          # requests per IP per minute on /api/
_hits: dict = {}
_hits_lock = threading.Lock()
_jobs_lock = threading.Lock()
FEEDBACK_KINDS = ("incorrect_answer", "incorrect_page", "missing_content", "ocr_error", "other")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "microphone=(self), camera=(self), geolocation=()",
    # 'wasm-unsafe-eval' + blob: workers are required by the local (in-browser) OCR engine
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'wasm-unsafe-eval' blob:; worker-src 'self' blob:; "
                               "img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; font-src 'self'; "
                               "connect-src 'self' data: blob:; object-src 'none'; base-uri 'self'; form-action 'self'",
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    with _hits_lock:
        q = _hits.setdefault(ip, [])
        while q and now - q[0] > RATE_WINDOW:
            q.pop(0)
        if len(q) >= RATE_LIMIT:
            return False
        q.append(now)
        if len(_hits) > 5000:
            _hits.clear()
        return True


# ----------------------------------------------------------------------------- data helpers
def catalog(con) -> dict:
    rows = con.execute(
        "SELECT e.id AS edition_id, e.slug, e.edition_label, e.academic_year, e.permission_status, e.review_status,"
        " e.discovery_status, e.corpus_version, e.page_count, e.ingested_at, e.license, e.source_url, t.id AS textbook_id,"
        " t.title, t.board, t.medium, t.standard, s.name_gu AS subject, s.name_en AS subject_en,"
        " (SELECT COUNT(*) FROM chapters c WHERE c.edition_id=e.id) AS chapter_count"
        " FROM textbook_editions e JOIN textbooks t ON t.id=e.textbook_id JOIN subjects s ON s.id=t.subject_id"
        " ORDER BY t.board, t.medium, t.standard, s.name_gu, t.title, e.id").fetchall()
    books: dict = {}
    for r in rows:
        d = dict(r)
        d["available"] = bool(d["permission_status"] == "AUTHORIZED" and d["review_status"] == "approved" and d["ingested_at"])
        b = books.setdefault(d["textbook_id"], {k: d[k] for k in ("textbook_id", "title", "board", "medium", "standard",
                                                                    "subject", "subject_en")} | {"editions": []})
        b["editions"].append({k: d[k] for k in ("edition_id", "slug", "edition_label", "academic_year", "permission_status",
                                                 "review_status", "discovery_status", "corpus_version", "page_count",
                                                 "chapter_count", "license", "source_url", "available")})
    out = list(books.values())
    for b in out:
        b["available"] = any(e["available"] for e in b["editions"])
    return {"textbooks": out, "unavailable_message": "પરવાનગી બાકી – આ પાઠ્યપુસ્તકનું લખાણ હજી ઉમેરાયું નથી."}


def _approved_edition(con, edition_id: int):
    row = con.execute(
        "SELECT e.*, t.title, t.board, t.medium, t.standard, s.name_gu AS subject FROM textbook_editions e"
        " JOIN textbooks t ON t.id=e.textbook_id JOIN subjects s ON s.id=t.subject_id WHERE e.id=?"
        " AND e.permission_status='AUTHORIZED' AND e.review_status='approved' AND e.ingested_at IS NOT NULL",
        (edition_id,)).fetchone()
    if row is None:
        raise ApiError(404, "edition not available (unknown, not authorized or not approved)")
    return dict(row)


def chapters(con, edition_id: int) -> dict:
    ed = _approved_edition(con, edition_id)
    chs = []
    for c in con.execute("SELECT * FROM chapters WHERE edition_id=? ORDER BY number", (edition_id,)):
        d = dict(c)
        d["sections"] = [dict(s) for s in con.execute(
            "SELECT id, number, title, page_start FROM sections WHERE chapter_id=? ORDER BY id", (c["id"],))]
        chs.append(d)
    return {"edition": _public_edition(ed), "chapters": chs}


def _public_edition(ed: dict) -> dict:
    return {k: ed[k] for k in ("id", "slug", "title", "board", "medium", "standard", "subject", "edition_label",
                               "academic_year", "license", "source_url", "permission_status", "corpus_version",
                               "content_sha256", "page_count")}


def page(con, edition_id: int, number: int) -> dict:
    ed = _approved_edition(con, edition_id)
    p = con.execute("SELECT page_number, text, extraction_method, confidence FROM pages WHERE edition_id=? AND page_number=?",
                    (edition_id, number)).fetchone()
    if p is None:
        raise ApiError(404, "page not found")
    ch = con.execute("SELECT number, title FROM chapters WHERE edition_id=? AND page_start<=? AND page_end>=? ORDER BY number"
                     " LIMIT 1", (edition_id, number, number)).fetchone()
    chunks = [dict(r) for r in con.execute(
        "SELECT id AS chunk_id, kind, text, section_title, chapter_title FROM text_chunks WHERE edition_id=? AND page_number=?"
        " ORDER BY chunk_index", (edition_id, number))]
    return {"edition": _public_edition(ed), "page": dict(p), "chapter": dict(ch) if ch else None, "chunks": chunks,
            "page_count": ed["page_count"]}


def offline_package(con, edition_id: int) -> dict:
    """Everything the browser needs to read and search this edition with no network. Authorized editions only."""
    ed = _approved_edition(con, edition_id)
    return {
        "format": "granth-offline-package/1", "generated_at": db.now(), "edition": _public_edition(ed),
        "chapters": chapters(con, edition_id)["chapters"],
        "pages": [dict(r) for r in con.execute(
            "SELECT page_number, text FROM pages WHERE edition_id=? ORDER BY page_number", (edition_id,))],
        "chunks": [dict(r) for r in con.execute(
            "SELECT id AS chunk_id, page_number, kind, text, chapter_number, chapter_title, section_title FROM text_chunks"
            " WHERE edition_id=? ORDER BY chunk_index", (edition_id,))],
        "vocabulary": [dict(r) for r in con.execute(
            "SELECT word, kind, explanation, context, page_number, chapter_id FROM vocabulary WHERE edition_id=? ORDER BY id",
            (edition_id,))],
    }


def sources(con) -> dict:
    rows = con.execute("SELECT s.id, s.name, s.base_url, s.kind, s.robots_status, s.last_checked_at, p.status AS permission_status,"
                       " p.license, p.notes AS permission_notes FROM textbook_sources s LEFT JOIN source_permissions p"
                       " ON p.source_id=s.id ORDER BY s.id").fetchall()
    return {"sources": [dict(r) for r in rows]}


def about() -> dict:
    return {"name": "GRANTH-AI", "version": __version__, "engine_version": ENGINE_VERSION, "credits": CREDITS,
            "policy": {"gu": "ઉત્તર માત્ર પસંદ કરેલા, અધિકૃત પાઠ્યપુસ્તકના લખાણમાંથી જ આપવામાં આવે છે. આધાર ન મળે તો સિસ્ટમ ઉત્તર આપતી નથી.",
                       "en": "Answers come only from the selected, authorized textbook text. Without evidence the system abstains."},
            "sample_notice": {"gu": "હાલમાં ઉપલબ્ધ પુસ્તકો GRANTH-AI પ્રોજેક્ટ માટે લખાયેલી નમૂના પાઠમાળા છે. તે GSEB/GSSTB કે NCERT નાં પાઠ્યપુસ્તકો નથી. "
                                    "સત્તાવાર પાઠ્યપુસ્તકો લેખિત પરવાનગી મળ્યા પછી જ ઉમેરાશે.",
                              "en": "Books currently available are sample readers written for this project. They are NOT GSEB/GSSTB or NCERT "
                                    "textbooks. Official textbooks will be added only after written permission."}}


# ----------------------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    server_version = "GRANTH-AI"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    router: providers.Router | None = None
    db_path = None
    quiet = False

    def log_message(self, fmt, *args):      # no query strings / bodies in logs (student privacy)
        if not self.quiet:
            super().log_message("%s", f"{self.command} {self.path.split('?')[0]} -> {args[1] if len(args) > 1 else ''}")

    @property
    def con(self):
        return db.thread_connection(self.db_path)

    # -- plumbing
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status: int = 200):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8",
                   {"Cache-Control": "no-store"})

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "bad Content-Length")
        if n > MAX_BODY:
            raise ApiError(413, "request body too large")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            raise ApiError(400, "body must be UTF-8 JSON")
        if not isinstance(data, dict):
            raise ApiError(400, "body must be a JSON object")
        return data

    def _require_admin(self):
        token = config.get("GRANTH_ADMIN_TOKEN")
        if not token:
            raise ApiError(403, "admin interface is disabled (GRANTH_ADMIN_TOKEN not configured)")
        given = self.headers.get("X-Admin-Token", "")
        if not hmac.compare_digest(given.encode(), token.encode()):
            raise ApiError(401, "invalid admin token")

    def _static(self, path: str):
        rel = urllib.parse.unquote(path.lstrip("/")) or "index.html"
        target = (WEB / rel).resolve()
        if WEB.resolve() not in target.parents and target != WEB.resolve():
            raise ApiError(404, "not found")
        if target.is_dir() or not target.exists():
            if "." in rel.rsplit("/", 1)[-1]:
                raise ApiError(404, "not found")
            target = WEB / "index.html"
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix in (".js", ".mjs"):
            ctype = "text/javascript"
        if target.suffix == ".webmanifest":
            ctype = "application/manifest+json"
        if ctype.startswith("text/") or ctype.endswith(("json", "javascript")):
            ctype += "; charset=utf-8"
        extra = {"Cache-Control": "public, max-age=604800" if rel.startswith(("vendor/", "fonts/")) else "no-cache"}
        if target.name == "sw.js":
            extra["Service-Worker-Allowed"] = "/"
        if target.suffix == ".gz":
            ctype = "application/octet-stream"
        self._send(200, target.read_bytes(), ctype, extra)

    def _dispatch(self, method: str):
        parsed = urllib.parse.urlparse(self.path)
        path, qs = parsed.path, urllib.parse.parse_qs(parsed.query)
        try:
            if not path.startswith("/api/"):
                if method not in ("GET", "HEAD"):
                    raise ApiError(405, "method not allowed")
                return self._static(path)
            if not _rate_ok(self.client_address[0]):
                raise ApiError(429, "too many requests - please wait a minute")
            for m, pattern, fn in ROUTES:
                if m == method:
                    match = re.fullmatch(pattern, path)
                    if match:
                        return self._json(fn(self, qs, *match.groups()))
            raise ApiError(404, "unknown endpoint")
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except answer.QuestionError as e:
            self._json({"error": str(e)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:                      # never leak internals to the client
            self.log_error("internal error: %r", e)
            self._json({"error": "internal error"}, 500)

    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")


def _int(v, name="id") -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ApiError(400, f"{name} must be an integer")


def _q(qs, name, default=None):
    return qs.get(name, [default])[0]


def r_health(h, qs):
    n = h.con.execute("SELECT COUNT(*) FROM text_chunks").fetchone()[0]
    return {"status": "ok", "version": __version__, "engine_version": ENGINE_VERSION, "chunks": n,
            "generative_enabled": bool(h.router and h.router.enabled)}


def r_ask(h, qs):
    b = h._body()
    scope = {k: b.get(k) for k in ("board", "medium", "standard", "subject", "textbook_id", "edition_id", "chapter_id")
             if b.get(k) not in (None, "")}
    marks = b.get("marks")
    return answer.ask(h.con, str(b.get("question", "")), scope, str(b.get("mode") or "auto"),
                      _int(marks, "marks") if marks not in (None, "") else None,
                      session_id=str(b.get("session_id") or "anonymous"), input_method=str(b.get("input_method") or "typed"),
                      router=h.router)


def r_feedback(h, qs):
    b = h._body()
    if b.get("kind") not in FEEDBACK_KINDS:
        raise ApiError(400, "kind must be one of " + ", ".join(FEEDBACK_KINDS))
    fid = h.con.execute("INSERT INTO feedback(question_id, answer_id, kind, comment, created_at) VALUES (?,?,?,?,?)",
                        (b.get("question_id"), b.get("answer_id"), b["kind"], str(b.get("comment") or "")[:1000], db.now())).lastrowid
    h.con.commit()
    return {"id": fid, "status": "open", "message": "આભાર! તમારો પ્રતિભાવ નોંધાયો છે."}


def r_saved_words_add(h, qs):
    b = h._body()
    vid = _int(b.get("vocabulary_id"), "vocabulary_id")
    if not h.con.execute("SELECT 1 FROM vocabulary WHERE id=?", (vid,)).fetchone():
        raise ApiError(404, "word not found")
    h.con.execute("INSERT OR IGNORE INTO saved_words(session_id, vocabulary_id, created_at) VALUES (?,?,?)",
                  (str(b.get("session_id") or "anonymous")[:64], vid, db.now()))
    h.con.commit()
    return {"saved": True}


def r_saved_words(h, qs):
    rows = h.con.execute(
        "SELECT v.*, c.number AS chapter_number, c.title AS chapter_title FROM saved_words s JOIN vocabulary v ON v.id=s.vocabulary_id"
        " LEFT JOIN chapters c ON c.id=v.chapter_id WHERE s.session_id=? ORDER BY s.id DESC",
        (str(_q(qs, "session", "anonymous"))[:64],)).fetchall()
    return {"words": [study._vocab_row(r) for r in rows]}


def r_saved_words_del(h, qs, vid):
    h.con.execute("DELETE FROM saved_words WHERE session_id=? AND vocabulary_id=?",
                  (str(_q(qs, "session", "anonymous"))[:64], _int(vid)))
    h.con.commit()
    return {"deleted": True}


def _or404(v):
    if v is None:
        raise ApiError(404, "not found")
    return v


def r_admin_review(h, qs, eid):
    h._require_admin()
    b = h._body()
    if b.get("decision") not in ("approved", "rejected", "pending"):
        raise ApiError(400, "decision must be approved | rejected | pending")
    ed = h.con.execute("SELECT * FROM textbook_editions WHERE id=?", (_int(eid),)).fetchone()
    if ed is None:
        raise ApiError(404, "edition not found")
    if b["decision"] == "approved" and ed["permission_status"] != "AUTHORIZED":
        raise ApiError(409, "cannot approve: permission status is " + ed["permission_status"])
    h.con.execute("UPDATE textbook_editions SET review_status=?, reviewed_by=?, reviewed_at=? WHERE id=?",
                  (b["decision"], str(b.get("reviewer") or "admin")[:80], db.now(), ed["id"]))
    removed = cache.invalidate_edition(h.con, ed["id"]) if b["decision"] != "approved" else 0
    h.con.commit()
    return {"edition_id": ed["id"], "review_status": b["decision"], "cache_entries_invalidated": removed}


def r_admin_editions(h, qs):
    h._require_admin()
    out = []
    for e in h.con.execute("SELECT e.*, t.title FROM textbook_editions e JOIN textbooks t ON t.id=e.textbook_id ORDER BY e.id"):
        d = dict(e)
        d["quality"] = [dict(r) for r in h.con.execute(
            "SELECT method, COUNT(*) pages, ROUND(AVG(score),4) avg_score, ROUND(AVG(engine_confidence),4) avg_engine_confidence,"
            " SUM(passed) passed FROM extraction_quality WHERE edition_id=? GROUP BY method", (e["id"],))]
        out.append(d)
    return {"editions": out}


def r_admin_feedback(h, qs):
    h._require_admin()
    return {"feedback": [dict(r) for r in h.con.execute(
        "SELECT f.*, q.text AS question FROM feedback f LEFT JOIN questions q ON q.id=f.question_id ORDER BY f.id DESC LIMIT 200")]}


def r_admin_jobs(h, qs):
    h._require_admin()
    return {"jobs": [dict(r) for r in h.con.execute("SELECT * FROM ingestion_jobs ORDER BY id DESC LIMIT 100")]}


def r_admin_ingest(h, qs):
    """Start a background (non-blocking) re-ingestion of a bundled sample book."""
    h._require_admin()
    b = h._body()
    slug = str(b.get("slug") or "")
    book_dir = ROOT / "data" / "sample" / slug
    if not re.fullmatch(r"[a-z0-9_]+", slug) or not (book_dir / "book.json").exists():
        raise ApiError(404, "unknown sample book")
    path = h.db_path

    def work():
        with _jobs_lock:
            con = db.connect(path)
            try:
                ingest.ingest_text_source(con, book_dir, force=True, auto_approve=True)
            except Exception:
                pass
            finally:
                con.close()

    threading.Thread(target=work, daemon=True).start()
    return {"started": True, "slug": slug, "poll": "/api/admin/jobs"}


ROUTES = [
    ("GET", r"/api/health", r_health),
    ("GET", r"/api/about", lambda h, qs: about()),
    ("GET", r"/api/catalog", lambda h, qs: catalog(h.con)),
    ("GET", r"/api/sources", lambda h, qs: sources(h.con)),
    ("GET", r"/api/editions/(\d+)/chapters", lambda h, qs, e: chapters(h.con, int(e))),
    ("GET", r"/api/editions/(\d+)/pages/(\d+)", lambda h, qs, e, p: page(h.con, int(e), int(p))),
    ("GET", r"/api/editions/(\d+)/package", lambda h, qs, e: offline_package(h.con, int(e))),
    ("POST", r"/api/ask", r_ask),
    ("GET", r"/api/history", lambda h, qs: {"history": answer.history(h.con, str(_q(qs, "session", "anonymous")))}),
    ("POST", r"/api/feedback", r_feedback),
    ("GET", r"/api/chapters/(\d+)/revision", lambda h, qs, c: _or404(study.chapter_revision(h.con, int(c)))),
    ("GET", r"/api/chapters/(\d+)/practice", lambda h, qs, c: _or404(study.practice_questions(h.con, int(c)))),
    ("GET", r"/api/chapters/(\d+)/vocabulary", lambda h, qs, c: {"words": study.chapter_vocabulary(h.con, int(c))}),
    ("GET", r"/api/vocabulary/search", lambda h, qs: {"words": study.search_vocabulary(
        h.con, str(_q(qs, "q", ""))[:80], _int(_q(qs, "edition")) if _q(qs, "edition") else None)}),
    ("GET", r"/api/saved-words", r_saved_words),
    ("POST", r"/api/saved-words", r_saved_words_add),
    ("DELETE", r"/api/saved-words/(\d+)", r_saved_words_del),
    ("GET", r"/api/stats", lambda h, qs: cost.summary(h.con)),
    ("GET", r"/api/providers", lambda h, qs: {"generative_enabled": bool(h.router and h.router.enabled),
                                              "providers": (h.router or providers.Router()).status(),
                                              "ocr": ocr.adapter_status()}),
    ("GET", r"/api/admin/editions", r_admin_editions),
    ("POST", r"/api/admin/editions/(\d+)/review", r_admin_review),
    ("GET", r"/api/admin/feedback", r_admin_feedback),
    ("GET", r"/api/admin/jobs", r_admin_jobs),
    ("POST", r"/api/admin/ingest", r_admin_ingest),
]


def make_server(host="0.0.0.0", port=8000, db_path=None, router=None, quiet=False) -> ThreadingHTTPServer:
    handler = type("GranthHandler", (Handler,), {"db_path": db_path, "quiet": quiet,
                                                 "router": router if router is not None else providers.Router()})
    srv = ThreadingHTTPServer((host, port), handler)
    srv.daemon_threads = True
    return srv


def serve(host="0.0.0.0", port=8000):
    srv = make_server(host, port)
    print(f"GRANTH-AI listening on http://{host}:{port}  (database: {config.db_path()})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
