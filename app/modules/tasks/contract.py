"""Contract switch check: compares the offer a worker was promised with the
contract they are asked to sign. The AI (if used) only transcribes the pages;
the terms below are picked out and compared by rules, so a document can't
"tell" Rafiq that everything is fine.

Reads English and Arabic (MOHRE contracts are often bilingual; some pages are
Arabic only), with Arabic-Indic digits. Salaries are compared like with like:
basic with basic, total with total (stated, or basic + listed allowances). A
contract that lists only a basic salary promises only that much in writing."""

from __future__ import annotations

import re
from dataclasses import dataclass

_AMOUNT = r"(\d{1,3}(?:,\d{3})+|\d{3,6})(?:\.\d{1,2})?"
_CUR = r"(?:aed|dhs?|dirhams?|درهم|د\.إ)"
_PERIOD = r"(?:per\s*month|monthly|/\s*month|a\s*month|p\.?m\.?|شهري[اًا]?|في الشهر|بالشهر)"

# What kind of salary figure a line gives. Order matters: an allowance line isn't a salary.
_KIND_ALLOW = re.compile(r"allowance|housing|accommodation|transport|food|other\s*benefits|بدل", re.I)
_KIND_TOTAL = re.compile(r"total|gross|package|all[\s-]*inclusive|الإجمالي|اجمالي|إجمالي|المجموع|الكلي", re.I)
_KIND_BASIC = re.compile(r"basic|الأساسي|الاساسي", re.I)
_SALARY_WORD = re.compile(r"salary|wage|pay|remuneration|راتب|الراتب|أجر|الأجر|اجر|الاجر", re.I)
_AMOUNT_RX = re.compile(rf"(?:{_CUR}\s*)?{_AMOUNT}(?:\s*{_CUR})?", re.I)

_JOB = re.compile(r"(?:job\s*title|position|designation|occupation|profession|post|role)\s*[:\-]\s*([A-Za-z][A-Za-z /&\-]{1,40})", re.I)
_JOB_AR = re.compile(r"(?:المسمى\s*الوظيفي|المهنة|الوظيفة)\s*[:\-]?\s*([؀-ۿ][؀-ۿ ]{1,40})")
_HOURS = re.compile(r"(\d{1,2})\s*(?:working\s*)?hours?\s*(?:per|a|/|each)\s*day|(?:hours\s*per\s*day|daily\s*hours|working\s*hours)\s*[:\-]?\s*(\d{1,2})"
                    r"|ساعات\s*العمل[^\d\n]{0,20}(\d{1,2})|(\d{1,2})\s*ساع[ةات]+\s*(?:يومي[اًا]?|في اليوم)", re.I)
_LEAVE = re.compile(r"(\d{1,2})\s*(?:calendar\s*|working\s*)?days?\s*(?:of\s*)?(?:paid\s*)?(?:annual\s*)?(?:leave|vacation|holiday)"
                    r"|(?:annual\s*leave|vacation)\s*[:\-]?\s*(\d{1,2})\s*days"
                    r"|الإجازة\s*السنوية[^\d\n]{0,20}(\d{1,2})|إجازة\s*سنوية[^\d\n]{0,20}(\d{1,2})|(\d{1,2})\s*يوم[اًا]?\s*(?:إجازة|اجازة)", re.I)
_YEARS = re.compile(r"(?:contract\s*(?:period|duration|term|length)|duration)\s*[:\-]?\s*(\d{1,2})\s*years?"
                    r"|(\d{1,2})\s*[- ]?years?\s*contract"
                    r"|مدة\s*العقد[^\d\n]{0,20}(\d{1,2})\s*(?:سنة|سنوات|عام|أعوام)", re.I)
_YEARS_AR_TWO = re.compile(r"مدة\s*العقد[^\n]{0,20}(?:سنتان|سنتين|عامان|عامين)")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٬٫", "01234567890123456789,.")


@dataclass
class Terms:
    salary: int | None = None        # a salary figure that doesn't say if it is basic or total
    job: str | None = None
    hours: int | None = None
    leave: int | None = None
    years: int | None = None
    basic: int | None = None
    total: int | None = None
    allowances: int | None = None    # sum of the allowances listed

    def found(self) -> bool:
        return self.best_salary() is not None or self.job is not None

    def best_salary(self) -> int | None:
        return self.total or self.salary or self.basic

    def total_pay(self) -> int | None:
        """Total monthly pay: stated, or basic + allowances when both are listed."""
        if self.total:
            return self.total
        if self.basic and self.allowances:
            return self.basic + self.allowances
        return None


def _first_int(m: re.Match[str] | None) -> int | None:
    if not m:
        return None
    for g in m.groups():
        if g:
            return int(g.replace(",", ""))
    return None


def normalise(text: str) -> str:
    """Arabic-Indic digits and separators to ASCII, so rules can read both languages."""
    return (text or "").translate(_AR_DIGITS)


def _salary_figures(text: str) -> tuple[int | None, int | None, int | None, int | None]:
    """(basic, total, allowances, unspecified) from lines that mention pay. English or Arabic."""
    basic = total = plain = None
    allowances = 0
    for line in re.split(r"[\n;|]", text):
        if not (_SALARY_WORD.search(line) or _KIND_ALLOW.search(line) or re.search(_CUR, line, re.I)):
            continue
        for m in _AMOUNT_RX.finditer(line):
            v = int(m.group(1).replace(",", ""))
            if not (100 <= v <= 200_000):
                continue
            before = line[max(0, m.start() - 45):m.start()]
            has_money = bool(re.search(_CUR, m.group(0), re.I) or re.search(_PERIOD, line[m.end():m.end() + 25], re.I)
                             or _SALARY_WORD.search(before) or _KIND_ALLOW.search(before))
            if not has_money:
                continue
            if _KIND_ALLOW.search(before) and not _KIND_TOTAL.search(before):
                allowances += v
            elif _KIND_TOTAL.search(before):
                total = total or v
            elif _KIND_BASIC.search(before):
                basic = basic or v
            elif v >= 300:
                plain = plain or v
    return basic, total, allowances or None, plain


def extract(text: str) -> Terms:
    text = normalise(text)
    basic, total, allowances, plain = _salary_figures(text)
    if plain and plain in (basic, total):
        plain = None
    job = None
    if m := _JOB.search(text):                        # prefer the English title on bilingual contracts
        job = re.sub(r"\s+", " ", m.group(1)).strip(" -/").title()[:40] or None
    elif m := _JOB_AR.search(text):
        job = re.sub(r"\s+", " ", m.group(1)).strip()[:40] or None
    hours = _first_int(_HOURS.search(text))
    leave = _first_int(_LEAVE.search(text))
    years = _first_int(_YEARS.search(text)) or (2 if _YEARS_AR_TWO.search(text) else None)
    return Terms(salary=plain, job=job, basic=basic, total=total, allowances=allowances,
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


def _is_arabic(s: str | None) -> bool:
    return bool(s and re.search(r"[؀-ۿ]", s))


def compare(offer: Terms, contract: Terms) -> list[Row]:
    """Like with like: basic vs basic, total vs total. A figure whose kind isn't clear is
    compared with the other side's total, never with a basic salary alone."""
    rows: list[Row] = []

    def num(key: str, o: int | None, c: int | None, lower_is_worse: bool, comparable: bool = True) -> None:
        worse = None if o is None or c is None or not comparable else (c < o if lower_is_worse else c > o)
        rows.append(Row(key, None if o is None else f"{o:,}", None if c is None else f"{c:,}", worse))

    def written_total(x: Terms) -> int | None:
        # A document that lists only a basic salary (no allowances, no total) promises only that much in writing.
        return x.total_pay() or x.salary or (x.basic if x.basic and not x.allowances else None)

    if offer.basic and contract.basic:
        num("salary_basic", offer.basic, contract.basic, True)
    o_total, c_total = written_total(offer), written_total(contract)
    if o_total and c_total and (o_total, c_total) != (offer.basic, contract.basic):
        key = "salary_total" if (offer.total_pay() or contract.total_pay() or offer.basic or contract.basic) else "salary"
        if contract.basic and not (contract.total_pay() or contract.salary):
            key = "salary_basic_only"
        num(key, o_total, c_total, True)
    elif (o_total or c_total) and not any(r.key.startswith("salary") for r in rows):
        num("salary", o_total, c_total, True)
    jobs_comparable = bool(offer.job and contract.job) and _is_arabic(offer.job) == _is_arabic(contract.job)
    rows.append(Row("job", offer.job, contract.job, None if not jobs_comparable else not _same_job(offer.job, contract.job)))
    num("hours", offer.hours, contract.hours, False)
    num("leave", offer.leave, contract.leave, True)
    num("years", offer.years, contract.years, False)
    # Show only points found in at least one document.
    return [r for r in rows if r.offer is not None or r.contract is not None]
