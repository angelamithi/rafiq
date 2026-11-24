"""Unpaid wages pack: turns the user's salary record into a PDF they can take
to MOHRE, a lawyer or their embassy. Pure functions (no I/O) so it is easy to test."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.i18n import MONTHS, fmt_date, t
from app.media.pdf import Section, build_pdf
from app.modules.tasks.content import CHECKED_ON, PACK_MAX_SALARY

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_MONTH_NAMES = {m.lower(): i + 1 for i, m in enumerate(MONTHS["en"])}
_MONTH_NAMES |= {m.lower()[:3]: i + 1 for i, m in enumerate(MONTHS["en"])}
_MONTH_NAMES["sept"] = 9
_MONTH_TOKEN = re.compile(r"([a-z]+)\s*(\d{4})?\s*(half|part|partly|partial)?", re.I)


def parse_salary(text: str) -> int | None:
    nums = [float(n.replace(",", "")) for n in _NUM.findall(text or "")]
    if len(nums) != 1:
        return None
    v = int(round(nums[0]))
    return v if 100 <= v <= PACK_MAX_SALARY else None


def parse_month_year(text: str, today: date) -> date | None:
    """'03/2024', '3-2024', 'March 2024', 'mar 24' -> first day of that month (not in the future)."""
    s = (text or "").strip().lower()
    m = re.fullmatch(r"(\d{1,2})\s*[/\-. ]\s*(\d{4}|\d{2})", s)
    if m:
        mo, y = int(m[1]), int(m[2])
    else:
        m = re.fullmatch(r"([a-z]+)\s*,?\s*(\d{4}|\d{2})", s)
        if not m or (mo := _MONTH_NAMES.get(m[1]) or _MONTH_NAMES.get(m[1][:3], 0)) == 0:
            from app.agent.parsing import parse_date

            d = parse_date(text)
            return d.replace(day=1) if d and d <= today else None
        y = int(m[2])
    y = y + 2000 if y < 100 else y
    if not (1 <= mo <= 12) or not (1970 <= y <= today.year):
        return None
    d = date(y, mo, 1)
    return d if d <= today else None


def parse_months(text: str, today: date) -> dict[str, str]:
    """'September, October 2026, August half' -> {'2026-09': 'unpaid', ..., '2026-08': 'part'}.
    A month without a year is its most recent past occurrence (the current month counts)."""
    out: dict[str, str] = {}
    for tok in re.split(r"[,;&\n]|\band\b", (text or "").lower()):
        m = _MONTH_TOKEN.search(tok.strip())
        if not m:
            continue
        mo = _MONTH_NAMES.get(m[1]) or _MONTH_NAMES.get(m[1][:3])
        if not mo:
            continue
        if m[2]:
            y = int(m[2])
        else:
            y = today.year if mo <= today.month else today.year - 1
        if not (2000 <= y <= today.year) or date(y, mo, 1) > today:
            continue
        out[f"{y:04d}-{mo:02d}"] = "part" if m[3] else "unpaid"
    return out


def month_label(key: str) -> str:
    y, m = key.split("-")
    return f"{MONTHS['en'][int(m) - 1]} {y}"


def gratuity(salary: int, start: date | None, today: date, lang: str | None) -> tuple[str, float | None]:
    if not start:
        return t("pack_to_confirm", lang), None
    years = max(0.0, (today - start).days / 365.25)
    if years < 1:
        return t("pack_under_year", lang), None
    days = 21 * min(years, 5) + 30 * max(0.0, years - 5)
    amount = min(salary / 30 * days, salary * 24)
    return t("pack_gratuity_val", lang, amount=f"{amount:,.0f}", years=f"{years:.1f}"), amount


@dataclass
class PackFacts:
    name: str
    employer: str
    salary: int
    start: date | None
    log: dict[str, str]          # {"2026-10": "unpaid" | "part" | "paid"}
    domestic: bool
    home_country: str | None
    sector: str | None
    received: dict[str, int] = field(default_factory=dict)   # amounts actually received, when known
    agreed: set[str] = field(default_factory=set)            # shortfalls the worker agreed to

    def owed(self, month: str) -> int | None:
        st = self.log.get(month)
        if month in self.agreed or st == "paid":
            return 0
        if st == "unpaid":
            return self.salary
        got = self.received.get(month)
        return max(0, self.salary - got) if got is not None else None


def summary(f: PackFacts, today: date, lang: str | None) -> dict[str, str]:
    unpaid = [k for k, v in sorted(f.log.items()) if v == "unpaid" and k not in f.agreed]
    part = [k for k, v in sorted(f.log.items()) if v == "part" and k not in f.agreed]
    g_text, _ = gratuity(f.salary, f.start, today, lang)
    total = sum(f.owed(k) or 0 for k in f.log)
    return {
        "unpaid": ", ".join(month_label(k) for k in unpaid) or "-",
        "part": ", ".join(month_label(k) for k in part) or "-",
        "owed": f"{total:,}",
        "gratuity": g_text,
        "months_text": ", ".join([*(month_label(k) for k in unpaid), *(f"{month_label(k)} (part)" for k in part)]) or "-",
    }


def build(f: PackFacts, today: date, lang: str | None) -> bytes:
    s = summary(f, today, lang)
    status = {"unpaid": t("pack_status_unpaid", lang), "part": t("pack_status_part", lang),
              "paid": t("pack_status_paid", lang)}
    rows = [[t("pack_col_month", lang), t("pack_col_status", lang), "Received (AED)", t("pack_col_owed", lang)]]
    for k, v in sorted(f.log.items()):
        o = f.owed(k)
        got = f.received.get(k)
        st = "Agreed deduction" if k in f.agreed else status[v]
        rows.append([month_label(k), st, f"{got:,}" if got is not None else ("0" if v == "unpaid" else "-"),
                     t("pack_to_confirm", lang) if o is None else f"{o:,}"])
    start = f"{MONTHS['en'][f.start.month - 1]} {f.start.year}" if f.start else "-"
    worker = [
        ["Item", "Details"],
        ["Worker", f.name],
        ["Home country", f.home_country or "-"],
        ["Employer", f.employer],
        ["Type of work", "Domestic worker" if f.domestic else (f.sector or "-").replace("_", " ").title()],
        ["Started", start],
        ["Monthly salary (contract)", f"AED {f.salary:,}"],
    ]
    owed = [
        ["Item", "Amount"],
        ["Total owed (known amounts)", f"AED {s['owed']}"],
        ["Months with an unknown amount", ", ".join(month_label(k) for k in f.log if f.owed(k) is None) or "-"],
        ["End-of-service gratuity (if the job ends)", s["gratuity"]],
    ]
    letter = t("pack_letter", lang, name=f.name, employer=f.employer, start=start, salary=f"{f.salary:,}",
               months=s["months_text"], owed=s["owed"], date=fmt_date(today, lang))
    rights = t("pack_rights_domestic" if f.domestic else "pack_rights_private", lang, checked=CHECKED_ON)
    sections = [
        Section(t("pack_h_worker", lang), table=worker),
        Section(t("pack_h_months", lang),
                ["Recorded by the worker through Rafiq's monthly salary check-ins and their own account."], table=rows),
        Section(t("pack_h_owed", lang), table=owed),
        Section(t("pack_h_rights", lang), [rights]),
        Section(t("pack_h_next", lang), [t("pack_next", lang)]),
        Section(t("pack_h_letter", lang), [letter], page_break_before=True),
    ]
    return build_pdf(t("pack_title", lang), t("pack_subtitle", lang, date=fmt_date(today, lang)), sections,
                     t("pack_footer", lang))
