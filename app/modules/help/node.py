"""LangGraph node for Module 9: Help & emergency.

Deterministic, fixed text with verified numbers and official links. Also hosts
the "not safe" response, which the router triggers from ANY state when a
message describes abuse, confinement or trafficking. Nothing is stored.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent import ui
from app.agent.state import AgentState
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.i18n import COUNTRIES, t
from app.modules.help import content  # noqa: F401  (registers the text)
from app.modules.help.content import (
    DUBAI_POLICE,
    EMBASSIES,
    GDRFA,
    ICP_SMART,
    U_AE_LOST_PASSPORT,
    UAE_MISSIONS,
    UNSAFE_PHRASES,
)
from app.security.tool_policy import authorize

NODE = "help"
MENU = ("unsafe", "embassy", "passport", "report", "police", "numbers", "about")
_UNSAFE = [re.compile(r"\b" + re.escape(p) + r"\b") for p in UNSAFE_PHRASES]
WAITING_STEPS = ("job:", "legal:", "plan:", "arrive:", "pay:", "money:")


def unsafe_intent(text: str) -> bool:
    """True if a message describes abuse, confinement, forced work or trafficking."""
    if not text:
        return False
    s = unicodedata.normalize("NFKC", text).lower().replace("’", "'").replace("‘", "'")
    s = re.sub(r"\s+", " ", s)
    return any(p.search(s) for p in _UNSAFE)


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _back(lang: str | None, *extra: Button) -> list[Button]:
    return [*extra, Button(id="menu:help", title=t("btn_help_menu", lang)), Button(id="menu:main", title=t("btn_menu", lang))][:3]


# ---------------------------------------------------------------- screens

def help_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"help:{k}", title=t(f"help_m_{k}", lang), description=t(f"help_m_{k}_d", lang)) for k in MENU]
    rows.insert(1, ListRow(id="task:sos_send", title=t("help_m_sos", lang), description=t("help_m_sos_d", lang)))
    return Outgoing(text=t("help_menu_text", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows[:10]))


def unsafe_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("help_unsafe", lang) + "\n\n" + t("help_unsafe_sos", lang),
                    buttons=[Button(id="task:sos_send", title=t("btn_sos_send", lang)),
                             Button(id="help:embassy", title=t("btn_my_embassy", lang)),
                             Button(id="menu:main", title=t("btn_menu", lang))])


def embassy_message(user, lang: str | None) -> Outgoing:  # type: ignore[no-untyped-def]
    missions = EMBASSIES.get(user.home_country or "")
    if missions:
        name = COUNTRIES.get(user.home_country, {}).get("en", user.home_country)
        lines = [t("help_embassy_head", lang, country=name)]
        lines += [t("help_embassy_line", lang, name=n, url=u) for n, u in missions]
        body = "\n".join(lines)
    else:
        body = t("help_embassy_other", lang, list=UAE_MISSIONS)
    body += "\n\n" + t("help_embassy_tail", lang) + "\n\n" + t("help_embassy_change", lang)
    return Outgoing(text=body, buttons=_back(lang))


def passport_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("help_passport", lang, gdrfa=GDRFA, icp=ICP_SMART, u_ae=U_AE_LOST_PASSPORT),
                    buttons=_back(lang, Button(id="help:embassy", title=t("btn_my_embassy", lang))))


def report_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("help_report", lang, police=DUBAI_POLICE), buttons=_back(lang))


def police_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("help_police", lang), buttons=_back(lang, Button(id="help:embassy", title=t("btn_my_embassy", lang))))


def numbers_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("help_numbers", lang), buttons=_back(lang, Button(id="help:unsafe", title=t("btn_im_not_safe", lang))))


# ---------------------------------------------------------------- the node

async def help_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    bid = state["incoming"].button_id or ""
    cmd = state.get("command") or ""
    action = bid.removeprefix("help:") if bid.startswith("help:") else ""

    if cmd == "unsafe_detected":
        # Like the crisis response: the user's place in any flow is kept.
        return _out(state, unsafe_message(lang), events=[*state.get("events", []), ("unsafe_support_shown", "")])

    if user.step.startswith(WAITING_STEPS):
        user.step = "ready"
    if action == "unsafe" or cmd == "unsafe":
        return _out(state, unsafe_message(lang))
    if action == "embassy" or cmd == "embassy":
        authorize(NODE, "get_own_profile")       # home country only
        return _out(state, embassy_message(user, lang))
    if action == "passport" or cmd == "lost_passport":
        return _out(state, passport_message(lang))
    if action == "report" or cmd == "report_crime":
        return _out(state, report_message(lang))
    if action == "police" or cmd == "police_trouble":
        return _out(state, police_message(lang))
    if action == "numbers" or cmd == "numbers":
        return _out(state, numbers_message(lang))
    if action == "about":
        return _out(state, ui.help_message(lang))
    return _out(state, help_menu(lang))
