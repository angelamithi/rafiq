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
from app.modules.pay import amounts as am
from app.modules.pay import overtime as ot
from app.modules.pay import wagecheck as wc
from app.modules.pay import content  # noqa: F401  (registers the text)
from app.modules.pay.content import GRATUITY_MAX_SALARY, GRATUITY_MAX_YEARS, GRATUITY_MIN_SALARY, MOHRE
from app.security.tool_policy import authorize

NODE = "pay"
AWAIT_GRATUITY = "pay:await_gratuity"
AWAIT_OT = "pay:await_ot"
AWAIT_WC = "pay:await_wc"
MENU = ("wc", "watch", "gaps", "slip", "late", "complaint", "rights", "ot", "gratuity", "proof")
AWAIT_SALARY, AWAIT_AMOUNT, AWAIT_SLIP = "pay:await_salary", "pay:await_amount", "pay:await_payslip"
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
        if (total := am.gaps(user)[1]) > 0:
            details = details.replace("about AED [amount]", f"about AED {total:,} (from my own records)")
    body = t("pay_draft_body", lang, subject=t(f"pay_d_{problem}_subject", lang), name=name, details=details,
             request=t(f"pay_d_{problem}_request", lang))
    return [Outgoing(text=t("pay_draft_head", lang)), Outgoing(text=body, keep_english=True),
            Outgoing(text=t("pay_draft_tail", lang), buttons=_back(lang, Button(id="pay:how", title=t("btn_how_to_complain", lang))))]


def rights_message(user, lang: str | None) -> Outgoing:  # type: ignore[no-untyped-def]
    key = "pay_rights_domestic" if is_domestic(user) else "pay_rights_private"
    extra = () if is_domestic(user) else (Button(id="pay:ot", title=t("pay_m_ot", lang)),)
    return Outgoing(text=_with_footer(t(key, lang), lang), buttons=_back(lang, *extra))


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


# ---------------------------------------------------------------- amounts (promised vs received)

def _draft(user) -> dict:  # type: ignore[no-untyped-def]
    d = repo.toolkit(user).get("pay_draft")
    return d if isinstance(d, dict) else {}


def _set_draft(user, d: dict | None) -> None:  # type: ignore[no-untyped-def]
    repo.update_toolkit(user, pay_draft=d or None)


def _ask_got(user, month: str, status: str, lang: str | None) -> Outgoing:  # type: ignore[no-untyped-def]
    salary = am.contract_salary(user)
    _set_draft(user, {"month": month, "status": status})
    if status == "paid":
        user.step = "ready"
        return Outgoing(text=t("pay_ask_got_paid", lang, salary=f"{salary:,}", month=month_label(month, lang)),
                        buttons=[Button(id="pay:full", title=t("btn_full_amount", lang)),
                                 Button(id="pay:less", title=t("btn_less", lang))])
    user.step = AWAIT_AMOUNT
    return Outgoing(text=t("pay_ask_got_part", lang, month=month_label(month, lang)))


def _after_got(state: AgentState, user, month: str, got: int, lang: str | None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    authorize(NODE, "update_own_pay")
    am.record_received(user, month, got)
    user.step = "ready"
    salary = am.contract_salary(user) or 0
    saved = t("pay_got_saved", lang, got=f"{got:,}", month=month_label(month, lang))
    ev = _events(state, ("salary_amount", "short" if got < salary else "full"))
    if got >= salary:
        _set_draft(user, None)
        return _out(state, Outgoing(text=f"{saved}\n\n{record_lines(user, lang)}", buttons=_back(lang)), events=ev)
    _set_draft(user, {"month": month, "status": "gap"})
    return _out(state, Outgoing(text=saved + "\n\n" + t("pay_gap_found", lang, gap=f"{salary - got:,}", salary=f"{salary:,}"),
                                buttons=[Button(id="pay:gap_agreed", title=t("btn_gap_agreed", lang)),
                                         Button(id="pay:gap_not", title=t("btn_gap_not", lang)),
                                         Button(id="pay:gap_unsure", title=t("btn_gap_unsure", lang))]),
                events=_events(state, ("salary_gap_found", "")) + ev[len(state.get("events", [])):])


def owed_message(user, lang: str | None) -> list[Outgoing]:  # type: ignore[no-untyped-def]
    rows, total = am.gaps(user)
    months = ", ".join(am.label(m) for m, _ in rows) or "-"
    msgs = [Outgoing(text=t("pay_gap_owed", lang, total=f"{total:,}", months=months),
                     buttons=[Button(id="task:pack", title=t("btn_build_pack", lang)),
                              Button(id="case:new:wages", title=t("btn_open_case", lang)),
                              Button(id="pay:late", title=t("pay_m_late", lang)[:20])])]
    if (n := am.shortfall_streak(user)) >= 2:
        msgs.insert(0, Outgoing(text=t("pay_pattern", lang, n=n)))
    return msgs


async def _payslip(state: AgentState, config: RunnableConfig, today: date) -> dict[str, Any]:
    user, msg, lang = state["user"], state["incoming"], state["user"].language
    text = state.get("text", "")
    if msg.kind == "media" and msg.media_type in ("image", "document"):
        from app.media.flow import read_media_from_message

        res, _ = await read_media_from_message(state, config)
        text = res.text or ""
    elif msg.kind != "text" or len(text) < 15:
        return _out(state, Outgoing(text=t("pay_slip_need_file", lang), buttons=_back(lang)))
    slip = am.read_payslip(text, today)
    user.step = "ready"
    if not slip.found():
        return _out(state, Outgoing(text=t("pay_slip_unreadable", lang), buttons=_back(lang)))
    lines = []
    for key, val in (("net", slip.net), ("gross", slip.gross), ("basic", slip.basic)):
        if val is not None:
            lines.append(t("pay_slip_line", lang, label=t(f"pay_slip_{key}", lang), amount=f"{val:,}"))
    lines += [t("pay_slip_line", lang, label=lbl, amount=f"{amt:,}") for lbl, amt in slip.deductions]
    month = slip.month or pay_month(today)
    body = [t("pay_slip_read", lang, month=f" ({month_label(month, lang)})" if slip.month else "", lines="\n".join(lines))]
    salary = am.contract_salary(user)
    if salary and slip.net is not None:
        body.append(t("pay_slip_vs", lang, salary=f"{salary:,}", gap=f"{salary - slip.net:,}") if slip.net < salary
                    else t("pay_slip_vs_ok", lang, salary=f"{salary:,}"))
    body.append(t("pay_slip_note", lang))
    buttons = _back(lang)
    if slip.net is not None:
        _set_draft(user, {"month": month, "status": "slip", "got": slip.net})
        body.append(t("pay_slip_save", lang, net=f"{slip.net:,}", month=month_label(month, lang)))
        buttons = [Button(id="pay:slip_save", title=t("btn_save", lang)), *_back(lang)][:3]
    return _out(state, Outgoing(text="\n\n".join(body), buttons=buttons), events=_events(state, ("payslip_read", "ok")))


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

    # ---- salary amounts and payslips (answers to a question we asked)
    if cmd == "gratuity_input" and not bid and user.step in (AWAIT_SALARY, AWAIT_AMOUNT, AWAIT_SLIP):
        if user.step == AWAIT_SLIP:
            return await _payslip(state, config, today)
        v = am.parse_amount(text) if msg.kind == "text" else None
        if user.step == AWAIT_SALARY:
            if v is None or not (am.MIN_SALARY <= v <= am.MAX_SALARY):
                return _out(state, Outgoing(text=t("pay_bad_amount", lang)))
            authorize(NODE, "update_own_pay")
            repo.update_toolkit(user, salary=v)
            d = _draft(user)
            return _out(state, _ask_got(user, d.get("month") or pay_month(today), d.get("status") or "paid", lang))
        if v is None:
            return _out(state, Outgoing(text=t("pay_bad_amount", lang)))
        return _after_got(state, user, _draft(user).get("month") or pay_month(today), v, lang)

    # ---- overtime calculator input
    if user.step == AWAIT_OT and cmd == "gratuity_input" and msg.kind == "text" and text and not bid:
        o = ot.parse(text)
        if o is None:
            return _out(state, Outgoing(text=t("ot_bad", lang), buttons=_back(lang)))
        user.step = "ready"
        return _out(state, Outgoing(text=ot.result_text(o, t, lang),
                                    buttons=[Button(id="pay:c:hours", title=t("btn_ot_complaint", lang)),
                                             Button(id="pay:ot", title=t("btn_ot_again", lang)),
                                             Button(id="menu:pay", title=t("btn_pay_menu", lang))]),
                    events=_events(state, ("overtime_estimate", "over_limit" if o.over_limit else "ok")))
    # ---- gratuity calculator input (a recognised command like "overtime" is NOT input)
    if user.step == AWAIT_GRATUITY and cmd == "gratuity_input" and msg.kind == "text" and text and not bid:
        result = gratuity_estimate(text, lang)
        if result is None:
            return _out(state, Outgoing(text=t("pay_gratuity_bad", lang), buttons=_back(lang)))
        user.step = "ready"
        return _out(state, result, events=_events(state, ("gratuity_estimate", "ok")))
    if user.step == AWAIT_WC and cmd == "gratuity_input" and msg.kind == "text" and text and not bid:
        cmd = "wage_check"                                        # her two amounts for the wage check
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
            if salary := am.contract_salary(user):
                am.record_received(user, month, salary)
            return _out(state, Outgoing(text=f"{saved}\n\n{record_lines(user, lang)}",
                                        buttons=_back(lang, Button(id="pay:watch", title=t("btn_salary_watch", lang)))), events=ev)
        if status == "part":
            if am.contract_salary(user) is None:      # ask the contract salary once, then the amount
                _set_draft(user, {"month": month, "status": status})
                user.step = AWAIT_SALARY
                return _out(state, Outgoing(text=saved), late_message(user, lang),
                            Outgoing(text=t("pay_ask_contract", lang)), events=ev)
            return _out(state, Outgoing(text=saved), late_message(user, lang), _ask_got(user, month, status, lang), events=ev)
        extra = owed_message(user, lang) if am.contract_salary(user) else []
        return _out(state, Outgoing(text=saved), late_message(user, lang), *extra, events=ev)

    # ---- Wage check: the flagship workflow (app/modules/pay/wagecheck.py)
    if action == "wc":
        user.step = AWAIT_WC
        return _out(state, Outgoing(text=t("wc_need_both", lang), buttons=_back(lang)))
    if cmd == "wage_check" and msg.kind == "text" and not bid:
        authorize(NODE, "update_own_pay")
        msgs, draft = wc.start(user, text, today, lang, month_label, is_domestic(user))
        if draft is None and "Send both amounts" in msgs[0].text:
            user.step = AWAIT_WC                                  # missing an amount: wait for both
        repo.update_toolkit(user, wage_check=draft)
        return _out(state, *msgs, events=_events(state, ("wage_check", "shortfall" if draft else "no_shortfall_or_missing")))
    if action.startswith("wc_ded:") and isinstance(repo.toolkit(user).get("wage_check"), dict):
        authorize(NODE, "update_own_pay")
        draft = repo.toolkit(user)["wage_check"]
        answer = action.split(":", 1)[1]
        repo.update_toolkit(user, wage_check=None)
        return _out(state, *wc.after_deduction(user, draft, answer, lang),
                    events=_events(state, ("wage_check_deduction", answer)))
    if action in ("wc_pack", "wc_draft"):
        from app.modules.cases.node import case_pdf, open_case, owed_for

        _, total = am.gaps(user)
        first = f"Wage check: potential shortfall AED {total:,} so far (from my own pay records)"
        case, opened = await open_case(state, config, "wages", first, actor=NODE)
        if case is None:
            return _out(state, *opened)
        if action == "wc_pack":
            authorize(NODE, "build_document")
            pdf = case_pdf(case, repo.get_display_name(user) or "Worker", lang, owed_for(user))
            return _out(state, Outgoing(text=t("wc_pack_done", lang), file=pdf, filename="evidence-pack-wages.pdf",
                                        file_mime="application/pdf",
                                        buttons=[Button(id="pay:wc_draft", title=t("btn_wc_draft", lang)),
                                                 Button(id="task:vault", title="My documents")]),
                        events=_events(state, ("evidence_pack_built", "wages")))
        authorize(NODE, "draft_complaint")
        drafts = complaint_draft(user, "unpaid", lang)
        return _out(state, Outgoing(text=t("wc_draft_head", lang)), drafts[1],
                    Outgoing(text=t("wc_draft_tail", lang),
                             buttons=[Button(id=f"case:filed:{case.id}", title=t("btn_wc_filed", lang)),
                                      Button(id="case:legal", title="Free legal help"),
                                      Button(id="pay:wc_pack", title=t("btn_wc_pack", lang))]),
                    events=_events(state, ("complaint_drafted", "wage_check")))
    if action == "full":
        d, salary = _draft(user), am.contract_salary(user)
        if salary:
            return _after_got(state, user, d.get("month") or pay_month(today), salary, lang)
    if action == "less":
        user.step = AWAIT_AMOUNT
        return _out(state, Outgoing(text=t("pay_ask_got_part", lang, month=month_label(_draft(user).get("month") or pay_month(today), lang))))
    if action == "slip_save" and _draft(user).get("status") == "slip":
        d = _draft(user)
        return _after_got(state, user, d["month"], int(d["got"]), lang)
    if action in ("gap_agreed", "gap_not", "gap_unsure") and _draft(user).get("month"):
        authorize(NODE, "update_own_pay")
        month = _draft(user)["month"]
        _set_draft(user, None)
        am.mark_agreed(user, month, action == "gap_agreed")
        if action == "gap_agreed":
            return _out(state, Outgoing(text=t("pay_gap_agreed", lang), buttons=_back(lang)),
                        events=_events(state, ("salary_gap_agreed", "")))
        return _out(state, *owed_message(user, lang), events=_events(state, ("salary_gap_owed", "")))
    if action == "gaps" or cmd == "salary_gaps":
        rows = am.gaps(user)[0]
        buttons = ([Button(id="task:pack", title=t("btn_build_pack", lang)),
                    Button(id="case:new:wages", title=t("btn_open_case", lang)), Button(id="menu:pay", title=t("btn_pay_menu", lang))]
                   if rows else _back(lang, Button(id="pay:watch", title=t("btn_salary_watch", lang))))
        return _out(state, Outgoing(text=am.gaps_message(user, lang), buttons=buttons))
    if action == "slip" or cmd == "payslip":
        user.step = AWAIT_SLIP
        return _out(state, Outgoing(text=t("pay_slip_ask", lang), buttons=_back(lang)))

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
    if action == "ot" or cmd == "overtime_calc":
        if is_domestic(user):
            return _out(state, Outgoing(text=t("ot_domestic", lang), buttons=_back(lang)))
        user.step = AWAIT_OT
        return _out(state, Outgoing(text=t("ot_ask", lang), buttons=_back(lang)))
    if action == "gratuity" or cmd == "gratuity":
        if is_domestic(user):
            return _out(state, Outgoing(text=t("pay_gratuity_domestic", lang), buttons=_back(lang)))
        user.step = AWAIT_GRATUITY
        return _out(state, Outgoing(text=t("pay_gratuity", lang), buttons=_back(lang)))
    if action == "proof":
        return _out(state, proof_message(lang))
    return _out(state, pay_menu(lang))
