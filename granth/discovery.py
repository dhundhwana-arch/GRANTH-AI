"""Official textbook discovery pipeline (metadata only).

For every portal the pipeline (1) reads robots.txt and obeys it, (2) fetches the public catalogue page,
(3) extracts candidate textbook PDF links with standard / subject / medium guesses, and (4) records them in the
registry with a PERMISSION STATUS. It never downloads a PDF: download + ingestion is a separate step that
`granth.ingest` refuses unless the edition is APPROVED.

No authentication, paywall, robots rule or access control is bypassed; on any doubt the entry is recorded
as UNKNOWN / UNREACHABLE and nothing is fetched.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

from . import db
from .config import ROOT

USER_AGENT = "GRANTH-AI-discovery/0.1 (+https://github.com/dhundhwana-arch/GRANTH-AI; metadata only)"
REGISTRY_PATH = ROOT / "data" / "registry" / "discovered.json"

# Permission status per portal, with the evidence it is based on. See docs/COPYRIGHT_AND_PERMISSION_REGISTER.md.
SOURCES = [
    {"id": "gsstb", "name": "Gujarat State Board of School Textbooks (GSSTB)",
     "catalogue_urls": ["https://gsstb.gujarat.gov.in/Home/gsstb/Std9to12"],
     "permission_status": "UNKNOWN",
     "permission_basis": "No explicit open licence or reuse grant for software/AI use was found. Textbooks are "
                         "copyright of the Board. Written permission must be obtained before any ingestion."},
    {"id": "ncert", "name": "NCERT", "catalogue_urls": ["https://ncert.nic.in/textbook.php"],
     "permission_status": "RESTRICTED",
     "permission_basis": "NCERT copyright notice on the textbook page: use of the online books 'as a part of digital "
                         "content packages or software is also strictly prohibited'; no hosting or redistribution. "
                         "Not ingested. Only written permission from NCERT could change this."},
    {"id": "diksha", "name": "DIKSHA", "catalogue_urls": ["https://diksha.gov.in/"],
     "permission_status": "UNKNOWN",
     "permission_basis": "Licence is declared per content item (many items are CC-licensed, others are not). "
                         "Each item's licence field must be read and recorded before use; nothing is assumed."},
]

GU_SUBJECTS = {"ગણિત": "Mathematics", "વિજ્ઞાન": "Science", "સામાજિક વિજ્ઞાન": "Social Science", "ગુજરાતી": "Gujarati",
               "અંગ્રેજી": "English", "હિન્દી": "Hindi", "સંસ્કૃત": "Sanskrit", "ભૌતિકવિજ્ઞાન": "Physics",
               "રસાયણવિજ્ઞાન": "Chemistry", "જીવવિજ્ઞાન": "Biology", "અર્થશાસ્ત્ર": "Economics"}
EN_SUBJECTS = {v.lower(): k for k, v in GU_SUBJECTS.items()}
_GU_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[dict] = []
        self._href = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append({"href": self._href, "text": " ".join(" ".join(self._text).split())})
            self._href = None


def guess_metadata(text: str, href: str = "") -> dict:
    """Best-effort standard / subject / medium guess from link text. Guesses are flagged, never trusted blindly."""
    blob = (text + " " + urllib.parse.unquote(href)).translate(_GU_DIGITS)
    std = None
    m = re.search(r"(?:ધોરણ|std\.?|standard|class)\s*[-:]?\s*(\d{1,2})", blob, re.I)
    if m and 1 <= int(m.group(1)) <= 12:
        std = int(m.group(1))
    subject = None
    for gu in sorted(GU_SUBJECTS, key=len, reverse=True):
        if gu in blob:
            subject = gu
            break
    if subject is None:
        low = blob.lower()
        for en in sorted(EN_SUBJECTS, key=len, reverse=True):
            if en in low:
                subject = EN_SUBJECTS[en]
                break
    medium = None
    low = blob.lower()
    if "ગુજરાતી માધ્યમ" in blob or "gujarati medium" in low or re.search(r"\b(guj|gm)\b", low):
        medium = "ગુજરાતી"
    elif "english medium" in low or "અંગ્રેજી માધ્યમ" in blob:
        medium = "English"
    year = re.search(r"(20\d{2})\s*[-–]\s*(\d{2,4})", blob)
    return {"standard": std, "subject": subject, "medium": medium, "academic_year": year.group(0) if year else None,
            "metadata_is_guess": True}


def parse_catalogue(html: str, base_url: str) -> list[dict]:
    """Extract links that point to PDF files, with guessed metadata."""
    p = _LinkParser()
    p.feed(html)
    out, seen = [], set()
    for link in p.links:
        href = (link["href"] or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        url = urllib.parse.urljoin(base_url, href)
        if not urllib.parse.urlparse(url).path.lower().endswith(".pdf") or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "title": link["text"] or Path(urllib.parse.urlparse(url).path).name,
                    **guess_metadata(link["text"], href)})
    return out


def robots_allows(url: str, timeout: int = 10) -> tuple[str, str]:
    """ALLOWED / DISALLOWED / UNREACHABLE for our user agent."""
    parts = urllib.parse.urlparse(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        req = urllib.request.Request(robots, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "DISALLOWED", f"robots.txt returned HTTP {e.code} (treated as full disallow)"
        if 400 <= e.code < 500:
            return "ALLOWED", f"no robots.txt (HTTP {e.code})"
        return "UNREACHABLE", f"robots.txt HTTP {e.code}"
    except Exception as e:
        return "UNREACHABLE", f"{type(e).__name__}: {e}"[:200]
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(body.splitlines())
    return ("ALLOWED", "robots.txt permits this path") if rp.can_fetch(USER_AGENT, url) else (
        "DISALLOWED", "robots.txt disallows this path")


def discover_source(src: dict, fetch=None, timeout: int = 15) -> dict:
    """Run discovery for one portal. `fetch(url)->html` is injectable for tests."""
    result = {"source_id": src["id"], "name": src["name"], "permission_status": src["permission_status"],
              "permission_basis": src["permission_basis"], "checked_at": db.now(), "catalogues": [], "books": []}
    for url in src["catalogue_urls"]:
        entry = {"url": url}
        if fetch is None:
            status, detail = robots_allows(url, timeout)
        else:
            status, detail = "ALLOWED", "injected fetcher (test)"
        entry.update(robots_status=status, robots_detail=detail)
        if status != "ALLOWED":
            entry["fetch_status"] = "SKIPPED"
            result["catalogues"].append(entry)
            continue
        try:
            if fetch is None:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    html = r.read(5_000_000).decode("utf-8", "replace")
            else:
                html = fetch(url)
            books = parse_catalogue(html, url)
            entry.update(fetch_status="OK", pdf_links_found=len(books))
            for b in books:
                b.update(source_id=src["id"], permission_status=src["permission_status"], downloaded=False, ingested=False)
            result["books"].extend(books)
        except Exception as e:
            entry.update(fetch_status="FAILED", error=f"{type(e).__name__}: {e}"[:200])
        result["catalogues"].append(entry)
    return result


def run_discovery(con=None, fetch=None, write: bool = True, sources=None) -> dict:
    report = {"generated_at": db.now(), "user_agent": USER_AGENT,
              "sources": [discover_source(s, fetch) for s in (sources or SOURCES)]}
    if con is not None:
        for s in report["sources"]:
            robots = (s["catalogues"][0]["robots_status"] if s["catalogues"] else "NOT_CHECKED")
            row = con.execute("SELECT id FROM textbook_sources WHERE name=?", (s["name"],)).fetchone()
            base = next(x for x in (sources or SOURCES) if x["id"] == s["source_id"])["catalogue_urls"][0]
            if row:
                con.execute("UPDATE textbook_sources SET robots_status=?, last_checked_at=? WHERE id=?",
                            (robots, s["checked_at"], row["id"]))
            else:
                sid = con.execute("INSERT INTO textbook_sources(name, base_url, kind, robots_status, last_checked_at, notes)"
                                  " VALUES (?,?,?,?,?,?)", (s["name"], base, "official_portal", robots, s["checked_at"],
                                                            s["permission_basis"])).lastrowid
                con.execute("INSERT INTO source_permissions(source_id, status, evidence_url, notes, reviewed_at)"
                            " VALUES (?,?,?,?,?)", (sid, s["permission_status"], base, s["permission_basis"], s["checked_at"]))
        con.commit()
    if write:
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
