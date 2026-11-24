"""Protection agent: exploitation early warning and incident records.

One sign on its own ("my boss is late with pay") is handled by the module it
belongs to. Two or more signs together ("not paid for two months AND can't
leave until I repay the agency fee"), or one severe sign, are a pattern the
ILO lists as indicators of forced labour. Then Rafiq:

1. names the signs it heard (never a legal ruling),
2. asks first whether the worker is in danger right now,
3. gives confidential help options,
4. offers a dated incident record, an evidence checklist and a complaint draft,
5. offers to alert the trusted contact (only with the worker's confirmation).

Scoring is by rules on the worker's own words: no AI decides whether someone
is at risk, and nothing is stored unless the worker asks for a record.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import S, t
from app.security.tool_policy import authorize

NODE = "protection"

# key -> (plain-English label, pattern). Patterns run on lower-cased text.
INDICATORS: dict[str, tuple[str, str]] = {
    "unpaid": ("Wages not paid", r"(not|haven'?t|hasn'?t|didn'?t|never)\s+(been\s+)?(paid|pay|give[ns]?\s+me\s+(my\s+)?(salary|money|pay))"
               r"|no\s+(salary|pay)\b|without\s+(pay|salary)|months?\s+(without|no)\s+(pay|salary)"),
    "debt": ("Made to repay a recruitment fee or debt", r"(repay|pay\s*back|return)\s+(the\s+|my\s+|his\s+)?(recruitment|agency|agent|visa|ticket)"
             r"|(can'?t|cannot|not\s+allowed\s+to)\s+(leave|go|quit|resign)\s+(until|unless|before)\s+(i\s+)?(pay|repay|return)"
             r"|\bowe\s+(the\s+)?(agency|agent|boss|employer|sponsor|madam)"),
    "passport": ("Passport kept by someone else", r"(took|taken|take|keeps?|kept|holding|holds|confiscat\w*)\s+(away\s+)?(my\s+)?passport"
                 r"|passport\s+(is\s+)?(with\s+(my\s+)?(boss|employer|madam|sponsor|agent)|taken|kept)"),
    "confined": ("Not allowed to leave or locked in", r"lock(ed|s)?\s+(me\s+)?(in|inside|up)\b|not\s+allowed\s+(to\s+)?(go\s+out|leave|outside)"
                 r"|can'?t\s+(go\s+out|leave\s+the\s+(house|room|villa|camp|building))|won'?t\s+let\s+me\s+(go\s+out|leave)"),
    "violence": ("Physical or sexual abuse", r"\b(beat|beats|beaten|beating|hit|hits|hitting|slapped|kicked|punched|raped?|molest\w*)\s+(me|her|us)\b"
                 r"|\btouch(ed|es|ing)\s+me\b|sexual(ly)?\s+(abuse|harass)"),
    "threats": ("Threats", r"threat(en|ens|ened|ening)?\s+(me|to)|(will|going\s+to|gonna)\s+(kill|hurt|deport|jail|report)\s+me"
                r"|(file|open)\s+(an?\s+)?absconding"),
    "no_rest": ("No rest day or extreme hours", r"no\s+(day\s+off|rest\s+day|off\s+day|days\s+off)|(1[5-9]|2[0-4])\s+hours?\s+(a|per|every|each)\s+day"
                r"|work\s+(every\s+single\s+day|7\s+days\s+a\s+week)"),
    "phone": ("Phone taken away", r"(took|taken|take|keeps?|kept|confiscat\w*)\s+(away\s+)?(my\s+)?(phone|mobile)"),
    "food": ("Not given enough food", r"no\s+food|not\s+(given|getting)\s+(enough\s+)?food|starv\w+|(don'?t|doesn'?t)\s+(give|feed)\s+(me|us)\s+(food|enough)"),
    "forced": ("Forced to work or not allowed to quit", r"forc(ed|ing|es?)\s+(me\s+)?(to\s+)?work|won'?t\s+let\s+me\s+(quit|resign|leave\s+(the\s+)?job)"
               r"|can'?t\s+(quit|resign)\b"),
    "deception": ("Job is different from what was promised", r"(different|not\s+the\s+same)\s+(job|work)|not\s+the\s+(job|work)\s+(i\s+was\s+)?promised"
                  r"|promised\s+(me\s+)?(a\s+)?\w+(\s+\w+)?\s+(job\s+)?but"),
}
SEVERE = {"violence", "confined", "threats"}
_COMPILED = {k: re.compile(p, re.I) for k, (_, p) in INDICATORS.items()}

STRINGS: dict[str, dict[str, str]] = {
    "pro_warning": {"en": (
        "🛡️ I'm taking this seriously. What you describe has *{n} warning sign{s}* that UAE law and the ILO treat as "
        "possible forced labour or trafficking:\n{signs}\n\n"
        "This isn't a legal ruling, but it is a reason to get help. *Are you safe right now?*"
    )},
    "btn_pro_danger": {"en": "I'm in danger now"},
    "btn_pro_safe": {"en": "Safe for now"},
    "btn_pro_unsure": {"en": "Not sure"},
    "pro_danger": {"en": (
        "🚨 *Call 999 now* (police). If you can't talk, call and leave the line open, or ask someone near you to call.\n\n"
        "• *800 7283* (800 SAVE): human trafficking hotline, every day, many languages.\n"
        "• *800 111*: Dubai Foundation for Women and Children, call or WhatsApp.\n"
        "• Your embassy can help you get to safety and get papers.\n\n"
        "{sos}"
    )},
    "pro_danger_sos": {"en": "Tap *Send SOS* and I'll alert your trusted contact with your location."},
    "pro_danger_no_sos": {"en": "When you're safe, set up a trusted contact so one tap alerts someone you trust."},
    "pro_options": {"en": (
        "OK. Here's what I can do for you now. You decide; I never contact your employer or anyone else.\n\n"
        "• *Record what happened*: a dated, private record you can show MOHRE, police or your embassy.\n"
        "• *Evidence checklist*: what to keep and how to keep it safe.\n"
        "• *Who can help*: confidential, free services."
    )},
    "pro_m_record": {"en": "Record what happened"},
    "pro_m_record_d": {"en": "Dated, private, can be exported as a PDF"},
    "pro_m_checklist": {"en": "Evidence checklist"},
    "pro_m_checklist_d": {"en": "What to keep and how to keep it safe"},
    "pro_m_help": {"en": "Who can help"},
    "pro_m_help_d": {"en": "Confidential and free services"},
    "pro_m_complaint": {"en": "Complaint draft"},
    "pro_m_complaint_d": {"en": "A letter you can send yourself"},
    "pro_m_sos": {"en": "Alert trusted contact"},
    "pro_m_sos_d": {"en": "Only after you confirm"},
    "pro_checklist": {"en": (
        "📋 *Evidence to keep* (only if it's safe to do so)\n"
        "• Photos of your contract, offer, visa and passport. Save them in *My documents*: they're encrypted.\n"
        "• Bank statements or payslips showing what you were (not) paid.\n"
        "• Screenshots of messages with threats, promises or instructions. Note the date.\n"
        "• Names of people who saw what happened, and where you were.\n"
        "• A dated note of each incident. I can keep this for you: tap *Record what happened*.\n\n"
        "Don't argue or show the evidence to your employer. Delete our chat if someone checks your phone; your record stays safe with me."
    )},
    "pro_help": {"en": (
        "🤝 *Confidential, free help*\n"
        "• *800 7283* (800 SAVE): human trafficking hotline, every day, many languages.\n"
        "• *800 111*: Dubai Foundation for Women and Children (shelter, call or WhatsApp).\n"
        "• *80084*: MOHRE, for unpaid wages, passport and contract problems, including domestic workers.\n"
        "• *999*: police, in an emergency.\n"
        "• Your embassy's labour attaché or welfare officer.\n\n"
        "You can report even if your visa has problems. Reporting first also protects you from a false absconding case."
    )},
    "pro_record_started": {"en": "✅ Started a private incident record with today's date and the signs you described."},
}
S.update(STRINGS)


def assess(text: str) -> list[str]:
    """Indicators found in the worker's own words (empty if none)."""
    low = (text or "").lower()
    return [k for k, rx in _COMPILED.items() if rx.search(low)]


def needs_protection(text: str) -> bool:
    """Two or more signs together, or one severe sign alongside any other.
    (A single sign is handled by its own module; single severe phrases still
    reach the Help & emergency screen through its own safety net.)"""
    found = assess(text)
    return len(found) >= 2


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _ev(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


def options_menu(lang: str | None, has_contact: bool) -> Outgoing:
    keys = ["record", "checklist", "help", "complaint"] + (["sos"] if has_contact else [])
    ids = {"record": "pro:record", "checklist": "pro:checklist", "help": "pro:help", "complaint": "pay:complaint",
           "sos": "task:sos_send"}
    rows = [ListRow(id=ids[k], title=t(f"pro_m_{k}", lang), description=t(f"pro_m_{k}_d", lang)) for k in keys]
    rows.append(ListRow(id="menu:main", title=t("btn_menu", lang)))
    return Outgoing(text=t("pro_options", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


async def protection(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user, msg = state["user"], state["incoming"]
    lang = user.language
    bid = msg.button_id or ""
    action = bid.removeprefix("pro:") if bid.startswith("pro:") else ""
    authorize(NODE, "assess_risk")
    has_contact = bool(repo.toolkit(user).get("contact_address"))

    if not action:
        signs = assess(state.get("text", ""))
        # Remember only the kinds of sign (not the words) for 1 hour, so "Record what happened" can note them.
        kv = ctx(config).get("kv")
        if kv is not None and signs:
            await kv.set(f"pro_signs:{user.id}", ",".join(signs), ex=3600)
        labels = "\n".join(f"• {INDICATORS[k][0]}" for k in signs)
        return _out(state, Outgoing(text=t("pro_warning", lang, n=len(signs), s="" if len(signs) == 1 else "s", signs=labels),
                                    buttons=[Button(id="pro:danger", title=t("btn_pro_danger", lang)),
                                             Button(id="pro:safe", title=t("btn_pro_safe", lang)),
                                             Button(id="pro:unsure", title=t("btn_pro_unsure", lang))]),
                    events=_ev(state, ("protection_warning", ",".join(signs)[:120])))

    if action == "danger":
        buttons = [Button(id="task:sos_send", title=t("btn_sos_send", lang))] if has_contact else []
        buttons += [Button(id="help:embassy", title=t("btn_my_embassy", lang)), Button(id="pro:record", title=t("pro_m_record", lang)[:20])]
        return _out(state, Outgoing(text=t("pro_danger", lang, sos=t("pro_danger_sos" if has_contact else "pro_danger_no_sos", lang)),
                                    buttons=buttons[:3]), events=_ev(state, ("protection_danger", "")))
    if action in ("safe", "unsure"):
        return _out(state, options_menu(lang, has_contact), events=_ev(state, ("protection_safe_now", action)))
    if action == "checklist":
        return _out(state, Outgoing(text=t("pro_checklist", lang),
                                    buttons=[Button(id="pro:record", title=t("pro_m_record", lang)[:20]),
                                             Button(id="task:vault", title=t("task_m_vault", lang)),
                                             Button(id="menu:main", title=t("btn_menu", lang))]))
    if action == "help":
        return _out(state, Outgoing(text=t("pro_help", lang),
                                    buttons=[Button(id="pro:record", title=t("pro_m_record", lang)[:20]),
                                             Button(id="help:embassy", title=t("btn_my_embassy", lang)),
                                             Button(id="menu:main", title=t("btn_menu", lang))]))
    if action == "record" and user.consent_status != "granted":
        return _out(state, Outgoing(text=t("pro_help", lang)), Outgoing(text=t("task_needs_consent", lang)))
    if action == "record":
        from app.modules.cases.node import _set_draft, open_case

        kv = ctx(config).get("kv")
        raw = await kv.get(f"pro_signs:{user.id}") if kv is not None else None
        signs = [s for s in (raw.decode() if isinstance(raw, bytes) else raw or "").split(",") if s in INDICATORS]
        labels = [INDICATORS[k][0] for k in signs]
        first = "Incident record started" + (f". Signs described: {', '.join(labels)}" if labels else "")
        case, msgs = await open_case(state, config, "safety", first, actor=NODE, extra={"signs": labels} if labels else None)
        if case is None:
            return _out(state, *msgs)
        _set_draft(user, "case:note", {"id": case.id})
        return _out(state, Outgoing(text=t("pro_record_started", lang)), Outgoing(text=t("case_ask_note", lang)),
                    events=_ev(state, ("incident_record_started", ",".join(signs)[:120])))
    return _out(state, options_menu(lang, has_contact))
