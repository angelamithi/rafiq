"""LangGraph node for Module 6: Pay & Rights.

Deterministic: fixed, sourced text. Complaint drafts are filled from a
template plus the user's own salary record; Rafiq never sends them anywhere
(no outward tool exists). The only free text read is the gratuity input
(two numbers), which is parsed and never stored.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import MONTHS, t
from app.modules.pay import content  # noqa: F401  (registers the text)
from app.modules.pay.content import GRATUITY_MAX_SALARY, GRATUITY_MAX_YEARS, GRATUITY_MIN_SALARY, MOHRE
from app.security.tool_policy import authorize

NODE = "pay"
AWAIT_GRATUITY = "pay:await_gratuity"
MENU = ("watch", "late", "complaint", "rights", "gratuity", "proof")
PROBLEMS = ("unpaid", "late", "passport", "hours", "contract", "final")
STATUS_CMDS = {"pay_paid": "paid", "pay_part": "part", "pay_unpaid": "unpaid"}
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


# ---------------------------------------------------------------- helpers

def pay_month(today: date) -> str:
    """The month whose salary is due now: last calendar month."""
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{y:04d}-{m:02d}"


def month_label(key: str, lang: str | None) -> str:
    y, m = key.split("-")
    return f"{MONTHS['en'][int(m) - 1]} {y}"


def is_domestic(user) -> bool:  # type: ignore[no-untyped-def]
    return user.sector == "domestic"


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _events(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


def _back(lang: str | None, *extra: Button) -> list[Button]:
    return [*extra, Button(id="menu:pay", title=t("btn_pay_menu", lang)), Button(id="menu:main", title=t("btn_menu", lang))][:3]


def _with_footer(body: str, lang: str | None) -> str:
    return f"{body}\n\n{t('pay_footer', lang)}"


# ---------------------------------------------------------------- screens

def pay_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"pay:{k}", title=t(f"pay_m_{k}", lang), description=t(f"pay_m_{k}_d", lang)) for k in MENU]
    return Outgoing(text=t("pay_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def record_lines(user, lang: str | None) -> str:  # type: ignore[no-untyped-def]
    log = repo.pay_log(user)
    if not log:
        return t("pay_watch_record_empty", lang)
    lines = [f"• {month_label(m, lang)}: {t(f'pay_status_{s}', lang)}" for m, s in sorted(log.items(), reverse=True)[:6]]
    return t("pay_watch_record", lang, lines="\n".join(lines))


def watch_screen(user, today: date, lang: str | None, *, header: str | None = None) -> Outgoing:  # type: ignore[no-untyped-def]
    on = repo.pay_watch_on(user)
    parts = [p for p in (header, t("pay_watch_intro", lang)) if p]
    parts.append(t("pay_watch_when_domestic" if is_domestic(user) else "pay_watch_when_private", lang))
    parts.append(t("pay_watch_status_on" if on else "pay_watch_status_off", lang))
    parts.append(record_lines(user, lang))
    parts.append(t("pay_watch_ask", lang, month=month_label(pay_month(today), lang)))
    rows = [ListRow(id=f"pay:{s}", title=t(f"pay_row_{s}", lang), description=t(f"pay_row_{s}_d", lang))
            for s in ("paid", "part", "unpaid")]
    toggle = "off" if on else "on"
    rows.append(ListRow(id=f"pay:{toggle}", title=t(f"pay_row_{toggle}", lang), description=t(f"pay_row_{toggle}_d", lang)))
    return Outgoing(text="\n\n".join(parts), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def late_message(user, lang: str | None) -> Outgoing:  # type: ignore[no-untyped-def]
    key = "pay_late_domestic" if is_domestic(user) else "pay_late_private"
    return Outgoing(text=_with_footer(t(key, lang), lang),
                    buttons=[Button(id="pay:complaint", title=t("btn_write_complaint", lang)),
                             Button(id="pay:how", title=t("btn_how_to_complain", lang)),
                             Button(id="menu:pay", title=t("btn_pay_menu", lang))])


def how_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("pay_how_to_complain", lang, mohre=MOHRE),
                    buttons=_back(lang, Button(id="pay:complaint", title=t("btn_write_complaint", lang))))


def complaint_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"pay:c:{k}", title=t(f"pay_c_{k}", lang), description=t(f"pay_c_{k}_d", lang)) for k in PROBLEMS]
    return Outgoing(text=t("pay_complaint_pick", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def complaint_draft(user, problem: str, lang: str | None) -> list[Outgoing]:  # type: ignore[no-untyped-def]
    """Template only. Personal values: the user's own name (if saved) and their
    own salary record. Everything else is a [placeholder] they fill in."""
    name = repo.get_display_name(user) or t("pay_name_placeholder", lang)
    details = t(f"pay_d_{problem}", lang)
    if problem == "unpaid":
        missing = [month_label(m, lang) for m, s in sorted(repo.pay_log(user).items()) if s in ("unpaid", "part")]
        details = t("pay_d_unpaid", lang, months=", ".join(missing)) if missing else t("pay_d_unpaid_none", lang)
    body = t("pay_draft_body", lang, subject=t(f"pay_d_{problem}_subject", lang), name=name, details=details,
             request=t(f"pay_d_{problem}_request", lang))
    return [Outgoing(text=t("pay_draft_head", lang)), Outgoing(text=body),
            Outgoing(text=t("pay_draft_tail", lang), buttons=_back(lang, Button(id="pay:how", title=t("btn_how_to_complain", lang))))]


def rights_message(user, lang: str | None) -> Outgoing:  # type: ignore[no-untyped-def]
    key = "pay_rights_domestic" if is_domestic(user) else "pay_rights_private"
    return Outgoing(text=_with_footer(t(key, lang), lang), buttons=_back(lang))


def proof_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("pay_proof", lang), buttons=_back(lang, Button(id="pay:watch", title=t("btn_salary_watch", lang))))


def _fmt(n: float) -> str:
    return f"{n:,.0f}" if n == int(n) else f"{n:,.1f}"


def gratuity_estimate(text: str, lang: str | None) -> Outgoing | None:
    """'2000 3.5' -> estimate. Returns None if the input can't be understood."""
    nums = [float(n.replace(",", "")) for n in _NUM.findall(text or "")]
    if len(nums) != 2:
        return None
    salary, years = nums
    if not (GRATUITY_MIN_SALARY <= salary <= GRATUITY_MAX_SALARY) or not (0 <= years <= GRATUITY_MAX_YEARS):
        return None
    if years < 1:
        return Outgoing(text=t("pay_gratuity_under_year", lang, years=_fmt(years)), buttons=_back(lang))
    days = 21 * min(years, 5) + 30 * max(0.0, years - 5)
    amount = min(salary / 30 * days, salary * 24)   # capped at 2 years' pay
    return Outgoing(text=_with_footer(t("pay_gratuity_result", lang, salary=_fmt(salary), years=_fmt(years),
                                        amount=f"{amount:,.0f}", days=_fmt(round(days, 1))), lang),
                    buttons=_back(lang))


# ---------------------------------------------------------------- the node

async def pay(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    msg = state["incoming"]
    bid = msg.button_id or ""
    cmd = state.get("command") or ""
    text = state.get("text", "")
    today: date = ctx(config).get("today") or date.today()
    authorize(NODE, "get_own_pay")
    action = bid.removeprefix("pay:") if bid.startswith("pay:") else ""

    # ---- gratuity calculator input (a recognised command like "overtime" is NOT input)
    if user.step == AWAIT_GRATUITY and cmd == "gratuity_input" and msg.kind == "text" and text and not bid:
        result = gratuity_estimate(text, lang)
        if result is None:
            return _out(state, Outgoing(text=t("pay_gratuity_bad", lang), buttons=_back(lang)))
        user.step = "ready"
        return _out(state, result, events=_events(state, ("gratuity_estimate", "ok")))
    user.step = "ready"

    # ---- salary record: paid / part / unpaid (buttons or typed replies to a check-in)
    status = action if action in ("paid", "part", "unpaid") else STATUS_CMDS.get(cmd)
    if status:
        authorize(NODE, "update_own_pay")
        month = pay_month(today)
        repo.set_pay_status(user, month, status)
        saved = t(f"pay_saved_{status}", lang, month=month_label(month, lang))
        ev = _events(state, ("salary_status", status))
        if status == "paid":
            return _out(state, Outgoing(text=f"{saved}\n\n{record_lines(user, lang)}",
                                        buttons=_back(lang, Button(id="pay:watch", title=t("btn_salary_watch", lang)))), events=ev)
        return _out(state, Outgoing(text=saved), late_message(user, lang), events=ev)

    if action in ("on", "off"):
        authorize(NODE, "update_own_pay")
        repo.set_pay_watch(user, action == "on")
        header = t("pay_watch_turned_on" if action == "on" else "pay_watch_turned_off", lang)
        return _out(state, watch_screen(user, today, lang, header=header), events=_events(state, ("salary_watch", action)))

    if action == "watch" or cmd == "salary_watch":
        return _out(state, watch_screen(user, today, lang))
    if action == "late" or cmd == "salary_late":
        return _out(state, late_message(user, lang))
    if action == "how":
        return _out(state, how_message(lang))
    if action == "complaint" or cmd == "complaint":
        return _out(state, complaint_menu(lang))
    if action.startswith("c:") and action[2:] in PROBLEMS:
        authorize(NODE, "draft_complaint")
        return _out(state, *complaint_draft(user, action[2:], lang), events=_events(state, ("complaint_drafted", action[2:])))
    if action == "rights" or cmd == "work_hours":
        return _out(state, rights_message(user, lang))
    if action == "gratuity" or cmd == "gratuity":
        if is_domestic(user):
            return _out(state, Outgoing(text=t("pay_gratuity_domestic", lang), buttons=_back(lang)))
        user.step = AWAIT_GRATUITY
        return _out(state, Outgoing(text=t("pay_gratuity", lang), buttons=_back(lang)))
    if action == "proof":
        return _out(state, proof_message(lang))
    return _out(state, pay_menu(lang))
