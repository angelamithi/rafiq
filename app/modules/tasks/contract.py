"""Contract switch check: compares the offer a worker was promised with the
contract they are asked to sign. The AI (if used) only transcribes the pages;
the terms below are picked out and compared by rules, so a document can't
"tell" Rafiq that everything is fine."""

from __future__ import annotations

import re
from dataclasses import dataclass

_AMOUNT = r"(\d{1,3}(?:,\d{3})+|\d{3,6})(?:\.\d{1,2})?"
_SALARY = re.compile(
    rf"(?:(?:salary|wage|pay|remuneration)[^\n\d]{{0,40}}(?:aed|dhs?|dirhams?)?\s*{_AMOUNT})"
    rf"|(?:(?:aed|dhs?)\s*{_AMOUNT}[^\n]{{0,25}}(?:per\s*month|monthly|/\s*month|a\s*month|p\.?m\.?))"
    rf"|(?:{_AMOUNT}\s*(?:aed|dhs?|dirhams?)[^\n]{{0,25}}(?:per\s*month|monthly|/\s*month|a\s*month|p\.?m\.?))",
    re.I)
_JOB = re.compile(r"(?:job\s*title|position|designation|occupation|profession|post|role)\s*[:\-]\s*([A-Za-z][A-Za-z /&\-]{1,40})", re.I)
_HOURS = re.compile(r"(\d{1,2})\s*(?:working\s*)?hours?\s*(?:per|a|/|each)\s*day|(?:hours\s*per\s*day|daily\s*hours|working\s*hours)\s*[:\-]?\s*(\d{1,2})", re.I)
_LEAVE = re.compile(r"(\d{1,2})\s*(?:calendar\s*|working\s*)?days?\s*(?:of\s*)?(?:paid\s*)?(?:annual\s*)?(?:leave|vacation|holiday)"
                    r"|(?:annual\s*leave|vacation)\s*[:\-]?\s*(\d{1,2})\s*days", re.I)
_YEARS = re.compile(r"(?:contract\s*(?:period|duration|term|length)|duration)\s*[:\-]?\s*(\d{1,2})\s*years?"
                    r"|(\d{1,2})\s*[- ]?years?\s*contract", re.I)


@dataclass
class Terms:
    salary: int | None = None
    job: str | None = None
    hours: int | None = None
    leave: int | None = None
    years: int | None = None

    def found(self) -> bool:
        return self.salary is not None or self.job is not None


def _first_int(m: re.Match[str] | None) -> int | None:
    if not m:
        return None
    for g in m.groups():
        if g:
            return int(g.replace(",", ""))
    return None


def extract(text: str) -> Terms:
    text = text or ""
    salaries = []
    for m in _SALARY.finditer(text):
        v = _first_int(m)
        if v and 300 <= v <= 200_000:
            salaries.append(v)
    job = None
    if m := _JOB.search(text):
        job = re.sub(r"\s+", " ", m.group(1)).strip(" -/").title()[:40] or None
    hours = _first_int(_HOURS.search(text))
    leave = _first_int(_LEAVE.search(text))
    years = _first_int(_YEARS.search(text))
    return Terms(salary=salaries[0] if salaries else None, job=job,
                 hours=hours if hours and 1 <= hours <= 24 else None,
                 leave=leave if leave and 0 < leave <= 60 else None,
                 years=years if years and 0 < years <= 10 else None)


@dataclass
class Row:
    key: str
    offer: str | None
    contract: str | None
    worse: bool | None        # None = can't compare


def _same_job(a: str, b: str) -> bool:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    return bool(wa & wb)


def compare(offer: Terms, contract: Terms) -> list[Row]:
    rows: list[Row] = []

    def num(key: str, o: int | None, c: int | None, lower_is_worse: bool) -> None:
        worse = None if o is None or c is None else (c < o if lower_is_worse else c > o)
        rows.append(Row(key, None if o is None else f"{o:,}", None if c is None else f"{c:,}", worse))

    num("salary", offer.salary, contract.salary, True)
    rows.append(Row("job", offer.job, contract.job,
                    None if not offer.job or not contract.job else not _same_job(offer.job, contract.job)))
    num("hours", offer.hours, contract.hours, False)
    num("leave", offer.leave, contract.leave, True)
    num("years", offer.years, contract.years, False)
    # Show only points found in at least one document.
    return [r for r in rows if r.offer is not None or r.contract is not None]
