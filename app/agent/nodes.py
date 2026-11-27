"""Graph nodes for Module 1 (Welcome & profile + privacy).

Module 1 is fully deterministic: no AI model writes replies, so it cannot
hallucinate, leak a prompt or be jailbroken. Every write goes through the tool
policy and only touches the current (verified) user's record.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent import ui
from app.agent.parsing import clean_country, clean_name, match_option, parse_date
from app.agent.state import AgentState, ctx
from app.channels.base import Outgoing
from app.db import repo
from app.db.models import User, utcnow
from app.i18n import COUNTRIES, SECTORS, STAGES, VISAS, VISAS_WITH_EXPIRY, t
from app.security.tool_policy import ToolNotAllowed, authorize, new_nonce

ONBOARDING_ORDER = ["name", "stage", "country", "visa", "expiry", "sector", "summary"]
ONBOARDING_STEPS = {"new", "consent", "name", "stage", "country", "country_other", "visa", "expiry", "sector", "summary", "edit"}
DELETE_CONFIRM_TTL_SECONDS = 600
MAX_FUTURE_YEARS = 10


def _lang(user: User) -> str:
    return user.language or "en"


def _months(config: RunnableConfig) -> int:
    settings = ctx(config).get("settings")
    return max(1, round(getattr(settings, "data_retention_days_inactive", 365) / 30.4))


def _today(config: RunnableConfig) -> date:
    return ctx(config).get("today") or date.today()


def _update(user: User, node: str, field: str, value: object) -> None:
    authorize(node, "update_own_profile")
    repo.set_field(user, field, value)


def _out(state: AgentState, *msgs: Outgoing | None, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *(m for m in msgs if m)], **extra}


def _event(state: AgentState, event: str, detail: str = "") -> list[tuple[str, str]]:
    return [*state.get("events", []), (event, detail)]


def reprompt(user: User, config: RunnableConfig) -> Outgoing | None:
    """Re-show the question the user is in the middle of, if any."""
    if user.step in ONBOARDING_STEPS - {"new"}:
        return ui.prompt_for_step(user.step, user.language, user, months=_months(config))
    return None


# ======================================================================= onboarding

def _choice(state: AgentState, step: str) -> str | None:
    """The option the user picked for this step: a button that belongs to the
    step (server-side check, so forged/stale ids are ignored) or matching text."""
    user = state["user"]
    options = ui.options_for_step(step, user.language)
    valid_ids = {oid for oid, _ in options}
    bid = state["incoming"].button_id
    if bid:
        return bid if bid in valid_ids else None
    return match_option(state.get("text", ""), options)


def _advance(user: User, after: str, config: RunnableConfig) -> list[Outgoing]:
    """Move to the next question, or back to where an edit started."""
    lang = user.language
    nxt = ONBOARDING_ORDER[ONBOARDING_ORDER.index(after) + 1] if after in ONBOARDING_ORDER else "summary"
    if after == "visa" and user.visa_type in VISAS_WITH_EXPIRY:
        nxt = "expiry"  # a visa with an end date always needs the date, even when editing
    elif nxt == "expiry" and user.visa_type not in VISAS_WITH_EXPIRY:
        nxt = "sector"

    if user.return_to and nxt != "expiry":
        target, user.return_to = user.return_to, None
        if target == "profile":
            user.step = "ready"
            return [ui.text("saved", lang), ui.profile_view(lang, user)]
        if target == "visa":  # Module 3: back to "My visa" after updating the date
            from app.modules.stay_legal.visa import visa_status

            user.step = "ready"
            return [ui.text("saved", lang), visa_status(user, _today(config), lang)]
        user.step = target
        return [ui.prompt_for_step(target, lang, user, months=_months(config))]  # type: ignore[list-item]

    user.step = nxt
    return [ui.prompt_for_step(nxt, lang, user, months=_months(config))]  # type: ignore[list-item]


async def onboarding(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    text = state.get("text", "")
    step = user.step
    nudge = ui.text("use_buttons", lang)

    if state["incoming"].kind == "media" and step != "new":
        return _out(state, ui.text("media_not_yet", lang), reprompt(user, config))  # type: ignore[arg-type]

    if step in ("new", "lang"):  # "lang" kept only for records from older versions
        _update(user, "onboarding", "language", "en")
        user.step = "consent"
        return _out(state, ui.consent_prompt("en", welcome=True, months=_months(config)))

    if step == "consent":
        if state.get("reconsent"):
            return _out(state, ui.consent_prompt(lang, updated=True, months=_months(config)))
        choice = _choice(state, "consent")
        if choice == "consent:more":
            return _out(state, ui.consent_prompt(lang, more=True, months=_months(config)))
        if choice == "consent:no":
            return _out(state, ui.text("consent_declined", lang), delete_user=True,
                        events=_event(state, "consent_declined"))
        if choice != "consent:yes":
            return _out(state, nudge, ui.consent_prompt(lang, months=_months(config)))
        settings = ctx(config).get("settings")
        user.consent_status = "granted"
        user.consent_version = getattr(settings, "privacy_policy_version", None)
        user.consent_at = utcnow()
        events = _event(state, "consent_granted", user.consent_version or "")
        if user.return_to:  # re-consent after a policy update
            user.step, user.return_to = "ready", None
            return _out(state, ui.main_menu(lang), events=events)
        user.step = "name"
        return _out(state, ui.name_prompt(lang), events=events)

    if step == "name":
        if _choice(state, "name") == "name:skip":
            _update(user, "onboarding", "display_name", None)
            return _out(state, *_advance(user, "name", config))
        name = clean_name(text) if state["incoming"].kind == "text" else None
        if not name:
            return _out(state, ui.text("name_invalid", lang), ui.name_prompt(lang))
        _update(user, "onboarding", "display_name", name)
        return _out(state, *_advance(user, "name", config))

    if step == "stage":
        choice = _choice(state, "stage")
        if not choice or choice.split(":")[1] not in STAGES:
            return _out(state, nudge, ui.stage_prompt(lang, user))
        _update(user, "onboarding", "journey_stage", choice.split(":")[1])
        return _out(state, *_advance(user, "stage", config))

    if step == "country":
        choice = _choice(state, "country")
        if choice == "country:other":
            user.step = "country_other"
            return _out(state, ui.country_other_prompt(lang))
        if choice and choice.split(":", 1)[1] in COUNTRIES:
            _update(user, "onboarding", "home_country", choice.split(":", 1)[1])
            return _out(state, *_advance(user, "country", config))
        typed = clean_country(text) if not state["incoming"].button_id else None
        if typed:  # users often just type their country instead of opening the list
            _update(user, "onboarding", "home_country", typed)
            return _out(state, *_advance(user, "country", config))
        return _out(state, nudge, ui.country_prompt(lang))

    if step == "country_other":
        country = clean_country(text)
        if not country:
            return _out(state, ui.text("country_invalid", lang))
        _update(user, "onboarding", "home_country", country)
        return _out(state, *_advance(user, "country", config))

    if step == "visa":
        choice = _choice(state, "visa")
        if not choice or choice.split(":")[1] not in VISAS:
            return _out(state, nudge, ui.visa_prompt(lang))
        _update(user, "onboarding", "visa_type", choice.split(":")[1])
        if user.visa_type not in VISAS_WITH_EXPIRY:
            _update(user, "onboarding", "visa_expiry", None)
        return _out(state, *_advance(user, "visa", config))

    if step == "expiry":
        if _choice(state, "expiry") == "expiry:skip":
            _update(user, "onboarding", "visa_expiry", None)
            return _out(state, *_advance(user, "expiry", config))
        d = parse_date(text)
        today = _today(config)
        if not d:
            return _out(state, ui.text("expiry_invalid", lang), ui.expiry_prompt(lang))
        if d < today:
            return _out(state, ui.text("expiry_past", lang), ui.expiry_prompt(lang))
        if d > today + timedelta(days=365 * MAX_FUTURE_YEARS):
            return _out(state, ui.text("expiry_too_far", lang), ui.expiry_prompt(lang))
        _update(user, "onboarding", "visa_expiry", d)
        return _out(state, *_advance(user, "expiry", config))

    if step == "sector":
        choice = _choice(state, "sector")
        if not choice or choice.split(":")[1] not in SECTORS:
            return _out(state, nudge, ui.sector_prompt(lang))
        _update(user, "onboarding", "sector", choice.split(":")[1])
        return _out(state, *_advance(user, "sector", config))

    if step == "summary":
        choice = _choice(state, "summary")
        if choice == "summary:edit":
            user.step = "edit"
            return _out(state, ui.edit_menu(lang))
        if choice != "summary:ok":
            return _out(state, nudge, ui.summary_prompt(lang, user))
        user.step = "ready"
        name = repo.get_display_name(user)
        done = ui.text("done", lang, name=name) if name else ui.text("done_no_name", lang)
        if user.journey_stage in ("planning", "offer"):
            done.text += "\n\n" + t("plan_tip", lang)
        elif user.journey_stage == "arrived":
            done.text += "\n\n" + t("arr_tip", lang)
        return _out(state, done, ui.main_menu(lang), events=_event(state, "onboarding_completed"))

    if step == "edit":
        choice = _choice(state, "edit")
        if not choice:
            return _out(state, nudge, ui.edit_menu(lang))
        field = choice.split(":")[1]
        user.return_to = user.return_to or "summary"
        user.step = field
        return _out(state, ui.prompt_for_step(field, lang, user, months=_months(config)))  # type: ignore[arg-type]

    # Unknown step (e.g. data from an older version): restart safely.
    user.step = "consent" if user.consent_status != "granted" else "ready"
    return _out(state, ui.main_menu(lang) if user.step == "ready" else ui.consent_prompt(lang, welcome=True, months=_months(config)))


# ======================================================================= menu & commands

async def menu(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = _lang(user)
    bid = state["incoming"].button_id or ""
    cmd = state.get("command")
    action = {
        "menu:main": "menu", "menu:profile": "profile", "menu:privacy": "privacy",
        "menu:help": "help", "profile:edit": "edit", "menu:more": "more",
    }.get(bid) or cmd or "menu"
    onboarding_active = user.step in ONBOARDING_STEPS

    # Already set up and only part-way through an edit:
    # a menu command simply cancels it (no dead ends).
    if onboarding_active and user.consent_status == "granted" and user.return_to in ("profile", "ready", "visa") and action != "help":
        user.step, user.return_to = "ready", None
        onboarding_active = False

    if action == "help":
        extra = reprompt(user, config) if onboarding_active else None
        return _out(state, *[m for m in (ui.help_message(lang), extra) if m])
    if onboarding_active:  # finish setting up first; keep the user on track
        return _out(state, ui.text("use_buttons", lang), reprompt(user, config))  # type: ignore[arg-type]

    if action == "profile":
        authorize("menu", "get_own_profile")
        return _out(state, ui.profile_view(lang, user))
    if action == "edit":
        user.step, user.return_to = "edit", "profile"
        return _out(state, ui.edit_menu(lang))
    if action == "stop":
        user.notifications_paused = 1
        return _out(state, ui.text("paused", lang), events=_event(state, "notifications_paused"))
    if action == "start":
        user.notifications_paused = 0
        return _out(state, ui.text("resumed", lang), ui.main_menu(lang), events=_event(state, "notifications_resumed"))
    if action == "greeting":
        return _out(state, ui.welcome_back(lang, user))
    if action == "more":
        return _out(state, ui.more_menu(lang))
    return _out(state, ui.main_menu(lang))


# ======================================================================= privacy

async def privacy(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = _lang(user)
    bid = state["incoming"].button_id or ""
    cmd = state.get("command")
    onboarding_active = user.step in ONBOARDING_STEPS

    if bid == "delete:no":
        user.pending_action = None
        tail = reprompt(user, config) if onboarding_active else ui.main_menu(lang)
        return _out(state, ui.text("delete_cancelled", lang), tail)  # type: ignore[arg-type]

    if bid.startswith("delete:yes:"):
        offered = bid.removeprefix("delete:yes:")
        expected, issued_at = _pending_delete(user)
        fresh = issued_at is not None and time.time() - issued_at <= DELETE_CONFIRM_TTL_SECONDS
        try:
            authorize("privacy", "delete_own_data", confirmed_nonce=offered, expected_nonce=expected if fresh else None)
        except ToolNotAllowed:
            user.pending_action = None
            return _out(state, ui.text("delete_expired", lang), events=_event(state, "delete_rejected", "bad_or_expired_nonce"))
        return _out(state, ui.text("deleted", lang), delete_user=True, events=_event(state, "data_deleted"))

    if bid == "privacy:delete" or cmd == "delete":
        nonce = new_nonce()
        user.pending_action = f"delete:{nonce}:{int(time.time())}"
        return _out(state, ui.delete_confirm(lang, nonce))

    if bid == "privacy:export" or cmd == "export":
        authorize("privacy", "export_own_data")
        authorize("privacy", "get_own_plan")
        authorize("privacy", "get_own_pay")
        msgs = [ui.export_message(lang, user)]
        if onboarding_active and (rp := reprompt(user, config)):
            msgs.append(rp)
        return _out(state, *msgs, events=_event(state, "data_exported"))

    msgs = [ui.privacy_menu(lang)]
    return _out(state, *msgs)


def _pending_delete(user: User) -> tuple[str | None, float | None]:
    parts = (user.pending_action or "").split(":")
    if len(parts) == 3 and parts[0] == "delete":
        try:
            return parts[1], float(parts[2])
        except ValueError:
            return None, None
    return None, None


# ======================================================================= fallback

async def fallback(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = _lang(user)
    if state["incoming"].kind in ("media", "unsupported"):
        return _out(state, ui.text("job_media", lang), ui.main_menu(lang))
    return _out(state, ui.main_menu(lang, intro=t("didnt_understand", lang)))
