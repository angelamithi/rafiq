"""LangGraph node for Module 5: Arrival Guide.

Fully deterministic: fixed, sourced text and the user's own ticks. The only
free text it reads is an arrival date, which is parsed, never echoed or sent
to an AI. Button ids are checked against THIS user's own steps.
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
from app.modules.arrival.checklist import (
    KIND,
    date_prompt,
    detail,
    example_date,
    item_for,
    overview,
    title,
)
from app.modules.arrival.content import MAX_DAYS_AGO
from app.security.tool_policy import authorize

AWAIT_DATE = "arrive:await_date"
NODE = "arrival"


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _events(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


async def arrival(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    msg = state["incoming"]
    bid = msg.button_id or ""
    cmd = state.get("command") or ""
    text = state.get("text", "")
    today: date = ctx(config).get("today") or date.today()
    authorize(NODE, "get_own_plan")

    # ---- a typed topic ("emirates id", "ejari"; see content.TOPICS) opens that step directly
    if cmd.startswith("arrive_topic:"):
        user.step = "ready"
        key = cmd.split(":", 1)[1]
        if key == "iloe" and user.sector == "domestic":
            return _out(state, Outgoing(text=t("arr_iloe_exempt", lang)), overview(user, today, lang))
        if key == "residency" and user.visa_type == "visit":
            key = "visit"
        item = item_for(user, key)
        return _out(state, detail(user, item, today, lang) if item else overview(user, today, lang))

    # ---- one step: show it, tick it, untick it
    parts = bid.split(":")
    if len(parts) == 3 and parts[0] == "arrive" and parts[1] in ("item", "done", "undo"):
        user.step = "ready"
        item = item_for(user, parts[2])
        if item is None:      # not on this user's list (forged, or the profile changed)
            return _out(state, overview(user, today, lang))
        if parts[1] == "item":
            return _out(state, detail(user, item, today, lang))
        authorize(NODE, "update_own_plan")
        done = parts[1] == "done"
        repo.set_plan_item(user, item.key, done, KIND)
        header = t("arr_marked" if done else "arr_unmarked", lang, item=title(item, lang))
        return _out(state, overview(user, today, lang, header=header),
                    events=_events(state, ("arrival_item", f"{item.key}={'done' if done else 'open'}")))

    # ---- arrival date
    if bid == "arrive:date" or cmd == "arrive_date":
        user.step = AWAIT_DATE
        return _out(state, date_prompt(user, today, lang))
    if bid == "arrive:date_skip":
        user.step = "ready"
        return _out(state, overview(user, today, lang, header=t("arr_date_skipped", lang)))
    if bid == "arrive:date_clear":
        authorize(NODE, "update_own_plan")
        user.step = "ready"
        repo.set_plan_date(user, KIND, None)
        return _out(state, overview(user, today, lang, header=t("arr_date_removed", lang)),
                    events=_events(state, ("arrival_date", "removed")))

    if user.step == AWAIT_DATE and not bid:
        if msg.kind != "text" or not text:
            return _out(state, date_prompt(user, today, lang))
        when = parse_date(text)
        if when is None:
            return _out(state, Outgoing(text=t("arr_date_bad", lang, example=example_date(today))), date_prompt(user, today, lang))
        days_ago = (today - when).days
        if days_ago < 0:
            return _out(state, Outgoing(text=t("arr_date_future", lang)), date_prompt(user, today, lang))
        if days_ago > MAX_DAYS_AGO:
            user.step = "ready"
            return _out(state, Outgoing(text=t("arr_date_old", lang)), overview(user, today, lang))
        authorize(NODE, "update_own_plan")
        repo.set_plan_date(user, KIND, when)
        user.step = "ready"
        return _out(state, overview(user, today, lang, header=t("arr_date_saved", lang)),
                    events=_events(state, ("arrival_date", "set")))

    # ---- the guide itself (menu, "arrival", or anything else routed here)
    user.step = "ready"
    return _out(state, overview(user, today, lang))

