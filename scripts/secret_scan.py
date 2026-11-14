"""Scan tracked files (and, with --history, every commit) for things that look like credentials.

Usage: python scripts/secret_scan.py [--history]      exit code 1 = something found
Only pattern names, file names and line numbers are printed - never the matching text.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "Google API key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{30,}"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
    "non-empty secret assignment": re.compile(
        r"^[ \t]*(?:export[ \t]+)?(GEMINI_API_KEY|HUGGINGFACE_API_TOKEN|OTHER_PROVIDER_API_KEY|GRANTH_ADMIN_TOKEN)[ \t]*=[ \t]*[\"']?[A-Za-z0-9_\-]{12,}", re.M),
}
FORBIDDEN_FILES = re.compile(r"(^|/)(\.env(\.(?!example$)[^/]*)?|PRIVATE_API_[^/]*\.md|[^/]*\.pem|[^/]*\.key|id_rsa[^/]*|\.netrc|\.git-credentials)$")
SKIP = re.compile(r"\.(png|jpg|jpeg|ico|woff2?|ttf|pdf|sqlite3?|traineddata|gz|br|wasm)$|(^|/)package-lock\.json$")


def scan_text(name: str, text: str) -> list[str]:
    hits = []
    for label, pat in PATTERNS.items():
        for m in pat.finditer(text):
            hits.append(f"{name}:{text.count(chr(10), 0, m.start()) + 1}: {label}")
    return hits


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, errors="replace").stdout


def main() -> int:
    hits = []
    files = [f for f in git("ls-files").splitlines() if f]
    for f in files:
        if FORBIDDEN_FILES.search(f):
            hits.append(f"{f}: file of a kind that must never be committed")
        if SKIP.search(f):
            continue
        try:
            hits += scan_text(f, (ROOT / f).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    scanned_commits = 0
    if "--history" in sys.argv:
        for commit in git("rev-list", "--all").split():
            scanned_commits += 1
            for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit).splitlines():
                if FORBIDDEN_FILES.search(f):
                    hits.append(f"{commit[:8]}:{f}: file of a kind that must never be committed")
            for h in scan_text(commit[:8], git("show", "--format=", "--unified=0", commit)):
                hits.append(h)
    print(f"scanned {len(files)} tracked files" + (f" and {scanned_commits} commits" if scanned_commits else ""))
    for h in sorted(set(hits)):
        print("FOUND", h)
    print("result:", "CLEAN" if not hits else f"{len(set(hits))} finding(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
