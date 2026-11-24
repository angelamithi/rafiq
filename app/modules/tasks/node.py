""""Do it for me" node: tasks Rafiq carries out for the user.

Least privilege (see app/security/tool_policy.py): this node may read and update
the user's OWN toolkit and vault, build PDFs, and send exactly one kind of
message to someone else: an SOS to the trusted contact the user chose, who
accepted the invite, after the user confirmed. Nothing is ever sent to an
employer, agency or office.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.parsing import clean_name, parse_date
from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import fmt_date, t
from app.modules.help.content import EMBASSIES, UAE_MISSIONS
from app.modules.money.content import CURRENCY
from app.modules.pay import amounts as am
from app.modules.tasks import contract as ct
from app.modules.tasks import pack as pk
from app.modules.tasks import rates as fx
from app.modules.tasks import vault as vt
from app.modules.tasks.content import (
    FORM_FIELD_MAX,
    JOIN_ATTEMPTS_PER_DAY,
    RATE_MAX_UP_PCT,
    RATE_MIN_UP_PCT,
    SOS_INVITE_HOURS,
    SOS_PER_HOUR,
    VAULT_KINDS,
    VAULT_MAX_BYTES,
    VAULT_MAX_DOCS,
)
from app.modules.tasks.forms import FORMS
from app.security.crypto import decrypt, encrypt
from app.security.tool_policy import authorize

NODE = "tasks"
MENU = ("pack", "vault", "sos", "rate", "forms", "contract", "status")
JOIN_RE = re.compile(r"^\s*(?:/start\s+join_|join\s+)([A-Za-z]{4}\d{4})\s*$", re.I)
_CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"

# typed command -> action
COMMAND_ACTIONS = {
    "tasks": "menu", "pack": "pack", "vault": "vault", "sos_menu": "sos", "sos": "sos_send", "rate": "rate",
    "forms": "forms", "contract": "contract", "task_status": "status",
}


# ---------------------------------------------------------------- helpers

def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _events(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


def _b(id_: str, key: str, lang: str | None) -> Button:
    return Button(id=id_, title=t(key, lang))


def _back(lang: str | None, *extra: Button) -> list[Button]:
    return [*extra, _b("task:menu", "btn_tasks", lang), _b("menu:main", "btn_menu", lang)][:3]


def _cancel(lang: str | None, *extra: Button) -> list[Button]:
    return [*extra, _b("task:cancel", "btn_cancel", lang)][:3]


def _today(config: RunnableConfig) -> date:
    return ctx(config).get("today") or date.today()


def _settings(config: RunnableConfig) -> Any:
    from app.config import get_settings

    return ctx(config).get("settings") or get_settings()


def _draft(user: Any) -> dict[str, Any]:
    d = repo.toolkit(user).get("draft")
    return d if isinstance(d, dict) else {}


def _set_draft(user: Any, step: str | None, draft: dict[str, Any] | None) -> None:
    repo.update_toolkit(user, draft=draft or None)
    user.step = step or "ready"


def _name(user: Any, lang: str | None) -> str:
    return repo.get_display_name(user) or "A Rafiq user"


def tasks_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"task:{k}", title=t(f"task_m_{k}", lang), description=t(f"task_m_{k}_d", lang)) for k in MENU]
    rows.insert(1, ListRow(id="case:list", title=t("task_m_cases", lang), description=t("task_m_cases_d", lang)))
    rows.insert(0, ListRow(id="life:brief", title=t("task_m_brief", lang), description=t("task_m_brief_d", lang)))
    return Outgoing(text=t("tasks_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


# ---------------------------------------------------------------- status

async def status_message(user: Any, session: Any, today: date, lang: str | None) -> Outgoing:
    from app.modules.arrival.checklist import items_for as arrival_items
    from app.modules.departure.checklist import items_for as departure_items

    lines = [t("status_head", lang)]
    if (exp := repo.get_visa_expiry(user)) and exp >= today:
        lines.append(t("status_visa", lang, date=fmt_date(exp, lang)))
    if user.plan is not None and repo.get_travel_date(user):
        total = len(departure_items(user))
        lines.append(t("status_travel", lang, done=min(len(repo.plan_done(user)), total), total=total))
    if user.arrival is not None and repo.get_plan_date(user, "arrival"):
        total = len(arrival_items(user))
        lines.append(t("status_arrival", lang, done=min(len(repo.plan_done(user, "arrival")), total), total=total))
    if repo.pay_watch_on(user):
        lines.append(t("status_pay", lang))
    if n := sum(1 for v in repo.pay_log(user).values() if v in ("unpaid", "part")):
        lines.append(t("status_unpaid", lang, n=n))
    if repo.social_checkin_on(user):
        lines.append(t("status_social", lang))
    docs = await vt.list_docs(session, user.id) if session is not None else []
    if docs:
        lines.append(t("status_vault", lang, n=len(docs)))
        upcoming = sorted((e, k) for _, k, e in docs if e and e >= today)
        if upcoming:
            lines.append(t("status_vault_next", lang, kind=vt.kind_label(upcoming[0][1], lang),
                           date=fmt_date(upcoming[0][0], lang)))
    kit = repo.toolkit(user)
    if kit.get("contact_address"):
        lines.append(t("status_sos", lang, name=kit.get("contact_name", "?")))
    elif kit.get("contact_pending"):
        lines.append(t("status_sos_pending", lang, name=kit.get("contact_pending")))
    if (rate := kit.get("rate")) and rate.get("target"):
        lines.append(t("status_rate", lang, target=fx.fmt_rate(rate["target"]), cur=rate.get("cur", "")))
    if len(lines) == 1:
        lines.append(t("status_none", lang))
    return Outgoing(text="\n".join(lines), buttons=_back(lang))


# ---------------------------------------------------------------- unpaid wages pack

def _pack_next_step(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Ask for whatever is still missing, or build the pack."""
    user, lang = state["user"], state["user"].language
    kit = repo.toolkit(user)
    if "employer" not in kit and not _draft(user).get("employer_skipped"):
        _set_draft(user, "task:pack_employer", {"task": "pack"})
        return _out(state, Outgoing(text=t("pack_intro", lang), buttons=_cancel(lang, _b("task:pack_skip", "btn_skip", lang))))
    if not kit.get("salary"):
        _set_draft(user, "task:pack_salary", {**_draft(user), "task": "pack"})
        return _out(state, Outgoing(text=t("pack_ask_salary", lang), buttons=_cancel(lang)))
    if "job_start" not in kit and not _draft(user).get("start_skipped"):
        _set_draft(user, "task:pack_start", {**_draft(user), "task": "pack"})
        return _out(state, Outgoing(text=t("pack_ask_start", lang), buttons=_cancel(lang, _b("task:pack_skip", "btn_skip", lang))))
    log = repo.pay_log(user)
    if not any(v in ("unpaid", "part") for v in log.values()):
        _set_draft(user, "task:pack_months", {**_draft(user), "task": "pack"})
        return _out(state, Outgoing(text=t("pack_ask_months", lang), buttons=_cancel(lang)))
    return _pack_build(state, config)


def _pack_build(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    authorize("tasks.employment", "build_document")
    today = _today(config)
    kit = repo.toolkit(user)
    start = date.fromisoformat(kit["job_start"]) if kit.get("job_start") else None
    from app.modules.pay.node import is_domestic

    facts = pk.PackFacts(name=_name(user, lang), employer=kit.get("employer") or t("pack_employer_unknown", lang),
                         salary=int(kit["salary"]), start=start, log=repo.pay_log(user), domestic=is_domestic(user),
                         home_country=user.home_country, sector=user.sector,
                         received=am.received(user),
                         agreed=am.agreed_months(user))
    pdf = pk.build(facts, today, lang)
    s = pk.summary(facts, today, lang)
    _set_draft(user, None, None)
    return _out(state,
                Outgoing(text=t("pack_caption", lang), file=pdf, filename=f"unpaid-wages-{today.isoformat()}.pdf",
                         file_mime="application/pdf"),
                Outgoing(text=t("pack_ready", lang, **{k: s[k] for k in ("unpaid", "part", "owed", "gratuity")}),
                         buttons=_back(lang, _b("pay:how", "btn_how_to_complain", lang))),
                events=_events(state, ("task_pack_built", str(len(facts.log)))))


def _pack_input(state: AgentState, config: RunnableConfig, text: str, skip: bool) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    step = user.step
    authorize("tasks.employment", "update_own_toolkit")
    if step == "task:pack_employer":
        if skip:
            _set_draft(user, step, {**_draft(user), "employer_skipped": True})
        else:
            name = re.sub(r"\s+", " ", text).strip()[:FORM_FIELD_MAX]
            if len(name) < 2:
                return _out(state, Outgoing(text=t("form_bad_text", lang), buttons=_cancel(lang)))
            repo.update_toolkit(user, employer=name)
    elif step == "task:pack_salary":
        if (v := pk.parse_salary(text)) is None:
            return _out(state, Outgoing(text=t("pack_bad_salary", lang), buttons=_cancel(lang)))
        repo.update_toolkit(user, salary=v)
    elif step == "task:pack_start":
        if skip:
            _set_draft(user, step, {**_draft(user), "start_skipped": True})
        elif (d := pk.parse_month_year(text, _today(config))) is None:
            return _out(state, Outgoing(text=t("pack_bad_start", lang), buttons=_cancel(lang, _b("task:pack_skip", "btn_skip", lang))))
        else:
            repo.update_toolkit(user, job_start=d.isoformat())
    elif step == "task:pack_months":
        months = pk.parse_months(text, _today(config))
        if not months:
            return _out(state, Outgoing(text=t("pack_bad_months", lang), buttons=_cancel(lang)))
        for m, st in months.items():
            repo.set_pay_status(user, m, st)
    return _pack_next_step(state, config)


# ---------------------------------------------------------------- vault

async def vault_screen(state: AgentState, session: Any, lang: str | None) -> Outgoing:
    user = state["user"]
    docs = await vt.list_docs(session, user.id)
    if not docs:
        return Outgoing(text=t("vault_head", lang) + "\n\n" + t("vault_empty", lang),
                        buttons=_back(lang, _b("task:vault_add", "btn_vault_add", lang)))
    rows = [ListRow(id=f"task:doc:{i}", title=vt.kind_label(k, lang)[:24],
                    description=(t("vault_doc_expiry", lang, date=fmt_date(e, lang)).strip(" ()") if e else None))
            for i, k, e in docs[:9]]
    if len(docs) < VAULT_MAX_DOCS:
        rows.append(ListRow(id="task:vault_add", title=t("btn_vault_add", lang)[:24]))
    return Outgoing(text=t("vault_head", lang) + "\n\n" + t("vault_list_head", lang, n=len(docs), max=VAULT_MAX_DOCS),
                    menu=ListMenu(button=t("btn_vault_open", lang), rows=rows[:10]))


def _vault_kinds(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"task:vk:{k}", title=t(f"vault_k_{k}", lang)) for k in VAULT_KINDS]
    return Outgoing(text=t("vault_pick_kind", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


async def _vault_file(state: AgentState, config: RunnableConfig, session: Any) -> dict[str, Any]:
    """A photo/PDF arrived while waiting for a document to save."""
    user, msg, lang = state["user"], state["incoming"], state["user"].language
    kind = _draft(user).get("kind", "other")
    if msg.kind != "media" or msg.media_type not in ("image", "document"):
        return _out(state, Outgoing(text=t("vault_need_file", lang), buttons=_cancel(lang)))
    authorize("tasks.life_admin", "update_own_vault")
    if await vt.count(session, user.id) >= VAULT_MAX_DOCS:
        _set_draft(user, None, None)
        return _out(state, Outgoing(text=t("vault_full", lang, max=VAULT_MAX_DOCS), buttons=_back(lang)))
    from app.media.fetch import MediaError, fetch_media
    from app.media.reader import read_document, sniff

    loader = ctx(config).get("media_loader") or fetch_media
    try:
        media = await loader(msg.channel, msg.media_id or "")
    except MediaError as e:
        key = "vault_too_big" if e.code == "too_large" else "vault_download_failed"
        return _out(state, Outgoing(text=t(key, lang), buttons=_cancel(lang)))
    if len(media.data) > VAULT_MAX_BYTES:
        return _out(state, Outgoing(text=t("vault_too_big", lang), buttons=_cancel(lang)))
    mime = sniff(media.data)
    if mime is None:
        return _out(state, Outgoing(text=t("vault_bad_file", lang), buttons=_cancel(lang)))

    # Read the page to suggest the expiry date (AI transcribes; rules pick the date).
    expiry = None
    if kind in ("passport", "visa", "eid", "contract", "other"):
        model = ctx(config).get("doc_model", "default")
        if model == "default":
            from app.agent.llm import get_doc_model

            model = get_doc_model()
        settings = _settings(config)
        res = await read_document(media.data, model=model, max_bytes=VAULT_MAX_BYTES, max_pages=2,
                                  timeout=float(settings.llm_doc_timeout_seconds))
        if res.text:
            expiry = vt.find_expiry(res.text, _today(config))
    doc_id = await vt.save(session, user.id, kind, media.data, mime, None)
    ev = _events(state, ("vault_saved", kind))
    if kind == "offer":   # offers don't expire: done
        _set_draft(user, None, None)
        return _out(state, Outgoing(text=t("vault_saved", lang, kind=vt.kind_label(kind, lang),
                                           remind=t("vault_saved_no_remind", lang)), buttons=_back(lang)), events=ev)
    if expiry:
        _set_draft(user, "task:vault_date", {"kind": kind, "doc": doc_id, "suggested": expiry.isoformat()})
        return _out(state, Outgoing(text=t("vault_found_expiry", lang, date=fmt_date(expiry, lang)),
                                    buttons=[_b("task:vault_yes", "btn_yes_correct", lang),
                                             _b("task:vault_change", "btn_change_date", lang),
                                             _b("task:vault_nodate", "btn_no_date", lang)]), events=ev)
    _set_draft(user, "task:vault_date", {"kind": kind, "doc": doc_id})
    return _out(state, Outgoing(text=t("vault_ask_expiry", lang), buttons=[_b("task:vault_nodate", "btn_no_date", lang)]),
                events=ev)


async def _vault_set_date(state: AgentState, config: RunnableConfig, session: Any, expiry: date | None) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    d = _draft(user)
    doc = await vt.get(session, user.id, d.get("doc", ""))
    _set_draft(user, None, None)
    if doc is None:
        return _out(state, Outgoing(text=t("vault_not_found", lang), buttons=_back(lang)))
    doc.expiry_enc = encrypt(expiry.isoformat()) if expiry else None
    kind_txt = vt.kind_label(doc.kind, lang)
    today = _today(config)
    if expiry is None:
        remind = t("vault_saved_no_remind", lang)
    elif expiry < today:
        remind = t("vault_saved_expired", lang, date=fmt_date(expiry, lang))
    else:
        remind = t("vault_saved_remind", lang, date=fmt_date(expiry, lang))
    text = t("vault_saved", lang, kind=kind_txt, remind=remind)
    if doc.kind == "visa" and expiry and expiry >= today:
        repo.set_field(user, "visa_expiry", expiry)
        text += "\n" + t("vault_visa_synced", lang)
    return _out(state, Outgoing(text=text, buttons=_back(lang, _b("task:vault", "task_m_vault", lang))))


async def _vault_open(state: AgentState, session: Any, doc_id: str) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    authorize("tasks.life_admin", "get_own_vault")
    doc = await vt.get(session, user.id, doc_id)
    data = vt.decrypt_file(doc.file_enc) if doc else None
    if doc is None or data is None:
        return _out(state, Outgoing(text=t("vault_not_found", lang), buttons=_back(lang)))
    raw = decrypt(doc.expiry_enc)
    exp = t("vault_doc_expiry", lang, date=fmt_date(date.fromisoformat(raw), lang)) if raw else ""
    return _out(state,
                Outgoing(text=t("vault_doc_caption", lang, kind=vt.kind_label(doc.kind, lang), expiry=exp),
                         file=data, filename=vt.filename_for(doc.kind, doc.mime), file_mime=doc.mime,
                         buttons=[_b(f"task:docdel:{doc.id}", "btn_vault_delete", lang),
                                  _b("task:vault", "task_m_vault", lang), _b("menu:main", "btn_menu", lang)]),
                events=_events(state, ("vault_opened", doc.kind)))


# ---------------------------------------------------------------- SOS

def _new_code() -> str:
    return "".join(secrets.choice(_CODE_LETTERS) for _ in range(4)) + "".join(secrets.choice("0123456789") for _ in range(4))


def _invite_card(user: Any, code: str, settings: Any, lang: str | None) -> str:
    link = ""
    if user.channel == "telegram" and settings.telegram_bot_username:
        link = t("sos_invite_link_tg", lang, bot=settings.telegram_bot_username.lstrip("@"), code=code)
    elif user.channel == "whatsapp" and settings.whatsapp_public_number:
        link = t("sos_invite_link_wa", lang, number="".join(c for c in settings.whatsapp_public_number if c.isdigit()),
                 code=code)
    return t("sos_invite_card", lang, owner=_name(user, lang), code=code, link=link)


async def _sos_invite(state: AgentState, config: RunnableConfig, contact_name: str) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    kv = ctx(config).get("kv")
    kit = repo.toolkit(user)
    if old := kit.get("invite_code"):
        await kv.delete(f"sos_inv:{old}")
    code = _new_code()
    await kv.set(f"sos_inv:{code}", user.id, ex=SOS_INVITE_HOURS * 3600)
    kit.update(contact_pending=contact_name, invite_code=code, draft=None)
    repo.save_toolkit(user, kit)
    user.step = "ready"
    return _out(state, Outgoing(text=t("sos_invite", lang, name=contact_name, hours=SOS_INVITE_HOURS)),
                Outgoing(text=_invite_card(user, code, _settings(config), lang)),
                Outgoing(text="👆", buttons=_back(lang)),
                events=_events(state, ("sos_invite_created", user.channel)))


def _sos_screen(user: Any, lang: str | None) -> Outgoing:
    kit = repo.toolkit(user)
    if kit.get("contact_address"):
        return Outgoing(text=t("sos_have_contact", lang, name=kit.get("contact_name", "?")),
                        buttons=[_b("task:sos_send", "btn_sos_send", lang), _b("task:sos_change", "btn_sos_change", lang),
                                 _b("task:sos_remove", "btn_sos_remove", lang)])
    if kit.get("contact_pending"):
        return Outgoing(text=t("sos_pending", lang, name=kit["contact_pending"]),
                        buttons=[_b("task:sos_reinvite", "btn_sos_reinvite", lang), _b("task:sos_change", "btn_sos_change", lang),
                                 _b("task:menu", "btn_tasks", lang)])
    return Outgoing(text=t("sos_intro", lang), buttons=_cancel(lang))


async def _sos_send(state: AgentState, config: RunnableConfig, *, lat: float | None = None,
                    lon: float | None = None) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    kv = ctx(config).get("kv")
    kit = repo.toolkit(user)
    user.step = "ready"
    if not kit.get("contact_address"):
        return _out(state, Outgoing(text=t("sos_no_contact", lang),
                                    buttons=[_b("task:sos", "btn_sos_setup", lang), _b("menu:help", "menu_help", lang)]))
    nonce = kit.get("sos_nonce")
    authorize("tasks.protection", "send_sos", confirmed_nonce=nonce, expected_nonce=nonce)   # set when the user tapped Send SOS
    from datetime import datetime, timezone

    hour = f"sos:{user.id}:{datetime.now(timezone.utc):%Y%m%d%H}"
    n = await kv.incr(hour)
    if n == 1:
        await kv.expire(hour, 3700)
    if n > SOS_PER_HOUR:
        return _out(state, Outgoing(text=t("sos_limit", lang, n=SOS_PER_HOUR)))
    if lat is None:
        raw = decrypt(await kv.get(f"sosloc:{user.id}") or None)
        if raw:
            lat, lon = json.loads(raw)
    await kv.delete(f"sosloc:{user.id}")
    owner = _name(user, lang)
    where = t("sos_where", lang, lat=lat, lon=lon) if lat is not None else t("sos_where_none", lang)
    missions = EMBASSIES.get(user.home_country or "")
    embassy_url = missions[0][1] if missions else UAE_MISSIONS
    alert = t("sos_alert", lang, owner=owner, where=where, embassy=t("sos_embassy", lang, url=embassy_url))
    settings = _settings(config)
    loc_param = f"https://maps.google.com/?q={lat},{lon}" if lat is not None else "No location shared"
    template = (settings.whatsapp_sos_template, [owner, loc_param]) if settings.whatsapp_sos_template else None
    item = {"channel": kit["contact_channel"], "to": kit["contact_address"], "out": Outgoing(text=alert),
            "template": template, "is_sos": True}
    kit.pop("sos_nonce", None)
    repo.save_toolkit(user, kit)
    return _out(state, Outgoing(text=t("sos_sent", lang, name=kit.get("contact_name", "?")),
                                buttons=[_b("help:embassy", "btn_my_embassy", lang), _b("menu:help", "menu_help", lang)]),
                outbox=[*state.get("outbox", []), item],
                events=_events(state, ("sos_sent", "location" if lat is not None else "no_location")))


async def _sos_join(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Someone sent JOIN <code>: they agree to be a trusted contact."""
    user, msg, lang = state["user"], state["incoming"], state["user"].language
    kv = ctx(config).get("kv")
    session = ctx(config).get("db")
    m = JOIN_RE.match(state.get("text", ""))
    code = m.group(1).upper() if m else ""
    tries = f"sos_join_try:{user.identity_hash}:{date.today().isoformat()}"
    n = await kv.incr(tries)
    if n == 1:
        await kv.expire(tries, 90_000)
    if n > JOIN_ATTEMPTS_PER_DAY:
        return _out(state, Outgoing(text=t("sos_join_limit", lang)))
    owner_id = await kv.get(f"sos_inv:{code}") if code else None
    if isinstance(owner_id, bytes):
        owner_id = owner_id.decode()
    if not owner_id:
        return _out(state, Outgoing(text=t("sos_bad_code", lang)), events=_events(state, ("sos_join_failed", "")))
    if owner_id == user.id:
        return _out(state, Outgoing(text=t("sos_own_code", lang)))
    from app.db.models import User

    owner = await session.get(User, owner_id)
    if owner is None:
        await kv.delete(f"sos_inv:{code}")
        return _out(state, Outgoing(text=t("sos_bad_code", lang)))
    kit = repo.toolkit(owner)
    name = kit.get("contact_pending") or "Your contact"
    kit.update(contact_name=name, contact_channel=msg.channel, contact_address=msg.external_id)
    for k in ("contact_pending", "invite_code"):
        kit.pop(k, None)
    repo.save_toolkit(owner, kit, contact_hash=user.identity_hash)
    await kv.delete(f"sos_inv:{code}")
    owner_name = repo.get_display_name(owner) or "your friend"
    out = []
    if to := decrypt(owner.address_enc):
        out.append({"channel": owner.channel, "to": to, "template": None,
                    "out": Outgoing(text=t("sos_joined_owner", owner.language, name=name))})
    return _out(state, Outgoing(text=t("sos_joined_contact", lang, owner=owner_name)),
                outbox=[*state.get("outbox", []), *out], events=_events(state, ("sos_contact_joined", msg.channel)))


async def _sos_leave(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """The trusted contact sent 'stop sos': unlink them from everyone who chose them."""
    from sqlalchemy import select

    from app.db.models import Toolkit, User

    user, lang = state["user"], state["user"].language
    session = ctx(config).get("db")
    owners = (await session.execute(select(User).join(Toolkit, Toolkit.user_id == User.id)
                                    .where(Toolkit.contact_hash == user.identity_hash))).scalars().all()
    if not owners:
        return _out(state, Outgoing(text=t("sos_not_contact", lang)))
    out = []
    for owner in owners:
        kit = repo.toolkit(owner)
        name = kit.get("contact_name", "Your contact")
        for k in ("contact_name", "contact_channel", "contact_address"):
            kit.pop(k, None)
        repo.save_toolkit(owner, kit, contact_hash=None)
        if to := decrypt(owner.address_enc):
            out.append({"channel": owner.channel, "to": to, "template": None,
                        "out": Outgoing(text=t("sos_owner_removed", owner.language, name=name))})
    return _out(state, Outgoing(text=t("sos_left", lang)), outbox=[*state.get("outbox", []), *out],
                events=_events(state, ("sos_contact_left", str(len(owners)))))


# ---------------------------------------------------------------- rates

def _currency(user: Any) -> str | None:
    kit = repo.toolkit(user)
    return (kit.get("rate") or {}).get("cur") or kit.get("currency") or CURRENCY.get(user.home_country or "")


async def _rate_screen(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    cur = _currency(user)
    if not cur:
        _set_draft(user, "task:rate_cur", {"task": "rate"})
        return _out(state, Outgoing(text=t("rate_no_currency", lang), buttons=_cancel(lang)))
    rates = await fx.get_rates(ctx(config).get("kv"), _settings(config).fx_url, ctx(config).get("fx_fetcher"))
    if not rates or cur not in rates.rates:
        return _out(state, Outgoing(text=t("rate_unavailable", lang), buttons=_back(lang)))
    now = rates.rates[cur]
    text = t("rate_head", lang, rate=fx.fmt_rate(now), cur=cur, source="open.er-api.com", updated=rates.updated or "today")
    alert = repo.toolkit(user).get("rate") or {}
    if alert.get("target"):
        text += "\n\n" + t("rate_current_alert", lang, target=fx.fmt_rate(alert["target"]), cur=cur)
        buttons = [_b("task:rate_own", "btn_rate_own", lang), _b("task:rate_stop", "btn_rate_cancel", lang),
                   _b("task:menu", "btn_tasks", lang)]
    else:
        buttons = [_b("task:rate:1", "btn_rate_1", lang), _b("task:rate:2", "btn_rate_2", lang),
                   _b("task:rate_own", "btn_rate_own", lang)]
    return _out(state, Outgoing(text=text, buttons=buttons))


async def _rate_set(state: AgentState, config: RunnableConfig, *, pct: float | None = None,
                    target: float | None = None) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    authorize("tasks.financial", "update_own_toolkit")
    cur = _currency(user)
    rates = await fx.get_rates(ctx(config).get("kv"), _settings(config).fx_url, ctx(config).get("fx_fetcher"))
    if not cur or not rates or cur not in rates.rates:
        return _out(state, Outgoing(text=t("rate_unavailable", lang), buttons=_back(lang)))
    now = rates.rates[cur]
    low, high = now * (1 + RATE_MIN_UP_PCT / 100), now * (1 + RATE_MAX_UP_PCT / 100)
    if pct is not None:
        target = now * (1 + pct / 100)
    if target is None or not (low <= target <= high):
        _set_draft(user, "task:rate_target", {"task": "rate"})
        return _out(state, Outgoing(text=t("rate_bad_target", lang, low=fx.fmt_rate(low), high=fx.fmt_rate(high)),
                                    buttons=_cancel(lang)))
    target = float(fx.fmt_rate(target).replace(",", ""))
    kit = repo.toolkit(user)
    kit.update(rate={"cur": cur, "target": target, "base": now}, draft=None)
    repo.save_toolkit(user, kit, rate_on=True)
    user.step = "ready"
    return _out(state, Outgoing(text=t("rate_set", lang, target=fx.fmt_rate(target), cur=cur, rate=fx.fmt_rate(now)),
                                buttons=_back(lang)),
                events=_events(state, ("rate_alert_set", cur)))


# ---------------------------------------------------------------- forms

def _forms_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"task:form:{k}", title=t(f"form_{k}", lang), description=t(f"form_{k}_d", lang)) for k in FORMS]
    return Outgoing(text=t("forms_head", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def _form_ask(state: AgentState, config: RunnableConfig, draft: dict[str, Any]) -> dict[str, Any]:
    """Ask the next unanswered question, or build the letter."""
    user, lang = state["user"], state["user"].language
    form = FORMS[draft["form"]]
    answers = draft.setdefault("a", {})
    kit = repo.toolkit(user)
    for f in form.fields:
        if f.key in answers:
            continue
        if f.key == "employer" and kit.get("employer"):
            answers["employer"] = kit["employer"]
            continue
        draft["q"] = f.key
        _set_draft(user, "task:form", draft)
        return _out(state, Outgoing(text=t(f.question, lang), buttons=_cancel(lang)))
    authorize("tasks.employment", "build_document")
    from app.modules.tasks.forms import build_letter

    today = _today(config)
    subject, pdf = build_letter(form.key, answers, _name(user, lang), today, lang)
    if answers.get("employer") and not kit.get("employer"):
        repo.update_toolkit(user, employer=answers["employer"])
    _set_draft(user, None, None)
    msgs = [Outgoing(text=t("form_caption", lang, title=subject), file=pdf, filename=f"{form.key}-letter.pdf",
                     file_mime="application/pdf"),
            Outgoing(text=t("form_ready", lang) + (("\n\n" + t(form.tip, lang)) if form.tip else ""),
                     buttons=_back(lang, _b("task:forms", "task_m_forms", lang)))]
    return _out(state, *msgs, events=_events(state, ("task_letter_built", form.key)))


def _form_input(state: AgentState, config: RunnableConfig, text: str) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    draft = _draft(user)
    if draft.get("form") not in FORMS:
        _set_draft(user, None, None)
        return _out(state, tasks_menu(lang))
    field = next((f for f in FORMS[draft["form"]].fields if f.key == draft.get("q")), None)
    if field is None:
        return _form_ask(state, config, draft)
    value = re.sub(r"\s+", " ", text).strip()
    if field.kind == "date":
        d = parse_date(value)
        if not d:
            return _out(state, Outgoing(text=t("form_bad_date", lang), buttons=_cancel(lang)))
        value = fmt_date(d, lang)
    elif not (1 <= len(value) <= FORM_FIELD_MAX):
        return _out(state, Outgoing(text=t("form_bad_text", lang), buttons=_cancel(lang)))
    draft.setdefault("a", {})[field.key] = value
    return _form_ask(state, config, draft)


# ---------------------------------------------------------------- contract switch

async def _contract_read(state: AgentState, config: RunnableConfig) -> tuple[str | None, str | None]:
    """Text of the offer/contract the user just sent (photo, PDF or pasted). (text, media_id)"""
    msg = state["incoming"]
    if msg.kind == "media" and msg.media_type in ("image", "document"):
        from app.media.flow import read_media_from_message

        res, _ = await read_media_from_message(state, config)
        return res.text, msg.media_id
    text = state.get("text", "")
    return (text if len(text) >= 20 else None), None


async def _contract_input(state: AgentState, config: RunnableConfig, session: Any) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    step = user.step
    text, media_id = await _contract_read(state, config)
    if not text:
        return _out(state, Outgoing(text=t("contract_unreadable", lang), buttons=_cancel(lang)))
    terms = ct.extract(text)
    if not terms.found():
        return _out(state, Outgoing(text=t("contract_no_terms", lang), buttons=_cancel(lang)))
    draft = _draft(user)
    if step == "task:contract_offer":
        draft.update(offer=terms.__dict__, offer_media=media_id)
        _set_draft(user, "task:contract_doc", draft)
        return _out(state, Outgoing(text=t("contract_ask_contract", lang), buttons=_cancel(lang)))
    offer = ct.Terms(**(draft.get("offer") or {}))
    return _contract_report(state, offer, terms, draft.get("offer_media"), media_id)


def _contract_report(state: AgentState, offer: ct.Terms, contract: ct.Terms, offer_media: str | None,
                     contract_media: str | None) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    rows = ct.compare(offer, contract)
    lines = [t("contract_head", lang)]
    for r in rows:
        mark = "⛔" if r.worse else ("✅" if r.worse is False else "❔")
        lines.append(t("contract_row", lang, label=t(f"contract_lbl_{r.key}", lang),
                       offer=r.offer or t("contract_unknown", lang), contract=r.contract or t("contract_unknown", lang),
                       mark=mark))
    worse = any(r.worse for r in rows)
    unknown = any(r.worse is None for r in rows)
    lines += ["", t("contract_bad" if worse else "contract_ok", lang)]
    if any(r.key == "salary_basic_only" for r in rows):
        lines.append(t("contract_salary_basic_only", lang))
    if any(r.key == "job" and r.worse is None and r.offer and r.contract for r in rows):
        lines.append(t("contract_arabic_job", lang))
    if unknown and not worse:
        lines.append(t("contract_partial", lang))
    lines += ["", t("contract_note", lang)]
    draft = {"offer_media": offer_media, "contract_media": contract_media} if offer_media and contract_media else None
    _set_draft(user, None, draft)
    extra = [_b("task:contract_save", "btn_save_docs", lang)] if draft else []
    return _out(state, Outgoing(text="\n".join(lines), buttons=_back(lang, *extra)),
                events=_events(state, ("contract_checked", "worse" if worse else "ok")))


async def _contract_save(state: AgentState, config: RunnableConfig, session: Any) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    d = _draft(user)
    _set_draft(user, None, None)
    if not d.get("offer_media") or not d.get("contract_media"):
        return _out(state, Outgoing(text=t("vault_download_failed", lang), buttons=_back(lang)))
    if await vt.count(session, user.id) + 2 > VAULT_MAX_DOCS:
        return _out(state, Outgoing(text=t("vault_full", lang, max=VAULT_MAX_DOCS), buttons=_back(lang)))
    authorize("tasks.employment", "save_to_vault")
    from app.media.fetch import MediaError, fetch_media
    from app.media.reader import sniff

    loader = ctx(config).get("media_loader") or fetch_media
    msg = state["incoming"]
    for kind, mid in (("offer", d["offer_media"]), ("contract", d["contract_media"])):
        try:
            media = await loader(msg.channel, mid)
        except MediaError:
            return _out(state, Outgoing(text=t("vault_download_failed", lang), buttons=_back(lang)))
        mime = sniff(media.data)
        if mime and len(media.data) <= VAULT_MAX_BYTES:
            await vt.save(session, user.id, kind, media.data, mime, None)
    return _out(state, Outgoing(text=t("contract_saved", lang), buttons=_back(lang, _b("task:vault", "task_m_vault", lang))),
                events=_events(state, ("vault_saved", "offer+contract")))


async def _contract_start(state: AgentState, session: Any) -> dict[str, Any]:
    user, lang = state["user"], state["user"].language
    _set_draft(user, "task:contract_offer", {"task": "contract"})
    has_offer = any(k == "offer" for _, k, _ in await vt.list_docs(session, user.id))
    if has_offer:
        return _out(state, Outgoing(text=t("contract_intro", lang)),
                    Outgoing(text=t("contract_use_saved", lang),
                             buttons=_cancel(lang, _b("task:contract_saved", "btn_use_saved", lang))))
    return _out(state, Outgoing(text=t("contract_intro", lang), buttons=_cancel(lang)))


async def _contract_use_saved(state: AgentState, config: RunnableConfig, session: Any) -> dict[str, Any]:
    from sqlalchemy import select

    from app.db.models import VaultDoc
    from app.media.reader import read_document

    user, lang = state["user"], state["user"].language
    doc = (await session.execute(select(VaultDoc).where(VaultDoc.user_id == user.id, VaultDoc.kind == "offer")
                                 .order_by(VaultDoc.created_at.desc()))).scalars().first()
    data = vt.decrypt_file(doc.file_enc) if doc else None
    if not data:
        return _out(state, Outgoing(text=t("vault_not_found", lang), buttons=_cancel(lang)))
    model = ctx(config).get("doc_model", "default")
    if model == "default":
        from app.agent.llm import get_doc_model

        model = get_doc_model()
    s = _settings(config)
    res = await read_document(data, model=model, max_bytes=VAULT_MAX_BYTES, max_pages=s.pdf_max_pages,
                              timeout=float(s.llm_doc_timeout_seconds))
    terms = ct.extract(res.text or "")
    if not terms.found():
        return _out(state, Outgoing(text=t("contract_no_terms", lang), buttons=_cancel(lang)))
    _set_draft(user, "task:contract_doc", {"task": "contract", "offer": terms.__dict__})
    return _out(state, Outgoing(text=t("contract_ask_contract", lang), buttons=_cancel(lang)))


# ---------------------------------------------------------------- the node

async def tasks(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user, msg = state["user"], state["incoming"]
    lang = user.language
    cmd = state.get("command")
    session = ctx(config).get("db")
    authorize(NODE, "get_own_profile")

    # Trusted-contact join/leave work for anyone (the contact may be new to Rafiq).
    if cmd == "sos_join":
        return await _sos_join(state, config)
    if cmd == "sos_leave":
        return await _sos_leave(state, config)
    if user.consent_status != "granted":
        return _out(state, Outgoing(text=t("task_needs_consent", lang)))

    bid = msg.button_id or ""
    action = bid.split(":", 1)[1] if bid.startswith("task:") else COMMAND_ACTIONS.get(cmd or "", "")
    text = state.get("text", "")

    # Shared location: used for an SOS, never stored (kept 10 minutes, encrypted, if no SOS yet).
    if msg.kind == "location":
        if user.step == "task:sos_loc":
            return await _sos_send(state, config, lat=msg.latitude, lon=msg.longitude)
        kit = repo.toolkit(user)
        if not kit.get("contact_address"):
            return _out(state, Outgoing(text=t("sos_location_nocontact", lang),
                                        buttons=_back(lang, _b("task:sos", "btn_sos_setup", lang))))
        await ctx(config)["kv"].set(f"sosloc:{user.id}", encrypt(json.dumps([msg.latitude, msg.longitude])) or "", ex=600)
        kit["sos_nonce"] = secrets.token_hex(4)
        repo.save_toolkit(user, kit)
        return _out(state, Outgoing(text=t("sos_location_nostep", lang),
                                    buttons=[_b("task:sos_now", "btn_sos_send", lang), _b("task:cancel", "btn_cancel", lang)]))

    if action == "cancel":
        kit = repo.toolkit(user)
        kit.pop("sos_nonce", None)
        kit.pop("draft", None)
        repo.save_toolkit(user, kit)
        user.step = "ready"
        await ctx(config)["kv"].delete(f"sosloc:{user.id}")
        return _out(state, Outgoing(text=t("task_cancelled", lang), buttons=_back(lang)))

    # ---- answers to a question we asked (typed text or a file)
    if not bid and user.step.startswith("task:"):
        step = user.step
        if step.startswith("task:pack_"):
            return _pack_input(state, config, text, skip=False)
        if step == "task:vault_file":
            return await _vault_file(state, config, session)
        if step == "task:vault_date":
            d = parse_date(text)
            if not d:
                return _out(state, Outgoing(text=t("vault_bad_date", lang), buttons=[_b("task:vault_nodate", "btn_no_date", lang)]))
            return await _vault_set_date(state, config, session, d)
        if step == "task:sos_name":
            name = clean_name(text)
            if not name:
                return _out(state, Outgoing(text=t("sos_bad_name", lang), buttons=_cancel(lang)))
            return await _sos_invite(state, config, name)
        if step == "task:sos_loc":
            return _out(state, Outgoing(text=t("sos_ask_location", lang),
                                        buttons=[_b("task:sos_now", "btn_sos_now", lang), _b("task:cancel", "btn_cancel", lang)]))
        if step == "task:rate_cur":
            code = re.sub(r"[^A-Za-z]", "", text).upper()
            rates = await fx.get_rates(ctx(config).get("kv"), _settings(config).fx_url, ctx(config).get("fx_fetcher"))
            if len(code) != 3 or (rates and code not in rates.rates):
                return _out(state, Outgoing(text=t("rate_bad_currency", lang), buttons=_cancel(lang)))
            repo.update_toolkit(user, currency=code, draft=None)
            user.step = "ready"
            return await _rate_screen(state, config)
        if step == "task:rate_target":
            return await _rate_set(state, config, target=fx.parse_target(text) or -1.0)
        if step == "task:form":
            return _form_input(state, config, text)
        if step in ("task:contract_offer", "task:contract_doc"):
            return await _contract_input(state, config, session)
        user.step = "ready"

    # ---- menu actions
    if action in ("", "menu"):
        return _out(state, tasks_menu(lang))
    if action == "status":
        return _out(state, await status_message(user, session, _today(config), lang))

    if action == "pack":
        return _pack_next_step(state, config)
    if action == "pack_skip" and user.step in ("task:pack_employer", "task:pack_start"):
        return _pack_input(state, config, "", skip=True)

    if action == "vault":
        return _out(state, await vault_screen(state, session, lang))
    if action == "vault_add":
        if await vt.count(session, user.id) >= VAULT_MAX_DOCS:
            return _out(state, Outgoing(text=t("vault_full", lang, max=VAULT_MAX_DOCS), buttons=_back(lang)))
        return _out(state, _vault_kinds(lang))
    if action.startswith("vk:") and action[3:] in VAULT_KINDS:
        kind = action[3:]
        _set_draft(user, "task:vault_file", {"kind": kind})
        return _out(state, Outgoing(text=t("vault_send_photo", lang, kind=vt.kind_label(kind, lang)), buttons=_cancel(lang)))
    if action == "vault_yes" and user.step == "task:vault_date" and _draft(user).get("suggested"):
        return await _vault_set_date(state, config, session, date.fromisoformat(_draft(user)["suggested"]))
    if action == "vault_nodate" and user.step == "task:vault_date":
        return await _vault_set_date(state, config, session, None)
    if action == "vault_change" and user.step == "task:vault_date":
        return _out(state, Outgoing(text=t("vault_ask_expiry", lang), buttons=[_b("task:vault_nodate", "btn_no_date", lang)]))
    if action.startswith("doc:"):
        return await _vault_open(state, session, action[4:])
    if action.startswith("docdel:"):
        authorize("tasks.life_admin", "update_own_vault")
        ok = await vt.remove(session, user.id, action[7:])
        return _out(state, Outgoing(text=t("vault_deleted" if ok else "vault_not_found", lang),
                                    buttons=_back(lang, _b("task:vault", "task_m_vault", lang))),
                    events=_events(state, ("vault_deleted", "")) if ok else state.get("events", []))

    if action == "sos":
        screen = _sos_screen(user, lang)
        kit = repo.toolkit(user)
        if not kit.get("contact_address") and not kit.get("contact_pending"):
            user.step = "task:sos_name"
        return _out(state, screen)
    if action in ("sos_change",):
        user.step = "task:sos_name"
        return _out(state, Outgoing(text=t("sos_intro", lang), buttons=_cancel(lang)))
    if action == "sos_reinvite":
        kit = repo.toolkit(user)
        if kit.get("contact_pending"):
            return await _sos_invite(state, config, kit["contact_pending"])
        return _out(state, _sos_screen(user, lang))
    if action == "sos_remove":
        kit = repo.toolkit(user)
        name = kit.get("contact_name") or kit.get("contact_pending") or ""
        for k in ("contact_name", "contact_channel", "contact_address", "contact_pending", "invite_code"):
            kit.pop(k, None)
        repo.save_toolkit(user, kit, contact_hash=None)
        return _out(state, Outgoing(text=t("sos_removed", lang, name=name), buttons=_back(lang)),
                    events=_events(state, ("sos_contact_removed", "")))
    if action == "sos_send":
        kit = repo.toolkit(user)
        if not kit.get("contact_address"):   # no contact yet: emergency help first, then offer to set one up
            from app.modules.help.node import help_menu

            return _out(state, help_menu(lang), Outgoing(text=t("sos_no_contact", lang),
                                                         buttons=[_b("task:sos", "btn_sos_setup", lang),
                                                                  _b("menu:main", "btn_menu", lang)]))
        kit["sos_nonce"] = secrets.token_hex(4)
        repo.save_toolkit(user, kit)
        return _out(state, Outgoing(text=t("sos_confirm", lang, name=kit.get("contact_name", "?")),
                                    buttons=[_b("task:sos_now", "btn_sos_now", lang), _b("task:sos_loc", "btn_sos_location", lang),
                                             _b("task:cancel", "btn_cancel", lang)]))
    if action == "sos_loc":
        if not repo.toolkit(user).get("sos_nonce"):
            return _out(state, _sos_screen(user, lang))
        user.step = "task:sos_loc"
        return _out(state, Outgoing(text=t("sos_ask_location", lang),
                                    buttons=[_b("task:sos_now", "btn_sos_now", lang), _b("task:cancel", "btn_cancel", lang)]))
    if action == "sos_now":
        if not repo.toolkit(user).get("sos_nonce"):   # only straight after the user confirmed
            return _out(state, _sos_screen(user, lang))
        return await _sos_send(state, config)

    if action == "rate":
        return await _rate_screen(state, config)
    if action in ("rate:1", "rate:2"):
        return await _rate_set(state, config, pct=float(action[-1]))
    if action == "rate_own":
        cur = _currency(user)
        rates = await fx.get_rates(ctx(config).get("kv"), _settings(config).fx_url, ctx(config).get("fx_fetcher"))
        if not cur or not rates or cur not in rates.rates:
            return _out(state, Outgoing(text=t("rate_unavailable", lang), buttons=_back(lang)))
        _set_draft(user, "task:rate_target", {"task": "rate"})
        return _out(state, Outgoing(text=t("rate_ask_target", lang, example=fx.fmt_rate(rates.rates[cur] * 1.02), cur=cur),
                                    buttons=_cancel(lang)))
    if action == "rate_stop":
        kit = repo.toolkit(user)
        kit.pop("rate", None)
        repo.save_toolkit(user, kit, rate_on=False)
        return _out(state, Outgoing(text=t("rate_stopped", lang), buttons=_back(lang)))

    if action == "forms":
        return _out(state, _forms_menu(lang))
    if action.startswith("form:") and action[5:] in FORMS:
        return _form_ask(state, config, {"form": action[5:], "a": {}})

    if action == "contract":
        return await _contract_start(state, session)
    if action == "contract_saved" and user.step == "task:contract_offer":
        return await _contract_use_saved(state, config, session)
    if action == "contract_save":
        return await _contract_save(state, config, session)

    return _out(state, tasks_menu(lang))
