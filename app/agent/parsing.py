"""Forgiving parsing of what users type, so they don't have to be precise."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from app.i18n import COUNTRIES, MONTHS

_MONTH_LOOKUP: dict[str, int] = {}
for _lang in MONTHS.values():
    for _i, _m in enumerate(_lang, start=1):
        _MONTH_LOOKUP[_m.lower()] = _i
        _MONTH_LOOKUP[_m.lower()[:3]] = _i
_MONTH_LOOKUP.update({"sept": 9})


def _year(y: str) -> int:
    n = int(y)
    return 2000 + n if n < 100 else n


def parse_date(text: str) -> date | None:
    """Accepts 15/03/2027, 15-3-27, 15.03.2027, 2027-03-15, 15 March 2027,
    March 15 2027, 15 Machi 2027. Day comes first (UAE and East Africa)."""
    s = unicodedata.normalize("NFKC", text or "").strip().lower()
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s).replace(",", " ")
    s = re.sub(r"\s+", " ", s)
    candidates: list[tuple[int, int, int]] = []  # (year, month, day)

    if m := re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s):
        candidates.append((int(m[1]), int(m[2]), int(m[3])))
    elif m := re.fullmatch(r"(\d{1,2})[-/. ](\d{1,2})[-/. ](\d{2}|\d{4})", s):
        a, b, y = int(m[1]), int(m[2]), _year(m[3])
        candidates.append((y, b, a))          # day/month (preferred)
        if b > 12 and a <= 12:
            candidates.append((y, a, b))      # month/day as a fallback
    elif m := re.fullmatch(r"(\d{1,2}) ([a-z]+) (\d{2}|\d{4})", s):
        if (mo := _MONTH_LOOKUP.get(m[2])) or (mo := _MONTH_LOOKUP.get(m[2][:3])):
            candidates.append((_year(m[3]), mo, int(m[1])))
    elif m := re.fullmatch(r"([a-z]+) (\d{1,2}) (\d{2}|\d{4})", s):
        if (mo := _MONTH_LOOKUP.get(m[1])) or (mo := _MONTH_LOOKUP.get(m[1][:3])):
            candidates.append((_year(m[3]), mo, int(m[2])))

    for y, mo, d in candidates:
        try:
            return date(y, mo, d)
        except ValueError:
            continue
    return None


_NAME_OK = re.compile(r"^[^\W\d_]+(?:[ '\-.][^\W\d_]+){0,3}\.?$", re.UNICODE)


def clean_name(text: str) -> str | None:
    """A first name or nickname: letters in any script, up to 4 words, 30 chars."""
    s = re.sub(r"\s+", " ", (text or "").strip())
    s = re.sub(r"^(my name is|i am|i'm|call me|jina langu ni|naitwa|niite)\s+", "", s, flags=re.IGNORECASE)
    if not (1 <= len(s) <= 30) or not _NAME_OK.match(s):
        return None
    return s[0].upper() + s[1:]


def clean_country(text: str) -> str | None:
    s = re.sub(r"\s+", " ", (text or "").strip())
    if not (2 <= len(s) <= 40) or not re.fullmatch(r"[^\W\d_]+(?:[ '\-.&][^\W\d_]+)*", s, re.UNICODE):
        return None
    for canonical in COUNTRIES:
        if s.lower() == canonical.lower():
            return canonical
    return " ".join(w[:1].upper() + w[1:] for w in s.split(" "))


def simplify(text: str) -> str:
    """Lower-case, no punctuation or emoji, single spaces: for command matching."""
    s = unicodedata.normalize("NFKC", text or "").lower()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def match_option(text: str, options: list[tuple[str, str]]) -> str | None:
    """Map typed text to an option id. options = [(id, title), ...].
    Accepts the option number ("2"), the exact title, or a unique prefix."""
    s = simplify(text)
    if not s:
        return None
    if s.isdigit() and 1 <= int(s) <= len(options):
        return options[int(s) - 1][0]
    titles = [(oid, simplify(title)) for oid, title in options]
    for oid, title in titles:
        if s == title:
            return oid
    hits = [oid for oid, title in titles if len(s) >= 3 and title.startswith(s)]
    return hits[0] if len(hits) == 1 else None
