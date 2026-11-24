"""Salary amounts: promised vs received, gap detection and payslip reading.

What's stored (encrypted, in the user's toolkit): the contract salary, the
amount received per month, and the months where a shortfall was an agreed
deduction. A payslip photo is read once (AI transcribes, rules pick the
numbers) and is not kept.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.db import repo
from app.i18n import MONTHS, S, t

MIN_SALARY, MAX_SALARY = 300, 200_000

STRINGS: dict[str, dict[str, str]] = {
    "pay_m_slip": {"en": "Read my payslip"},
    "pay_m_slip_d": {"en": "Check deductions and the amount you got"},
    "pay_m_gaps": {"en": "What I'm owed"},
    "pay_m_gaps_d": {"en": "Promised vs received, month by month"},
    "pay_ask_contract": {"en": "What *monthly salary* does your contract say, in AED? (just the number, e.g. *1500*)"},
    "pay_ask_got_paid": {"en": "Did you get the full *AED {salary}* for {month}?"},
    "pay_ask_got_part": {"en": "How much did you receive for {month}, in AED? (just the number)"},
    "btn_full_amount": {"en": "Yes, full amount"},
    "btn_less": {"en": "Less than that"},
    "pay_bad_amount": {"en": "Please type just the amount in AED, e.g. *1200*."},
    "pay_got_saved": {"en": "Saved: AED {got} received for {month}."},
    "pay_gap_found": {"en": (
        "⚠️ That's *AED {gap} less* than your contract salary of AED {salary}.\n"
        "Was this an *agreed deduction*? For example an advance you asked for, or housing you agreed to in writing."
    )},
    "btn_gap_agreed": {"en": "Agreed deduction"},
    "btn_gap_not": {"en": "Not agreed"},
    "btn_gap_unsure": {"en": "Not sure"},
    "pay_gap_agreed": {"en": "OK, I've noted it as an agreed deduction, so it isn't counted as owed. Keep the paper you signed."},
    "pay_gap_owed": {"en": (
        "Noted. Deductions need your written agreement or a legal reason, and can't take more than half your wage.\n\n"
        "*Owed so far:* about AED {total} ({months}).\n"
        "Want me to build your evidence pack or open a case to track it?"
    )},
    "pay_pattern": {"en": "🔁 This is the *{n}th month* in a row with less than your contract salary. That's a pattern worth acting on."},
    "btn_build_pack": {"en": "Build evidence pack"},
    "btn_open_case": {"en": "Open a case"},
    "pay_gaps_head": {"en": "💰 *Promised vs received* (contract: AED {salary}/month)"},
    "pay_gaps_row": {"en": "• {month}: {got} {mark}"},
    "pay_gaps_none": {"en": "No gaps recorded. 👍 Tell me each month what you received and I'll keep watch."},
    "pay_gaps_total": {"en": "*Owed: about AED {total}.*"},
    "pay_gaps_unknown": {"en": "Some months were part-paid but I don't know the amount. Tap the month in Salary watch to add it."},
    "pay_got_none": {"en": "nothing"},
    "pay_got_unknown": {"en": "part (amount unknown)"},
    "pay_slip_ask": {"en": "📄 Send a clear photo or PDF of your payslip. I read it once and don't keep it."},
    "pay_slip_need_file": {"en": "Please send the payslip as a *photo* or *PDF*, or paste its text."},
    "pay_slip_unreadable": {"en": "I couldn't find the amounts on that payslip. Try a clearer photo of the whole page."},
    "pay_slip_read": {"en": "📄 *Your payslip{month}*\n{lines}"},
    "pay_slip_line": {"en": "• {label}: AED {amount}"},
    "pay_slip_net": {"en": "Net pay (what you got)"},
    "pay_slip_gross": {"en": "Gross pay"},
    "pay_slip_basic": {"en": "Basic salary"},
    "pay_slip_vs": {"en": "Your contract says AED {salary}. Net pay is *AED {gap} less*."},
    "pay_slip_vs_ok": {"en": "That matches your contract salary of AED {salary}. 👍"},
    "pay_slip_save": {"en": "Save AED {net} as received for {month}?"},
    "btn_save": {"en": "Save it"},
    "pay_slip_note": {"en": "I read this automatically. Check the numbers against the paper."},
}
S.update(STRINGS)

_NUM = r"(\d{1,3}(?:,\d{3})+|\d{2,6})(?:\.\d{1,2})?"
_LINE_AMT = re.compile(_NUM)
_LABELS = {
    "net": re.compile(r"net\s*(pay|salary|amount|payable)|take\s*home|amount\s*(paid|credited)|total\s*paid", re.I),
    "gross": re.compile(r"gross|total\s*earnings|total\s*salary", re.I),
    "basic": re.compile(r"\bbasic\b", re.I),
}
_DEDUCT = re.compile(r"deduct|advance|fine|absence|absent|penalt|loan|accommodation|housing\s*deduct|food|uniform", re.I)
_MONTH_WORDS = {m.lower(): i + 1 for i, m in enumerate(MONTHS["en"])} | {m.lower()[:3]: i + 1 for i, m in enumerate(MONTHS["en"])}


def parse_amount(text: str) -> int | None:
    nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")]
    if len(nums) != 1:
        return None
    v = int(round(nums[0]))
    return v if 0 <= v <= MAX_SALARY else None


def _amount_in(line: str) -> int | None:
    vals = [int(m.group(1).replace(",", "")) for m in _LINE_AMT.finditer(line)]
    vals = [v for v in vals if 10 <= v <= MAX_SALARY and not (1990 <= v <= 2100)]   # skip years
    return vals[-1] if vals else None


@dataclass
class Payslip:
    net: int | None = None
    gross: int | None = None
    basic: int | None = None
    deductions: list[tuple[str, int]] = field(default_factory=list)
    month: str | None = None       # "2026-10"

    def found(self) -> bool:
        return self.net is not None or self.gross is not None


def read_payslip(text: str, today: date) -> Payslip:
    slip = Payslip()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        amt = _amount_in(line)
        if amt is None:
            continue
        if _LABELS["net"].search(line) and slip.net is None:
            slip.net = amt
        elif _LABELS["gross"].search(line) and slip.gross is None:
            slip.gross = amt
        elif _LABELS["basic"].search(line) and slip.basic is None:
            slip.basic = amt
        elif _DEDUCT.search(line) and len(slip.deductions) < 6:
            label = re.sub(r"[\d,.:]+|aed|dhs?", "", line, flags=re.I).strip(" -:|")[:30] or "Deduction"
            slip.deductions.append((label.title(), amt))
    m = re.search(r"\b([A-Za-z]{3,9})[\s\-/,]+(\d{4})\b", text or "")
    if m and (mo := _MONTH_WORDS.get(m.group(1).lower()) or _MONTH_WORDS.get(m.group(1).lower()[:3])):
        y = int(m.group(2))
        if 2000 <= y <= today.year:
            slip.month = f"{y:04d}-{mo:02d}"
    if slip.net is None and slip.gross is not None and slip.deductions:
        slip.net = max(0, slip.gross - sum(a for _, a in slip.deductions))
    return slip


# ---------------------------------------------------------------- the record

def contract_salary(user) -> int | None:  # type: ignore[no-untyped-def]
    v = repo.toolkit(user).get("salary")
    return int(v) if isinstance(v, (int, float)) and v > 0 else None


def received(user) -> dict[str, int]:  # type: ignore[no-untyped-def]
    r = repo.toolkit(user).get("received") or {}
    return {k: int(v) for k, v in r.items() if isinstance(v, (int, float))}


def agreed_months(user) -> set[str]:  # type: ignore[no-untyped-def]
    return set(repo.toolkit(user).get("agreed") or [])


def record_received(user, month: str, got: int) -> None:  # type: ignore[no-untyped-def]
    kit = repo.toolkit(user)
    rec = kit.get("received") or {}
    rec[month] = got
    kit["received"] = dict(sorted(rec.items())[-24:])
    repo.save_toolkit(user, kit)
    salary = contract_salary(user)
    if got == 0:
        repo.set_pay_status(user, month, "unpaid")
    elif salary and got < salary:
        repo.set_pay_status(user, month, "part")
    else:
        repo.set_pay_status(user, month, "paid")


def mark_agreed(user, month: str, agreed: bool) -> None:  # type: ignore[no-untyped-def]
    kit = repo.toolkit(user)
    months = set(kit.get("agreed") or [])
    (months.add if agreed else months.discard)(month)
    kit["agreed"] = sorted(months)
    repo.save_toolkit(user, kit)


def gaps(user) -> tuple[list[tuple[str, int | None]], int]:  # type: ignore[no-untyped-def]
    """[(month, owed or None if unknown)], total known owed. Agreed deductions aren't owed."""
    salary = contract_salary(user)
    got, agreed = received(user), agreed_months(user)
    out: list[tuple[str, int | None]] = []
    for month, status in sorted(repo.pay_log(user).items()):
        if month in agreed:
            continue
        if status == "unpaid":
            out.append((month, salary))
        elif month in got and salary and got[month] < salary:
            out.append((month, salary - got[month]))
        elif status == "part":
            out.append((month, None))
    return out, sum(v for _, v in out if v)


def shortfall_streak(user) -> int:  # type: ignore[no-untyped-def]
    """How many of the most recent recorded months in a row were short or unpaid."""
    owed = {m for m, _ in gaps(user)[0]}
    n = 0
    for month, _ in sorted(repo.pay_log(user).items(), reverse=True):
        if month not in owed:
            break
        n += 1
    return n


def label(month: str) -> str:
    y, m = month.split("-")
    return f"{MONTHS['en'][int(m) - 1]} {y}"


def gaps_message(user, lang: str | None) -> str:  # type: ignore[no-untyped-def]
    salary = contract_salary(user)
    rows, total = gaps(user)
    if not salary or not rows:
        return t("pay_gaps_none", lang)
    got = received(user)
    lines = [t("pay_gaps_head", lang, salary=f"{salary:,}")]
    unknown = False
    for month, owed in rows:
        if owed is None:
            unknown = True
            g = t("pay_got_unknown", lang)
        else:
            g = f"AED {got.get(month, 0):,}" if got.get(month) else t("pay_got_none", lang)
        lines.append(t("pay_gaps_row", lang, month=label(month), got=g, mark=f"(owed AED {owed:,})" if owed else ""))
    lines.append(t("pay_gaps_total", lang, total=f"{total:,}"))
    if unknown:
        lines.append(t("pay_gaps_unknown", lang))
    return "\n".join(lines)
