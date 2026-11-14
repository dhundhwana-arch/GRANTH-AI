"""Database access and forward-only migrations (SQLite now, PostgreSQL-portable SQL)."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_local = threading.local()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    p = str(path or config.db_path())
    if p != ":memory:":
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, timeout=15, check_same_thread=False)
    con.row_factory = sqlite3.Row
    if p != ":memory:":
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA foreign_keys = OFF")     # table rebuilds inside migrations need enforcement off
    migrate(con)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def migrate(con: sqlite3.Connection) -> list[str]:
    con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    done = {r[0] for r in con.execute("SELECT name FROM schema_migrations")}
    applied = []
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if f.name in done:
            continue
        con.executescript("BEGIN;\n" + f.read_text(encoding="utf-8") + "\nCOMMIT;")
        con.execute("INSERT INTO schema_migrations(name, applied_at) VALUES (?,?)", (f.name, now()))
        con.commit()
        applied.append(f.name)
    return applied


def thread_connection(path: str | Path | None = None) -> sqlite3.Connection:
    """One connection per thread (used by the HTTP server)."""
    key = str(path or config.db_path())
    cons = getattr(_local, "cons", None)
    if cons is None:
        cons = _local.cons = {}
    if key not in cons:
        cons[key] = connect(key)
    return cons[key]
