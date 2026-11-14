"""Gujarati text processing: normalization, tokenization, light stemming,
script-integrity validation and character error rate.

Pure standard library. Two normalization levels exist on purpose:

* ``normalize_text``  – display-safe clean-up (NFC, whitespace, invisible chars). Stored text.
* ``search_key``      – aggressive folding used ONLY for matching (never shown to students).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

GUJ_START, GUJ_END = 0x0A80, 0x0AFF
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
_GUJ_DIGITS = {ord(c): str(i) for i, c in enumerate("૦૧૨૩૪૫૬૭૮૯")}

# Folding table for matching: spelling variants students commonly mix up.
_FOLD = {
    ord("ઍ"): "એ", ord("ઑ"): "ઓ", ord("ૅ"): "ે", ord("ૉ"): "ો",   # candra vowels (ઍસિડ / એસિડ)
    ord("ઈ"): "ઇ", ord("ી"): "િ",                                   # hrasva / dirgha i
    ord("ઊ"): "ઉ", ord("ૂ"): "ુ",                                   # hrasva / dirgha u
    ord("ઁ"): "ં",                                                   # chandrabindu -> anusvara
    ord("઼"): None,                                                  # nukta
    ord("ઃ"): None,                                                  # visarga
    ord("ૠ"): "ઋ",
}
_FOLD.update(_GUJ_DIGITS)

MATRAS = set("ાિીુૂૃૄૅેૈૉોૌ")
VIRAMA = "્"
SIGNS = set("ંઃઁ઼")

_TOKEN_RE = re.compile(r"[\u0A80-\u0AFF]+|[A-Za-z]+[0-9]*|[0-9]+(?:\.[0-9]+)?")

# Question / instruction words that carry no topical content.
STOPWORDS_RAW = """
છે છો છું હતું હતી હતા હોય થાય થયું કરે કરો કરવું અને અથવા કે તો પણ જ એ આ તે તેને તેમને તેનું તેની તેના તેનો
શું શુ શા કેમ કેવી કેવો કેવું કેવા કેવી રીતે કઈ કયા કયો કયું કોને કોણ કેટલા કેટલી કેટલો કેટલું ક્યાં ક્યારે માટે
એટલે કહે કહેવાય કહેવામાં આવે વ્યાખ્યા આપો સમજાવો લખો જણાવો વર્ણવો ટૂંકનોંધ ટૂંકમાં વિશે અંગે વચ્ચે વચ્ચેનો
એક બે માં થી ને ના ની નું નો પર હું મને અમે તમે મારે જોઈએ ખરું ખોટું સાચું મુજબ પ્રમાણે દ્વારા તથા જે જેને જેમાં
ઉત્તર જવાબ પ્રશ્ન કારણ આપી જણાવ
સ્પષ્ટ બતાવો દર્શાવો ગણી ગણો ચર્ચો નોંધો
શેનો શેનું શેની શેના શેમાં શેનાથી શેમાંથી શાનો શાનું શાની શાથી ક્યાંથી શો શી કોનો કોની કોનું કોના કઈ
આવી આવ્યું આવ્યો આવ્યા આવતી આવતા આવતો આવતું આવેલી આવેલા આવેલો આવેલું આવેલાં
શાને શેને વખતે દરમિયાન સમયે ખૂબ બહુ પછી પહેલાં ત્યારે જ્યારે કર્યા કર્યું કરવાથી કરવા કરતાં થતાં થયા થતી થતો થતું
વગર વિના સિવાય નથી નહીં નહિ નહી ન શકાય શકે શકીએ રહે રહેવું પડે પડતું અર્થ મતલબ સમજાવ સમજ
"""

# Case / plural suffixes stripped by the light stemmer (longest first).
_SUFFIXES = sorted(
    ["ઓમાંથી", "ઓમાં", "ઓનું", "ઓની", "ઓના", "ઓનો", "ઓને", "ઓથી", "માંથી", "માંની", "માંનું", "વાળું", "વાળી",
     "વાળો", "ોમાંથી", "ોમાં", "ોનું", "ોની", "ોના", "ોનો", "ોને", "ોથી", "માંનાં", "નાં", "માં", "નું", "ની",
     "ના", "નો", "ને", "થી", "ઓ", "એ", "ાં", "ો", "ા", "ું", "ી"],
    key=len, reverse=True)


def normalize_text(text: str) -> str:
    """Display-safe normalization. Keeps the textbook wording intact."""
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    t = t.translate(_INVISIBLE)
    t = t.replace("\u00a0", " ").replace("\u0964", "।")
    t = re.sub(r"[ \t\f\v]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return t.strip()


def fold(text: str) -> str:
    """Aggressive folding for matching. Not reversible; never display."""
    t = unicodedata.normalize("NFC", text or "").translate(_INVISIBLE).translate(_FOLD)
    return t.lower()


def _fold_suffixes():
    return sorted({fold(s) for s in _SUFFIXES}, key=len, reverse=True)


_FSUFFIXES = _fold_suffixes()


def _cluster_len(s: str) -> int:
    """Number of base letters (ignores matras/signs/virama) – a rough syllable count."""
    return sum(1 for ch in s if ch not in MATRAS and ch not in SIGNS and ch != VIRAMA)


@lru_cache(maxsize=50000)
def stem(folded_token: str) -> str:
    """Light, conservative suffix stripper for already-folded Gujarati tokens."""
    t = folded_token
    if not t or not (GUJ_START <= ord(t[0]) <= GUJ_END):
        return t
    for _ in range(3):
        for suf in _FSUFFIXES:
            if t.endswith(suf) and _cluster_len(t[: -len(suf)]) >= 2:
                t = t[: -len(suf)]
                break
        else:
            break
    return t


def tokenize(text: str) -> list[str]:
    """Folded tokens (Gujarati words, latin words, numbers)."""
    return _TOKEN_RE.findall(fold(text))


STOPWORDS = frozenset(stem(t) for t in tokenize(STOPWORDS_RAW)) | frozenset(tokenize(STOPWORDS_RAW))


def content_terms(text: str) -> list[str]:
    """Stemmed tokens without stopwords – the unit used by keyword retrieval."""
    out = []
    for tok in tokenize(text):
        if tok in STOPWORDS:
            continue
        st = stem(tok)
        if st in STOPWORDS or (len(st) < 2 and not st.isdigit()):
            continue
        out.append(st)
    return out


def search_key(text: str) -> str:
    """Canonical key for the question cache: order-preserving folded token string."""
    return " ".join(tokenize(text))


def char_ngrams(text: str, n: int = 3) -> list[str]:
    s = " " + " ".join(tokenize(text)) + " "
    return [s[i:i + n] for i in range(max(0, len(s) - n + 1))]


_SENT_RE = re.compile(r"(?<=[.!?।])\s+(?=[^\s])")


def split_sentences(text: str) -> list[str]:
    """Sentence segmentation that does not break decimals / abbreviations like '10 cm.'"""
    parts = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        buf = ""
        for piece in _SENT_RE.split(line):
            buf = (buf + " " + piece).strip() if buf else piece
            # do not end a sentence on a bare number like "1." (list markers)
            if re.search(r"(^|\s)\d+\.$", buf):
                continue
            parts.append(buf)
            buf = ""
        if buf:
            parts.append(buf)
    return parts


def is_gujarati_char(ch: str) -> bool:
    return GUJ_START <= ord(ch) <= GUJ_END


def validate_gujarati(text: str) -> dict:
    """Script-integrity check used to decide whether an extracted page can be trusted.

    Broken PDF text layers typically show (a) characters from unrelated blocks
    (Latin-1 supplement, IPA, PUA) and (b) orphan matras / viramas.
    """
    t = unicodedata.normalize("NFC", text or "")
    letters = [c for c in t if not c.isspace()]
    n = len(letters)
    if n == 0:
        return {"chars": 0, "gujarati_ratio": 0.0, "suspicious_ratio": 0.0, "orphan_ratio": 0.0,
                "score": 0.0, "passed": False, "reason": "empty"}
    guj = sum(1 for c in letters if is_gujarati_char(c))
    ok_other = sum(1 for c in letters if ord(c) < 0x80 or c in "–—‘’“”→×÷°±≤≥·•−√π∆Ω।")
    suspicious = n - guj - ok_other
    orphans = 0
    prev = " "
    for c in t:
        if (c in MATRAS or c == VIRAMA) and not (is_gujarati_char(prev) and prev not in MATRAS):
            orphans += 1
        prev = c
    gr, sr, orr = guj / n, suspicious / n, orphans / max(guj, 1)
    score = max(0.0, min(1.0, 1.0 - 4 * sr - 4 * orr))
    passed = gr >= 0.4 and sr <= 0.01 and orr <= 0.01
    reason = "ok" if passed else ("low-gujarati-ratio" if gr < 0.4 else "suspicious-characters" if sr > 0.01 else "orphan-matras")
    return {"chars": n, "gujarati_ratio": round(gr, 4), "suspicious_ratio": round(sr, 4),
            "orphan_ratio": round(orr, 4), "score": round(score, 4), "passed": passed, "reason": reason}


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Character error rate after whitespace collapsing and NFC."""
    r = " ".join(unicodedata.normalize("NFC", reference).split())
    h = " ".join(unicodedata.normalize("NFC", hypothesis).split())
    if not r:
        return 0.0 if not h else 1.0
    return levenshtein(r, h) / len(r)
