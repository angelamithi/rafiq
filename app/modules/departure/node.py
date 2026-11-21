"""LangGraph node for Module 4: Departure Planner.

Fully deterministic: fixed, sourced text and the user's own ticks. The only
free text it reads is a travel date, which is parsed (never echoed or sent to
an AI). Button ids are checked against THIS user's checklist, so forged or
stale ids change nothing.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.parsing import parse_date
from app.agent.state import AgentState, ctx
from app.channels.base import Outgoing
from app.db import repo
from app.i18n import t
from app.modules.departure.checklist import date_prompt, detail, item_for, overview, title
from app.modules.departure.content import MAX_DAYS_AHEAD
from app.security.tool_policy import authorize

AWAIT_DATE = "plan:await_date"
NODE = "departure"


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _events(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


async def departure(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    msg = state["incoming"]
    bid = msg.button_id or ""
    cmd = state.get("command")
    text = state.get("text", "")
    today: date = ctx(config).get("today") or date.today()
    authorize(NODE, "get_own_plan")

    # ---- one item: show it, tick it, untick it
    parts = bid.split(":")
    if len(parts) == 3 and parts[0] == "plan" and parts[1] in ("item", "done", "undo"):
        user.step = "ready"
        item = item_for(user, parts[2])
        if item is None:      # not on this user's list (forged, or the profile changed)
            return _out(state, overview(user, today, lang))
        if parts[1] == "item":
            return _out(state, detail(user, item, lang))
        authorize(NODE, "update_own_plan")
        done = parts[1] == "done"
        repo.set_plan_item(user, item.key, done)
        header = t("plan_marked" if done else "plan_unmarked", lang, item=title(item, lang))
        return _out(state, overview(user, today, lang, header=header),
                    events=_events(state, ("plan_item", f"{item.key}={'done' if done else 'open'}")))

    # ---- travel date
    if bid == "plan:date" or cmd == "plan_date":
        user.step = AWAIT_DATE
        return _out(state, date_prompt(user, lang))
    if bid == "plan:date_skip":
        user.step = "ready"
        return _out(state, overview(user, today, lang, header=t("plan_date_skipped", lang)))
    if bid == "plan:date_clear":
        authorize(NODE, "update_own_plan")
        user.step = "ready"
        repo.set_travel_date(user, None)
        return _out(state, overview(user, today, lang, header=t("plan_date_removed", lang)),
                    events=_events(state, ("plan_date", "removed")))

    if user.step == AWAIT_DATE and not bid:
        if msg.kind != "text" or not text:
            return _out(state, date_prompt(user, lang))
        when = parse_date(text)
        if when is None:
            return _out(state, Outgoing(text=t("plan_date_bad", lang)), date_prompt(user, lang))
        days = (when - today).days
        if days < 0:
            return _out(state, Outgoing(text=t("plan_date_past", lang)), date_prompt(user, lang))
        if days > MAX_DAYS_AHEAD:
            return _out(state, Outgoing(text=t("plan_date_far", lang)), date_prompt(user, lang))
        authorize(NODE, "update_own_plan")
        repo.set_travel_date(user, when)
        user.step = "ready"
        header = t("plan_date_saved", lang)
        if user.visa_type != "visit" and "permit" not in repo.plan_done(user):
            header += "\n" + t("plan_date_after_permit", lang)
        return _out(state, overview(user, today, lang, header=header), events=_events(state, ("plan_date", "set")))

    # ---- the checklist itself (menu, "checklist", or anything else routed here)
    user.step = "ready"
    return _out(state, overview(user, today, lang))
