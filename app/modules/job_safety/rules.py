"""Deterministic red-flag rules for job offers.

These run on the raw offer text, locally, with no AI. They work even when the
AI model is switched off, and their wording is written by us (not generated),
so they cannot hallucinate. Each flag points to an official source.

Facts behind the rules (UAE):
- Recruitment costs must be paid by the employer, not the worker.
- Working on a visit/tourist visa is illegal for worker and employer.
- Employers may not keep a worker's passport.
- Salaries are paid through the Wage Protection System (bank/exchange), not cash.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.modules.job_safety.sources import MOHRE

HIGH, MEDIUM = "high", "medium"


@dataclass(frozen=True)
class Flag:
    code: str
    severity: str
    title: str
    detail: str
    source: str | None = None


@dataclass
class RuleResult:
    flags: list[Flag] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)   # terms the offer does not mention

    @property
    def risk(self) -> str:
        if any(f.severity == HIGH for f in self.flags):
            return HIGH
        if any(f.severity == MEDIUM for f in self.flags):
            return MEDIUM
        return "low"

    def codes(self) -> list[str]:
        return [f.code for f in self.flags]


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = re.sub(r"[‘’]", "'", t)
    return re.sub(r"[ \t]+", " ", t)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


_PAY = re.compile(r"\b(pay|paying|payment|send|deposit|transfer|fee|fees|charge|charges|cost|costs|amount)\b")
_PAY_ITEMS = re.compile(r"\b(visa|processing|registration|medical|training|ticket|air ?ticket|work permit|permit|insurance|"
                        r"application|booking|placement|recruitment|agency|documentation|attestation|interview|security deposit)\b")
_EMPLOYER_PAYS = re.compile(r"\b(free|provided|paid by|covered by|borne by|sponsored|at (the )?(company|employer)'?s? (cost|expense)|"
                            r"(company|employer|we|they) (will )?(pay|pays|cover|covers|bear|bears|provide|provides|arrange|arranges))\b")
_YOU_PAY = re.compile(r"\byou (will |must |need to |have to |should |are required to )(pay|send|deposit|transfer)\b")
_MONEY = re.compile(r"(\b(ksh|kes|inr|rs|pkr|bdt|npr|php|ugx|ngn|egp|usd|aed|dhs?|dirhams?)\b\.?\s?\d|\$\s?\d|\d[\d,.]*\s?(ksh|kes|usd|aed|dhs?|dirhams?|rs|pkr|bdt|npr|php|ugx|ngn|egp)\b)")

_VISIT_VISA = re.compile(r"\b(visit|visiting|tourist|travel|holiday) visa\b")
_WORK_WORDS = re.compile(r"\b(work|working|job|start|join|joining|employ\w*|duty|change|changed|convert|converted|transfer|later|after)\b")
_VISIT_NEGATION = re.compile(r"\b(not|never|don't|do not|cannot|can't|illegal)\b")
_VISA_LATER = re.compile(r"\bvisa (will be |would be |is )?(changed|converted|transferred|processed|arranged|done|issued) (after|later|once|when|inside|in (the )?(uae|dubai))\b")

_PERSONAL_CHANNEL = re.compile(r"\b(western union|moneygram|m-?pesa|gcash|bkash|easypaisa|jazzcash|bitcoin|crypto(currency)?|usdt|"
                               r"gift ?cards?|personal (bank )?account|cash ?app|send (the )?money to (my|this|our agent))\b")
_FREE_EMAIL = re.compile(r"[a-z0-9._%+-]+@(gmail|yahoo|hotmail|outlook|ymail|aol|proton(mail)?|icloud)\.[a-z.]+")
_CHAT_ONLY = re.compile(r"\b(contact|reach|message|text|apply|call)\b.{0,30}\b(whatsapp|telegram|signal)\b.{0,15}\bonly\b|\bonly\b.{0,20}\b(on|via|through) (whatsapp|telegram|signal)\b")
_URGENCY = re.compile(r"\b(urgent(ly)?|immediately|within (24|48|72) hours|today only|limited (slots?|seats?|vacanc(y|ies)|positions?)|"
                      r"last chance|hurry|asap|first come,? first served|offer expires)\b")
_TOO_EASY = re.compile(r"\b(no interview|without (an |any )?interview|no experience (is )?(needed|required|necessary)|"
                       r"no (qualifications?|documents?|education) (is |are )?(needed|required)|guaranteed (job|visa|placement|employment)|100% (guaranteed|sure))\b")
_PASSPORT_KEEP = re.compile(r"\b(keep|hold|retain|surrender|hand over|deposit|submit|give us|send|leave)\b.{0,25}\b(your )?original passports?\b|"
                            r"\b(keep|hold|retain|surrender|hand over|deposit|give us)\b.{0,25}\b(your )?passports?\b|"
                            r"\bpassports?\b.{0,25}\b(kept|held|retained|stay(s)?) (by|with) (the )?(company|employer|agency|sponsor|us)\b|"
                            r"\bpassports?\b.{0,40}\b(we|they|the company|the employer|the agency|sponsor) (will )?(keep|hold|retain)\b")
_PASSPORT_COPY = re.compile(r"\b(copy|copies|scan|scanned|photo|photocopy|picture)\b")
_CASH_SALARY = re.compile(r"\b(salary|salaries|wages?|pay)\b.{0,25}\bin cash\b|\bcash (salary|payment of salary|wages)\b|\bpaid in cash\b")

_HAS_SALARY = re.compile(r"\b(salary|wages?|basic pay|monthly pay|aed|dhs?|dirhams?|per month|/month|monthly)\b")
_MISSING_CHECKS = {
    "hours": re.compile(r"\b(hours?|shifts?|hrs)\b"),
    "days_off": re.compile(r"\b(day off|days off|off day|weekly off|rest day|days? per week|days? a week|weekly holiday)\b"),
    "contract": re.compile(r"\bcontract\b.{0,30}\b(\d+|one|two|three)\s*(years?|months?)\b|\b(\d+|one|two|three)[- ]?(years?|months?)\b.{0,20}\bcontract\b|\b(contract (period|duration|length))\b"),
    "accommodation": re.compile(r"\b(accommodation|housing|room|lodging|staff camp|labou?r camp)\b"),
    "leave": re.compile(r"\b(annual leave|paid leave|vacation|leave days)\b"),
}


def _flag_fees(sentences: list[str]) -> Flag | None:
    for s in sentences:
        asks = (_PAY.search(s) and _PAY_ITEMS.search(s)) or _YOU_PAY.search(s) or (_MONEY.search(s) and _PAY.search(s))
        if asks and not _EMPLOYER_PAYS.search(s):
            return Flag(
                "fees", HIGH, "They ask you to pay fees",
                "In the UAE, the employer must pay recruitment costs such as the visa, permit and medical. Real employers don't charge workers.",
                MOHRE,
            )
    return None


def _flag_visit_visa(sentences: list[str]) -> Flag | None:
    for s in sentences:
        if (_VISIT_VISA.search(s) and _WORK_WORDS.search(s) and not _VISIT_NEGATION.search(s)) or _VISA_LATER.search(s):
            return Flag(
                "visit_visa", HIGH, "Working on a visit visa",
                "Working on a visit or tourist visa is illegal in the UAE. You can be fined, jailed or deported. You need an employment visa before you start work.",
                MOHRE,
            )
    return None


def check_offer(raw: str) -> RuleResult:
    text = _norm(raw)
    sents = _sentences(text)
    res = RuleResult()
    add = res.flags.append

    if f := _flag_fees(sents):
        add(f)
    if f := _flag_visit_visa(sents):
        add(f)
    if _PERSONAL_CHANNEL.search(text):
        add(Flag("personal_payment", HIGH, "Payment through a personal channel",
                 "Requests to pay by mobile money, money transfer, crypto or gift cards are a common scam sign. Companies don't recruit this way."))
    if any(_PASSPORT_KEEP.search(s) and not _PASSPORT_COPY.search(s) for s in sents):
        add(Flag("passport", MEDIUM, "They want to keep your passport",
                 "UAE employers are not allowed to keep your passport. They may only hold it briefly for visa paperwork, then must return it.",
                 MOHRE))
    if _CASH_SALARY.search(text):
        add(Flag("cash_salary", MEDIUM, "Salary paid in cash",
                 "UAE salaries should be paid through the Wage Protection System (into a bank or exchange account), so there's a record.",
                 MOHRE))
    if _FREE_EMAIL.search(text):
        add(Flag("free_email", MEDIUM, "Uses a free email address",
                 "Real companies usually email from their own company website address, not Gmail, Yahoo or similar."))
    if _CHAT_ONLY.search(text):
        add(Flag("chat_only", MEDIUM, "Contact by chat app only",
                 "Be careful when a recruiter will only talk on WhatsApp or Telegram and has no office or company website."))
    if _URGENCY.search(text):
        add(Flag("urgency", MEDIUM, "Pressure to act fast",
                 "Scammers rush you so you don't have time to check. A real offer can wait a few days for you to verify it."))
    if _TOO_EASY.search(text):
        add(Flag("too_easy", MEDIUM, "Sounds too easy",
                 "\"No interview\", \"no experience needed\" or \"guaranteed visa\" promises are often used to lure people into paying."))
    if not _HAS_SALARY.search(text):
        add(Flag("no_salary", MEDIUM, "No salary stated",
                 "A real offer clearly states your monthly salary in AED."))

    res.missing = [k for k, pat in _MISSING_CHECKS.items() if not pat.search(text)]
    if "no_salary" in res.codes():
        res.missing.insert(0, "salary")
    return res


_OFFER_WORDS = re.compile(r"\b(salary|aed|dhs|dirhams?|visa|vacanc(y|ies)|position|hiring|recruit\w*|agency|employer|"
                          r"contract|accommodation|interview|job offer|work permit|duty hours|per month|ticket|apply now)\b")


def looks_like_offer(text: str) -> bool:
    """A pasted/forwarded job offer: long enough and several job words."""
    t = _norm(text)
    if len(t) < 120:
        return False
    return len({m.group(0) for m in _OFFER_WORDS.finditer(t)}) >= 3
