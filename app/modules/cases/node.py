"""Dispute case manager (Employment agent) and incident records (Protection agent).

A complaint letter alone isn't the end: Rafiq keeps the case. It opens it,
points to the evidence, explains where to file, records the reference number
the worker gets, reminds them to follow up and records how it ended. The
worker files the complaint themselves; Rafiq never contacts an office.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import S, fmt_date, t
from app.media.pdf import Section, build_pdf
from app.modules.cases import store
from app.security.tool_policy import authorize

NODE = "cases"
OUTCOMES = ("Paid in full", "Partly paid", "Passport returned", "Sorted out", "Sent to Labour Court", "Not resolved",
            "I withdrew", "Repaired or refunded")

LEGAL_CHECKED = "2026-11-24"

STRINGS: dict[str, dict[str, str]] = {
    "case_legal": {"en": (
        "⚖️ *Free legal help*\nRafiq is not a lawyer. This is how to reach one without paying.\n\n"
        "*Start here (any emirate, free)*\n"
        "• *MOHRE 80084*: free advice and labour complaints, including domestic workers (also in the MOHRE app). "
        "MOHRE contacts both sides within 14 days; larger claims go to court.\n"
        "• Bring your *case PDF* from Rafiq: dates, amounts, reference numbers.\n\n"
        "*Free lawyers*\n"
        "• *Dubai Courts 'Shoor'*: one free consultation with a licensed law firm before you file, if you can't afford a lawyer. Call 04 334 7777.\n"
        "• *Dubai CDA Legal Clinic*: free legal consultations for Dubai residents.\n"
        "• *Abu Dhabi Judicial Department*: free legal aid, including a lawyer, for people who can't pay (depends on the case and income).\n"
        "• *Other emirates*: the Ministry of Justice gives free consultation on court documents to people who can't pay.\n"
        "• *Your embassy's labour office* may also help citizens with labour cases.\n\n"
        "More: https://u.ae/en/information-and-services/justice-safety-and-the-law/promoting-the-competency-of-the-judicial-system-in-the-uae/legal-aid-and-guidance\n"
        "_Checked {checked}._")},
    "case_legal_after": {"en": "If you want to take it further, free legal help is available:"},
    "btn_case_legal": {"en": "Free legal help"},
    "menu_cases": {"en": "My cases"},
    "cases_head": {"en": "📂 *My cases*\nI keep track of each complaint: evidence, where to file, the reference number, follow-ups and how it ended."},
    "cases_none": {"en": "You have no cases yet."},
    "btn_new_case": {"en": "➕ New case"},
    "case_pick_kind": {"en": "What is the case about?"},
    "case_k_wages": {"en": "Unpaid or short wages"},
    "case_k_passport": {"en": "Passport kept by employer"},
    "case_k_contract": {"en": "Contract different from offer"},
    "case_k_safety": {"en": "Abuse or unsafe work"},
    "case_k_housing": {"en": "Landlord or housing"},
    "case_k_other": {"en": "Something else"},
    "case_s_open": {"en": "open"},
    "case_s_filed": {"en": "filed, waiting"},
    "case_s_resolved": {"en": "resolved"},
    "case_s_closed": {"en": "closed"},
    "case_full": {"en": "You have {n} open cases, the most I can track. Close one first."},
    "case_view": {"en": "📂 *{kind}*: {status}\nOpened {opened}{ref}\n\n*Next step:* {next}\n\n*Timeline*\n{timeline}"},
    "case_ref": {"en": " · ref {ref}"},
    "case_next_open": {"en": "1) gather evidence, 2) file the complaint yourself ({where}), 3) tap *I filed it* and I'll track it."},
    "case_next_filed": {"en": "wait for MOHRE to contact you. I'll check in with you on {date}. Record the outcome when it ends."},
    "case_next_done": {"en": "nothing. This case is finished. You can download its history."},
    "case_where_work": {"en": "MOHRE app or website, or call 80084; domestic workers can also go to a Tadbeer centre"},
    "case_where_housing": {"en": "write to your landlord first and keep a copy; then the Rental Disputes Centre (dubailand.gov.ae) with your Ejari contract"},
    "case_where_safety": {"en": "police 999; Dubai Police human trafficking and abuse line 800 7283; your embassy"},
    "btn_case_evidence": {"en": "Get evidence"},
    "btn_case_filed": {"en": "I filed it"},
    "btn_case_note": {"en": "Add a note"},
    "btn_case_outcome": {"en": "Record outcome"},
    "btn_case_pdf": {"en": "Download history"},
    "btn_case_delete": {"en": "Delete case"},
    "btn_cases": {"en": "My cases"},
    "case_opened": {"en": "✅ Case opened: *{kind}*."},
    "case_ask_ref": {"en": "Great that you filed it. 👏 Type the *reference number* you were given (or tap Skip)."},
    "case_filed": {"en": "✅ Recorded. I'll check in with you on *{date}* and every 2 weeks after, until it's resolved."},
    "case_ask_note": {"en": "Type your note: what happened, when, who was there. (Up to 300 characters, dated today.)"},
    "case_note_saved": {"en": "✅ Note added to the timeline with today's date."},
    "case_bad_note": {"en": "Please type a short note (up to 300 characters)."},
    "case_pick_outcome": {"en": "How did it end?"},
    "case_ask_recovered": {"en": "How much was paid to you in AED? (just the number, or tap Skip)"},
    "case_closed_msg": {"en": "✅ Outcome recorded. Thank you for telling me: it helps show what works for other workers."},
    "case_confirm_delete": {"en": "Delete this case and its notes for good?"},
    "btn_yes_delete": {"en": "Yes, delete"},
    "case_deleted": {"en": "🗑️ Case deleted."},
    "case_not_found": {"en": "I couldn't find that case."},
    "case_caption": {"en": "📂 Your case pack: Arabic first (for MOHRE, courts and typing centres), then English, with amounts owed and what to bring."},
    "case_followup": {"en": "📂 Any news on your *{kind}* complaint{ref}? Type *my cases* to add an update or record how it ended."},
}
S.update(STRINGS)


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _ev(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


def _b(id_: str, key: str, lang: str | None) -> Button:
    return Button(id=id_, title=t(key, lang))


def _draft(user) -> dict:  # type: ignore[no-untyped-def]
    d = repo.toolkit(user).get("case_draft")
    return d if isinstance(d, dict) else {}


def _set_draft(user, step: str | None, d: dict | None) -> None:  # type: ignore[no-untyped-def]
    repo.update_toolkit(user, case_draft=d or None)
    user.step = step or "ready"


def kind_label(kind: str, lang: str | None) -> str:
    return t(f"case_k_{kind if kind in store.KINDS else 'other'}", lang)


EVIDENCE = {"wages": "task:pack", "contract": "task:contract", "passport": "task:form:passport",
            "safety": "pro:checklist", "housing": "home:rights", "other": "task:forms"}


def case_screen(case, lang: str | None) -> Outgoing:  # type: ignore[no-untyped-def]
    d = store.data(case)
    where = t({"safety": "case_where_safety", "housing": "case_where_housing"}.get(case.kind, "case_where_work"), lang)
    nxt = {"open": t("case_next_open", lang, where=where),
           "filed": t("case_next_filed", lang, date=fmt_date(case.next_check, lang) if case.next_check else "-")}.get(
        case.status, t("case_next_done", lang))
    timeline = "\n".join(f"• {fmt_date(date.fromisoformat(e['d']), lang)}: {e['e']}" for e in (d.get("timeline") or [])[-8:])
    text = t("case_view", lang, kind=kind_label(case.kind, lang), status=t(f"case_s_{case.status}", lang),
             opened=fmt_date(date.fromisoformat(d.get("opened", date.today().isoformat())), lang),
             ref=t("case_ref", lang, ref=d["ref"]) if d.get("ref") else "", next=nxt, timeline=timeline or "-")
    rows: list[ListRow] = []
    if case.status == "open":
        rows += [ListRow(id=EVIDENCE.get(case.kind, "task:forms"), title=t("btn_case_evidence", lang)),
                 ListRow(id=f"case:filed:{case.id}", title=t("btn_case_filed", lang))]
    if case.status in ("open", "filed"):
        rows += [ListRow(id=f"case:note:{case.id}", title=t("btn_case_note", lang)),
                 ListRow(id=f"case:out:{case.id}", title=t("btn_case_outcome", lang))]
    rows += [ListRow(id="case:legal", title=t("btn_case_legal", lang)),
             ListRow(id=f"case:pdf:{case.id}", title=t("btn_case_pdf", lang)),
             ListRow(id=f"case:del:{case.id}", title=t("btn_case_delete", lang)),
             ListRow(id="case:list", title=t("btn_cases", lang))]
    return Outgoing(text=text, menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def legal_help(lang: str | None) -> Outgoing:
    return Outgoing(text=t("case_legal", lang, checked=LEGAL_CHECKED),
                    buttons=[_b("case:new", "btn_new_case", lang), Button(id="help:embassy", title="My embassy"),
                             Button(id="menu:main", title="Menu")])


async def cases_list(session: Any, user, lang: str | None) -> Outgoing:  # type: ignore[no-untyped-def]
    items = await store.list_for(session, user.id)
    rows = [ListRow(id=f"case:view:{c.id}", title=kind_label(c.kind, lang)[:24],
                    description=f"{t(f'case_s_{c.status}', lang)} · {fmt_date(c.created_at.date(), lang)}") for c in items[:8]]
    rows.append(ListRow(id="case:new", title=t("btn_new_case", lang)))
    rows.append(ListRow(id="case:legal", title=t("btn_case_legal", lang)))
    body = t("cases_head", lang) + ("" if items else "\n\n" + t("cases_none", lang))
    return Outgoing(text=body, menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def kinds_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"case:new:{k}", title=t(f"case_k_{k}", lang)[:24]) for k in store.KINDS]
    return Outgoing(text=t("case_pick_kind", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


# Arabic for the case pack: MOHRE, the courts and typing centres work in Arabic.
# Fixed wording only; the worker's own entries are copied as written, never machine-translated.
AR_KIND = {"wages": "أجور غير مدفوعة", "passport": "احتجاز جواز السفر", "contract": "مخالفة عقد العمل",
           "safety": "سلامة العامل وحوادث", "housing": "السكن والإيجار", "other": "أخرى"}
AR_STATUS = {"open": "مفتوحة", "filed": "مقدَّمة وبانتظار الرد", "resolved": "تمت تسويتها", "closed": "مغلقة"}
AR_OUTCOME = {"Paid in full": "تم الدفع بالكامل", "Partly paid": "تم دفع جزء", "Passport returned": "أُعيد جواز السفر",
              "Sorted out": "تمت التسوية", "Sent to Labour Court": "أُحيلت إلى المحكمة العمالية", "Not resolved": "لم تُحل",
              "I withdrew": "سحب العامل الشكوى", "Repaired or refunded": "تم الإصلاح أو الاسترداد"}
AR_BRING = ("رقم تصريح العمل", "رقم جواز السفر", "الرقم الموحد (للعمالة المساعدة)", "رقم المنشأة الخاص بصاحب العمل",
            "هذا السجل، وصور العقد وكشوف الراتب أو التحويلات")
EN_BRING = ("Work permit number", "Passport number", "Unified ID number (domestic workers)", "Employer's establishment number",
            "This record, plus photos of the contract and payslips or transfers")


def _owed_rows(owed: dict | None) -> tuple[list[list[str]], list[list[str]], int]:
    """(Arabic table, English table, total) for a wages case, from the worker's own pay records."""
    if not owed or not owed.get("rows"):
        return [], [], 0
    salary, got = owed.get("salary"), owed.get("received") or {}
    ar = [["الشهر", "الراتب حسب العقد (درهم)", "المبلغ المستلم (درهم)", "المستحق (درهم)"]]
    en = [["Month", "Contract salary (AED)", "Received (AED)", "Owed (AED)"]]
    for month, amt in owed["rows"]:
        g = got.get(month)
        cells = [month, f"{salary:,}" if salary else "-", f"{g:,}" if g is not None else ("0" if amt == salary else "-"),
                 f"{amt:,}" if amt else "?"]
        ar.append(cells)
        en.append(cells)
    return ar, en, int(owed.get("total") or 0)


def case_pdf(case, name: str, lang: str | None, owed: dict | None = None) -> bytes:  # type: ignore[no-untyped-def]
    """Bilingual case pack: Arabic first (for MOHRE, courts, typing centres), then English."""
    d = store.data(case)
    ar_owed, en_owed, total = _owed_rows(owed if case.kind == "wages" else None)
    timeline_rows = [[e["d"], e["e"]] for e in d.get("timeline") or []]

    ar_summary = [["البند", "التفاصيل"], ["العامل", name], ["نوع القضية", AR_KIND.get(case.kind, AR_KIND["other"])],
                  ["الحالة", AR_STATUS.get(case.status, case.status)], ["تاريخ الفتح", d.get("opened", "-")],
                  ["تاريخ التقديم", d.get("filed", "-")], ["الرقم المرجعي", d.get("ref", "-")],
                  ["النتيجة", AR_OUTCOME.get(d.get("outcome", ""), d.get("outcome") or "-")]]
    if d.get("recovered"):
        ar_summary.append(["المبلغ المسترد", f"{d['recovered']:,} درهم"])
    if d.get("signs"):
        ar_summary.append(["علامات التحذير (بالإنجليزية)", ", ".join(d["signs"])])
    ar: list[Section] = [
        Section(f"سجل قضية: {AR_KIND.get(case.kind, AR_KIND['other'])}", [
            "سجل شخصي يحتفظ به العامل بمساعدة «رفيق». ليس وثيقة رسمية.",
            "الصيغة العربية ثابتة، أما ما كتبه العامل فمنقول كما هو دون ترجمة. يُنصح بمراجعته لدى مركز خدمة معتمد قبل التقديم."],
            rtl=True, big=True),
        Section("الملخص", table=ar_summary, rtl=True),
    ]
    if ar_owed:
        ar.append(Section("المبالغ المستحقة", [f"إجمالي المستحق المعروف: {total:,} درهم (حسب سجلات العامل)."],
                          table=ar_owed, rtl=True))
    if timeline_rows:
        ar.append(Section("التسلسل الزمني (بكلمات العامل)", table=[["التاريخ", "ما حدث"], *timeline_rows], rtl=True))
    ar.append(Section("ما يجب إحضاره إلى وزارة الموارد البشرية والتوطين",
                      [*(f"• {x}" for x in AR_BRING), "مركز الاستشارات والمطالبات العمالية: 80084 (مجاني)."], rtl=True))

    summary = [["Item", "Details"], ["Worker", name], ["Case", kind_label(case.kind, lang)],
               ["Status", t(f"case_s_{case.status}", lang)], ["Opened", d.get("opened", "-")],
               ["Filed", d.get("filed", "-")], ["Reference", d.get("ref", "-")], ["Outcome", d.get("outcome", "-")]]
    if d.get("recovered"):
        summary.append(["Recovered", f"AED {d['recovered']:,}"])
    if d.get("signs"):
        summary.append(["Warning signs noted", ", ".join(d["signs"])])
    en: list[Section] = [Section(f"Case record: {kind_label(case.kind, lang)}", ["English version. Entries are the worker's own words."],
                                 page_break_before=True, big=True),
                         Section("Summary", table=summary)]
    if en_owed:
        en.append(Section("Amounts owed", [f"Known total owed: AED {total:,} (from the worker's own records)."], table=en_owed))
    en.append(Section("Timeline", table=[["Date", "What happened"], *timeline_rows]))
    en.append(Section("Bring to MOHRE", [*(f"- {x}" for x in EN_BRING), "Labour Claims and Advisory Centre: 80084 (free)."]))
    return build_pdf("Case record (Arabic / English)", "Kept by the worker with Rafiq. Arabic version first, English after.",
                     [*ar, *en], "Made with Rafiq. A personal record, not an official document.")


def owed_for(user) -> dict:  # type: ignore[no-untyped-def]
    from app.modules.pay import amounts as am

    rows, total = am.gaps(user)
    return {"rows": rows, "total": total, "salary": am.contract_salary(user), "received": am.received(user)}


async def open_case(state: AgentState, config: RunnableConfig, kind: str, first_event: str,
                    actor: str = NODE, extra: dict[str, Any] | None = None) -> tuple[Any, list[Outgoing]]:
    """Shared by the Employment (cases) and Protection agents."""
    user, lang = state["user"], state["user"].language
    session = ctx(config)["db"]
    authorize(actor, "update_own_cases")
    today = ctx(config).get("today") or date.today()
    if existing := await store.find_open(session, user.id, kind):
        if first_event:
            store.add_event(existing, today, first_event)
        return existing, [case_screen(existing, lang)]
    if await store.open_count(session, user.id) >= store.MAX_OPEN:
        return None, [Outgoing(text=t("case_full", lang, n=store.MAX_OPEN), buttons=[_b("case:list", "btn_cases", lang)])]
    case = await store.create(session, user.id, kind, today, first_event, extra)
    return case, [Outgoing(text=t("case_opened", lang, kind=kind_label(kind, lang))), case_screen(case, lang)]


async def cases(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user, msg = state["user"], state["incoming"]
    lang = user.language
    session = ctx(config)["db"]
    today: date = ctx(config).get("today") or date.today()
    bid = msg.button_id or ""
    text = (state.get("text") or "").strip()
    authorize(NODE, "get_own_cases")
    action = bid.removeprefix("case:") if bid.startswith("case:") else ""

    # ---- answers to our questions
    if not bid and user.step.startswith("case:"):
        d = _draft(user)
        case = await store.get(session, user.id, d.get("id", ""))
        step = user.step
        if case is None:
            _set_draft(user, None, None)
            return _out(state, await cases_list(session, user, lang))
        authorize(NODE, "update_own_cases")
        if step == "case:ref":
            ref = re.sub(r"[^\w\-/ ]", "", text)[:40].strip() or None
            store.mark_filed(case, today, ref)
            _set_draft(user, None, None)
            if ref:   # the user's own reference: the output guard must not mask it
                refs = [r for r in (repo.toolkit(user).get("case_refs") or []) if r != ref][-9:]
                repo.update_toolkit(user, case_refs=[*refs, ref])
            return _out(state, Outgoing(text=t("case_filed", lang, date=fmt_date(case.next_check, lang))), case_screen(case, lang),
                        events=_ev(state, ("case_filed", case.kind)))
        if step == "case:note":
            if not (2 <= len(text) <= 300):
                return _out(state, Outgoing(text=t("case_bad_note", lang)))
            store.add_event(case, today, text)
            _set_draft(user, None, None)
            return _out(state, Outgoing(text=t("case_note_saved", lang)), case_screen(case, lang),
                        events=_ev(state, ("case_note", case.kind)))
        if step == "case:recovered":
            nums = re.findall(r"\d[\d,]*", text)
            amount = int(nums[0].replace(",", "")) if len(nums) == 1 else None
            store.mark_outcome(case, today, d.get("outcome", "Paid in full"), amount if amount and amount < 10_000_000 else None)
            _set_draft(user, None, None)
            return _out(state, Outgoing(text=t("case_closed_msg", lang)), case_screen(case, lang),
                        events=_ev(state, ("case_resolved", d.get("outcome", ""))))

    if action == "skip" and user.step in ("case:ref", "case:recovered"):
        d = _draft(user)
        case = await store.get(session, user.id, d.get("id", ""))
        if case:
            authorize(NODE, "update_own_cases")
            if user.step == "case:ref":
                store.mark_filed(case, today, None)
                _set_draft(user, None, None)
                return _out(state, Outgoing(text=t("case_filed", lang, date=fmt_date(case.next_check, lang))),
                            case_screen(case, lang), events=_ev(state, ("case_filed", case.kind)))
            store.mark_outcome(case, today, d.get("outcome", "Paid in full"))
            _set_draft(user, None, None)
            return _out(state, Outgoing(text=t("case_closed_msg", lang)), case_screen(case, lang),
                        events=_ev(state, ("case_resolved", d.get("outcome", ""))))
    user.step = "ready"

    if action.startswith("new:") and action[4:] in store.KINDS:
        kind = action[4:]
        case, msgs = await open_case(state, config, kind, "Case opened")
        return _out(state, *msgs, events=_ev(state, ("case_opened", kind)) if case else state.get("events", []))
    if action == "new":
        return _out(state, kinds_menu(lang))
    if action == "legal" or state.get("command") == "legal_aid":
        return _out(state, legal_help(lang), events=_ev(state, ("legal_help", "")))

    m = re.fullmatch(r"(view|filed|note|out|pdf|del|delyes):([0-9a-f\-]{36})", action)
    o = re.fullmatch(r"o:(\d):([0-9a-f\-]{36})", action)
    case_id = (m.group(2) if m else o.group(2) if o else "")
    case = await store.get(session, user.id, case_id) if case_id else None
    if case_id and case is None:
        return _out(state, Outgoing(text=t("case_not_found", lang)), await cases_list(session, user, lang))
    if m and case:
        verb = m.group(1)
        if verb == "view":
            return _out(state, case_screen(case, lang))
        if verb == "filed" and case.status == "open":
            _set_draft(user, "case:ref", {"id": case.id})
            return _out(state, Outgoing(text=t("case_ask_ref", lang), buttons=[_b("case:skip", "btn_skip", lang)]))
        if verb == "note" and case.status in ("open", "filed"):
            _set_draft(user, "case:note", {"id": case.id})
            return _out(state, Outgoing(text=t("case_ask_note", lang)))
        if verb == "out" and case.status in ("open", "filed"):
            rows = [ListRow(id=f"case:o:{i}:{case.id}", title=name) for i, name in enumerate(OUTCOMES)]
            return _out(state, Outgoing(text=t("case_pick_outcome", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows)))
        if verb == "pdf":
            authorize(NODE, "build_document")
            pdf = case_pdf(case, repo.get_display_name(user) or "Worker", lang, owed_for(user) if case.kind == "wages" else None)
            return _out(state, Outgoing(text=t("case_caption", lang), file=pdf, filename=f"case-{case.kind}.pdf",
                                        file_mime="application/pdf"), events=_ev(state, ("case_exported", case.kind)))
        if verb == "del":
            return _out(state, Outgoing(text=t("case_confirm_delete", lang),
                                        buttons=[_b(f"case:delyes:{case.id}", "btn_yes_delete", lang), _b(f"case:view:{case.id}", "btn_cancel", lang)]))
        if verb == "delyes":
            authorize(NODE, "update_own_cases")
            await session.delete(case)
            return _out(state, Outgoing(text=t("case_deleted", lang)), await cases_list(session, user, lang))
        return _out(state, case_screen(case, lang))
    if o and case and case.status in ("open", "filed") and int(o.group(1)) < len(OUTCOMES):
        outcome = OUTCOMES[int(o.group(1))]
        if outcome in ("Paid in full", "Partly paid"):
            _set_draft(user, "case:recovered", {"id": case.id, "outcome": outcome})
            return _out(state, Outgoing(text=t("case_ask_recovered", lang), buttons=[_b("case:skip", "btn_skip", lang)]))
        authorize(NODE, "update_own_cases")
        store.mark_outcome(case, today, outcome)
        extra = [Outgoing(text=t("case_legal_after", lang), buttons=[_b("case:legal", "btn_case_legal", lang)])] \
            if outcome in ("Sent to Labour Court", "Not resolved") else []
        return _out(state, Outgoing(text=t("case_closed_msg", lang)), case_screen(case, lang), *extra,
                    events=_ev(state, ("case_resolved", outcome)))
    return _out(state, await cases_list(session, user, lang))


# ---------------------------------------------------------------- follow-up reminders (worker)

async def send_case_follow_ups(session: Any, send: Any, today: date) -> int:
    from datetime import timedelta

    from app.db.models import User
    from app.modules.stay_legal.visa import Reminder
    from app.security.crypto import decrypt

    sent = 0
    for case in await store.due_follow_ups(session, today):
        user = await session.get(User, case.user_id)
        if user is None or user.consent_status != "granted" or user.notifications_paused:
            continue
        to = decrypt(user.address_enc)
        if not to:
            continue
        d = store.data(case)
        lang = user.language
        r = Reminder(user_id=user.id, channel=user.channel, to=to, days=0, kind="case",
                     text=t("case_followup", lang, kind=kind_label(case.kind, lang),
                            ref=f" (ref {d['ref']})" if d.get("ref") else ""),
                     template_params=[kind_label(case.kind, lang), d.get("ref") or "-"])
        try:
            if await send(r):
                sent += 1
        except Exception:
            continue
        case.next_check = today + timedelta(days=store.FOLLOW_UP_EVERY_DAYS)
    await session.commit()
    return sent
