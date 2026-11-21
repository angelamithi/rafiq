"""LangGraph node for Module 7: Friends & wellbeing.

Deterministic, fixed text. Never connects users with each other and never
shares anyone's details. Also hosts the crisis response, which the router
triggers from ANY state when someone mentions self-harm or suicide.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent import ui
from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import t
from app.modules.social import content  # noqa: F401  (registers the text)
from app.modules.social.content import (
    CRISIS_PHRASES,
    DUBAI_CULTURE,
    DUBAI_POLICE,
    MBRL,
    VISIT_DUBAI_EVENTS,
    current_events,
)
from app.security.tool_policy import authorize

NODE = "social"
MENU = ("lonely", "free", "meet", "talk", "checkin")
MOODS = {"mood_good": "good", "mood_ok": "ok", "mood_hard": "hard"}
_CRISIS = [re.compile(r"\b" + re.escape(p) + r"\b") for p in CRISIS_PHRASES]


def crisis_intent(text: str) -> bool:
    """True if the message mentions suicide or self-harm (checked on every message)."""
    if not text:
        return False
    s = unicodedata.normalize("NFKC", text).lower().replace("’", "'").replace("‘", "'")
    s = re.sub(r"\s+", " ", s)
    return any(p.search(s) for p in _CRISIS)


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _events(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


def _back(lang: str | None, *extra: Button) -> list[Button]:
    return [*extra, Button(id="menu:social", title=t("btn_soc_menu", lang)), Button(id="menu:main", title=t("btn_menu", lang))][:3]


# ---------------------------------------------------------------- screens

def social_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"social:{k}", title=t(f"soc_m_{k}", lang), description=t(f"soc_m_{k}_d", lang)) for k in MENU]
    return Outgoing(text=t("soc_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def lonely_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("soc_lonely", lang), buttons=[
        Button(id="social:free", title=t("btn_free_things", lang)),
        Button(id="social:talk", title=t("btn_talk", lang)),
        Button(id="menu:social", title=t("btn_soc_menu", lang)),
    ])


def free_messages(today: date, lang: str | None) -> list[Outgoing]:
    """Current dated events (if any) as their own message, then the always-free places."""
    out: list[Outgoing] = []
    now = current_events(today)
    if now:
        out.append(Outgoing(text=t("soc_events_head", lang) + "\n\n" + "\n\n".join(
            t(f"soc_event_{e.key}", lang, link=e.link) for e in now)))
    out.append(Outgoing(text=t("soc_free", lang, mbrl=MBRL, culture=DUBAI_CULTURE, events=VISIT_DUBAI_EVENTS),
                        buttons=_back(lang, Button(id="social:meet", title=t("btn_meet_safely", lang)))))
    return out


def meet_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("soc_meet", lang, police=DUBAI_POLICE),
                    buttons=_back(lang, Button(id="social:free", title=t("btn_free_things", lang))))


def talk_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("soc_talk", lang), buttons=_back(lang))


def checkin_screen(user, lang: str | None, *, header: str | None = None) -> Outgoing:  # type: ignore[no-untyped-def]
    on = repo.social_checkin_on(user)
    parts = [p for p in (header, t("soc_checkin_intro", lang), t("soc_checkin_on" if on else "soc_checkin_off", lang)) if p]
    toggle = Button(id=f"social:{'off' if on else 'on'}", title=t("btn_checkin_off" if on else "btn_checkin_on", lang))
    return Outgoing(text="\n\n".join(parts), buttons=_back(lang, toggle))


def crisis_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("soc_crisis", lang), buttons=[Button(id="social:talk", title=t("btn_talk", lang))])


# ---------------------------------------------------------------- the node

async def social(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    bid = state["incoming"].button_id or ""
    cmd = state.get("command") or ""
    today: date = ctx(config).get("today") or date.today()
    action = bid.removeprefix("social:") if bid.startswith("social:") else ""

    if cmd == "crisis":
        # Never changes the user's step: whatever they were doing is still there afterwards.
        return _out(state, crisis_message(lang), events=_events(state, ("crisis_support_shown", "")))

    user.step = "ready" if user.step.startswith(("job:", "legal:", "plan:", "arrive:", "pay:")) else user.step

    if cmd in MOODS:
        mood = MOODS[cmd]
        if mood == "hard":
            return _out(state, Outgoing(text=t("soc_mood_hard", lang)), talk_message(lang))
        if not repo.social_checkin_on(user):          # a bare "good" / "ok" with no check-in to answer
            return _out(state, ui.main_menu(lang))
        extra = Button(id="social:free", title=t("btn_free_things", lang))
        return _out(state, Outgoing(text=t(f"soc_mood_{mood}", lang), buttons=_back(lang, extra)))

    if action in ("on", "off"):
        authorize(NODE, "update_own_wellbeing_pref")
        repo.set_social_checkin(user, action == "on")
        header = t("soc_checkin_turned_on" if action == "on" else "soc_checkin_turned_off", lang)
        return _out(state, checkin_screen(user, lang, header=header), events=_events(state, ("wellbeing_checkin", action)))
    if action == "lonely" or cmd == "lonely":
        return _out(state, lonely_message(lang))
    if action == "free" or cmd == "free_things":
        return _out(state, *free_messages(today, lang))
    if action == "meet" or cmd == "meet":
        return _out(state, meet_message(lang))
    if action == "talk" or cmd == "talk":
        return _out(state, talk_message(lang))
    if action == "checkin" or cmd == "wellbeing_checkin":
        return _out(state, checkin_screen(user, lang))
    return _out(state, social_menu(lang))
