"""Turns rule results + grounded AI fields into the messages the user sees.
All wording is fixed text from i18n.py; only values copied from the offer
(and checked against it) are inserted."""

from __future__ import annotations

from app.channels.base import Button, Outgoing
from app.i18n import t
from app.modules.job_safety.extract import DISPLAY_FIELDS, OfferFields
from app.modules.job_safety.rules import HIGH, MEDIUM, Flag, RuleResult
from app.modules.job_safety.sources import MOHRE, agency_check_for

WHATSAPP_TEXT_MAX = 4096
_SEVERITY_ICON = {HIGH: "⛔", MEDIUM: "⚠️"}

# Which AI field answers which "missing" item.
FIELD_FOR_MISSING = {
    "salary": "salary", "hours": "working_hours", "days_off": "days_off",
    "contract": "contract_length", "accommodation": "accommodation",
}


def next_buttons(lang: str | None) -> Outgoing:
    return Outgoing(
        text=t("job_next", lang),
        buttons=[
            Button(id="job:questions", title=t("btn_questions", lang)),
            Button(id="job:agency", title=t("btn_check_agency", lang)),
            Button(id="job:check", title=t("btn_check_another", lang)),
        ],
    )


def effective_missing(rules: RuleResult, fields: OfferFields | None) -> list[str]:
    missing = list(rules.missing)
    if fields:
        missing = [m for m in missing if not getattr(fields, FIELD_FOR_MISSING.get(m, ""), None)]
    return missing


def build_report(rules: RuleResult, flags: list[Flag], fields: OfferFields | None, missing: list[str],
                 home_country: str | None, lang: str | None, *, auto: bool = False, prefix: str | None = None) -> list[Outgoing]:
    risk = HIGH if any(f.severity == HIGH for f in flags) else MEDIUM if flags else "low"
    parts: list[str] = []
    if prefix:
        parts.append(prefix)
    elif auto:
        parts.append(t("job_auto", lang))
    parts.append(t(f"job_risk_{risk}", lang))

    if flags:
        ordered = sorted(flags, key=lambda f: 0 if f.severity == HIGH else 1)
        lines = [f"{_SEVERITY_ICON[f.severity]} *{f.title}*: {f.detail}" for f in ordered]
        parts.append(t("job_found", lang) + "\n" + "\n".join(lines))

    detail_lines = []
    if fields:
        for name in DISPLAY_FIELDS:
            value = getattr(fields, name)
            if value:
                detail_lines.append(f"• {t('detail_' + name, lang)}: {value}")
    if missing:
        items = ", ".join(t(f"missing_{m}", lang) for m in missing)
        detail_lines.append(t("job_not_mentioned", lang, items=items))
    if detail_lines:
        parts.append(t("job_details_title", lang) + "\n" + "\n".join(detail_lines))

    todo = []
    if risk == HIGH:
        todo.append(t("job_todo_dont_pay", lang))
    todo.append(t("job_todo_offer_letter", lang, link=MOHRE))
    agency = agency_check_for(home_country)
    todo.append(t("job_todo_agency", lang, name=agency[0], link=agency[1]) if agency else t("job_todo_agency_generic", lang))
    if missing or risk != "low":
        todo.append(t("job_todo_ask", lang))
    parts.append(t("job_todo", lang) + "\n" + "\n".join(todo))
    parts.append(t("job_disclaimer", lang))

    text = "\n\n".join(parts)
    if len(text) > WHATSAPP_TEXT_MAX:  # never cut mid-advice: drop the offer details first
        parts = [p for p in parts if not p.startswith(t("job_details_title", lang))]
        text = "\n\n".join(parts)[:WHATSAPP_TEXT_MAX]
    return [Outgoing(text=text), next_buttons(lang)]


def questions_message(missing: list[str], lang: str | None) -> Outgoing:
    keys = [f"q_{m}" for m in missing if f"q_{m}" in ("q_salary", "q_hours", "q_days_off", "q_contract", "q_accommodation", "q_leave")]
    keys += ["q_company", "q_offer_letter", "q_visa", "q_costs", "q_passport"]
    questions = "\n".join(f"{i}. {t(k, lang)}" for i, k in enumerate(keys, 1))
    return Outgoing(
        text=t("job_questions", lang, questions=questions),
        buttons=[Button(id="job:check", title=t("btn_check_another", lang)), Button(id="menu:main", title=t("btn_menu", lang))],
    )


def agency_message(home_country: str | None, lang: str | None) -> Outgoing:
    agency = agency_check_for(home_country)
    line = (t("agency_country_line", lang, country=home_country, name=agency[0], link=agency[1])
            if agency else t("agency_country_generic", lang))
    return Outgoing(
        text=t("job_agency", lang, country_line=line, mohre=MOHRE),
        buttons=[Button(id="job:check", title=t("btn_check_offer", lang)), Button(id="menu:main", title=t("btn_menu", lang))],
    )


def intro_message(lang: str | None) -> Outgoing:
    return Outgoing(
        text=t("job_intro", lang),
        buttons=[Button(id="job:agency", title=t("btn_check_agency", lang)), Button(id="menu:main", title=t("btn_menu", lang))],
    )
