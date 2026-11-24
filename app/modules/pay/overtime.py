"""Overtime calculator (private sector, Federal Decree-Law 33 of 2021, Article 19).

Rules checked 2026-11-24 (MOHRE guidance; u.ae):
- Normal hours: 8 a day or 48 a week. Overtime may not exceed 2 hours a day, and
  total hours may not exceed 144 every 3 weeks.
- Hourly wage = basic salary / 30 / 8 (MOHRE's own formula). Basic salary only:
  allowances are not included.
- Overtime: hourly wage + at least 25%. Between 10pm and 4am: + at least 50%
  (not for shift workers).
- Work on the rest day: a substitute rest day, or the day's wage + at least 50%.
- Domestic workers are under a different law (Decree-Law 9 of 2022): this
  calculator does not apply to them.

Rules only, no AI: the numbers come from what the worker types, and every
result is an *estimate of the minimum*, never a decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.i18n import S

CHECKED = "2026-11-24"
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
MIN_BASIC, MAX_BASIC = 300, 200_000
MAX_HOURS_MONTH = 400
MAX_REST_DAYS = 31

STRINGS: dict[str, dict[str, str]] = {
    "ot_ask": {"en": (
        "⏱️ *Overtime calculator* (private sector)\n\n"
        "Send up to 4 numbers for *one month*, in this order:\n"
        "1. Your *basic* salary (AED, without allowances)\n"
        "2. Extra hours worked (normal time)\n"
        "3. Extra hours between *10pm and 4am* (0 if none)\n"
        "4. Rest days worked with *no* day off in return (0 if none)\n\n"
        "Example: *1500 20 4 1*")},
    "ot_bad": {"en": "Please send the numbers like *1500 20 4 1* (basic salary, extra hours, night hours, rest days)."},
    "ot_result": {"en": (
        "⏱️ *Overtime estimate · basic AED {basic}*\n"
        "• Hourly wage: {basic} ÷ 30 ÷ 8 = *AED {hourly}*\n"
        "{lines}"
        "• *Total, at least: AED {total}*\n\n"
        "{warn}"
        "_An estimate of the minimum the law sets (Article 19), from the numbers you gave. Allowances aren't included; "
        "some roles are treated differently. MOHRE (80084) decides any dispute. Rules checked {checked}._")},
    "ot_line_normal": {"en": "• {h} extra hours × AED {rate} (+25%) = AED {amt}\n"},
    "ot_line_night": {"en": "• {h} night hours (10pm–4am) × AED {rate} (+50%) = AED {amt}\n"},
    "ot_line_rest": {"en": "• {d} rest day(s) × AED {rate} (day's wage +50%) = AED {amt}\n"},
    "ot_warn_limit": {"en": "⚠️ {h} extra hours is more than 2 hours a day on average over a month. The law limits overtime to "
                            "2 hours a day (and 144 hours in total every 3 weeks), except to prevent serious loss or accidents.\n\n"},
    "ot_domestic": {"en": (
        "⏱️ Overtime rules for the private sector (Labour Law) don't apply to domestic workers, who are covered by "
        "a separate law (Decree-Law 9 of 2022). Your hours and rest are set by that law and your contract. "
        "If you work very long hours without rest, call MOHRE's free line *80084* for advice.")},
    "btn_ot_complaint": {"en": "Draft hours complaint"},
    "btn_ot_again": {"en": "Calculate again"},
}
S.update(STRINGS)


@dataclass(frozen=True)
class Overtime:
    basic: float
    hours: float
    night: float
    rest_days: float

    @property
    def hourly(self) -> float:
        return self.basic / 30 / 8

    @property
    def normal_pay(self) -> float:
        return self.hourly * 1.25 * self.hours

    @property
    def night_pay(self) -> float:
        return self.hourly * 1.5 * self.night

    @property
    def rest_pay(self) -> float:
        return self.basic / 30 * 1.5 * self.rest_days

    @property
    def total(self) -> float:
        return self.normal_pay + self.night_pay + self.rest_pay

    @property
    def over_limit(self) -> bool:
        return self.hours + self.night > 2 * 26          # more than 2 h a day on average over ~26 working days


def parse(text: str) -> Overtime | None:
    nums = [float(n.replace(",", "")) for n in _NUM.findall(text or "")]
    if not (2 <= len(nums) <= 4):
        return None
    basic, hours, night, rest = (nums + [0.0, 0.0])[:4]
    if not (MIN_BASIC <= basic <= MAX_BASIC) or not (0 <= hours <= MAX_HOURS_MONTH) or not (0 <= night <= MAX_HOURS_MONTH) \
            or not (0 <= rest <= MAX_REST_DAYS) or hours + night + rest == 0:
        return None
    return Overtime(basic, hours, night, rest)


def _m(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".") if x != int(x) else f"{x:,.0f}"


def result_text(o: Overtime, t, lang: str | None) -> str:  # type: ignore[no-untyped-def]
    lines = ""
    if o.hours:
        lines += t("ot_line_normal", lang, h=_m(o.hours), rate=_m(round(o.hourly * 1.25, 2)), amt=_m(round(o.normal_pay, 2)))
    if o.night:
        lines += t("ot_line_night", lang, h=_m(o.night), rate=_m(round(o.hourly * 1.5, 2)), amt=_m(round(o.night_pay, 2)))
    if o.rest_days:
        lines += t("ot_line_rest", lang, d=_m(o.rest_days), rate=_m(round(o.basic / 30 * 1.5, 2)), amt=_m(round(o.rest_pay, 2)))
    warn = t("ot_warn_limit", lang, h=_m(o.hours + o.night)) if o.over_limit else ""
    return t("ot_result", lang, basic=_m(o.basic), hourly=_m(round(o.hourly, 2)), lines=lines, total=_m(round(o.total, 2)),
             warn=warn, checked=CHECKED)
