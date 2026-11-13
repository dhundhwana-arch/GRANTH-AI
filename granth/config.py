"""Runtime configuration. Reads a local ``.env`` (never committed) without extra dependencies."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_loaded = False


def load_env(path: Path | None = None) -> None:
    """Minimal .env loader: KEY=VALUE lines; existing environment wins."""
    global _loaded
    if _loaded and path is None:
        return
    p = path or ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    _loaded = True


def get(name: str, default: str = "") -> str:
    load_env()
    return os.environ.get(name, default)


def get_int(name: str, default: int) -> int:
    try:
        return int(get(name, str(default)))
    except ValueError:
        return default


def db_path() -> Path:
    return Path(get("GRANTH_DB_PATH", str(ROOT / "var" / "granth.sqlite3")))


def mask(secret: str) -> str:
    """Never print full credentials: show only the last 4 characters."""
    if not secret:
        return "(not set)"
    return "****" + secret[-4:] if len(secret) > 8 else "****"
