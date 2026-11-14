"""Command line: python -m granth <command>."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import answer, config, cost, db, discovery, ingest, ocr
from .config import ROOT


def _print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def seed_samples(con, force=False) -> list[dict]:
    out = []
    for d in sorted((ROOT / "data" / "sample").iterdir()):
        if (d / "book.json").exists():
            out.append({"book": d.name, **ingest.ingest_text_source(con, d, force=force, auto_approve=True)})
    sup = ROOT / "data" / "supplementary"                 # opt-in supplementary sources (role = supplementary)
    for d in sorted(sup.iterdir()) if sup.exists() else []:
        if (d / "book.json").exists():
            out.append({"book": d.name, **ingest.ingest_text_source(con, d, force=force, auto_approve=True)})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="granth", description="GRANTH-AI command line")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="create / migrate the database")
    s = sub.add_parser("seed-samples", help="ingest the project-authored sample books")
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("serve", help="run the web application")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=config.get_int("GRANTH_PORT", 8000))
    s = sub.add_parser("ask", help="ask a question from the terminal")
    s.add_argument("question")
    s.add_argument("--edition", type=int)
    s.add_argument("--subject")
    s.add_argument("--standard", type=int)
    s.add_argument("--mode", default="auto", choices=answer.MODES)
    s.add_argument("--marks", type=int)
    sub.add_parser("discover", help="run the official-source discovery pipeline (metadata only)")
    s = sub.add_parser("ingest-pdf", help="ingest an APPROVED PDF described by a book.json")
    s.add_argument("pdf")
    s.add_argument("meta", help="path to book.json")
    s.add_argument("--force", action="store_true")
    sub.add_parser("stats", help="cost / cache / usage accounting")
    sub.add_parser("ocr-status", help="which OCR engines are available")
    a = ap.parse_args(argv)

    if a.cmd == "serve":
        from . import api
        con = db.connect()
        if not con.execute("SELECT 1 FROM textbook_editions WHERE ingested_at IS NOT NULL LIMIT 1").fetchone():
            seed_samples(con)
        con.close()
        api.serve(a.host, a.port)
        return 0
    con = db.connect()
    if a.cmd == "init-db":
        _print({"database": str(config.db_path()), "migrations": [r[0] for r in con.execute("SELECT name FROM schema_migrations")]})
    elif a.cmd == "seed-samples":
        _print(seed_samples(con, a.force))
    elif a.cmd == "ask":
        scope = {k: v for k, v in (("edition_id", a.edition), ("subject", a.subject), ("standard", a.standard)) if v}
        _print(answer.ask(con, a.question, scope, a.mode, a.marks, session_id="cli"))
    elif a.cmd == "discover":
        _print(discovery.run_discovery(con))
    elif a.cmd == "ingest-pdf":
        meta = json.loads(Path(a.meta).read_text(encoding="utf-8"))
        try:
            _print(ingest.ingest_pdf(con, Path(a.pdf), meta, ocr.get_default_adapter(), force=a.force))
        except ingest.IngestionRefused as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            return 2
    elif a.cmd == "stats":
        _print(cost.summary(con))
    elif a.cmd == "ocr-status":
        _print(ocr.adapter_status())
    return 0


if __name__ == "__main__":
    sys.exit(main())
