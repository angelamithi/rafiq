"""The message pipeline. Every incoming message passes these gates in order:

 1. de-duplication (Meta retries webhooks)
 2. abuse cool-down and rate limits (per hashed identity)
 3. input cleaning + length limit
 4. prompt-injection / jailbreak / exfiltration / privilege-escalation scan
 5. the LangGraph agent (least-privilege tools, verified identity only)
 6. output guard on every reply (secrets, prompt canary, other people's
    data, non-official links)
 7. send

Message text is never stored or logged.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from app.agent.graph import build_graph
from app.knowledge.monitor import modules_under_review
from app.media.voice import voice_to_text
from app.agent.state import AgentState
from app.channels.base import Incoming, Outgoing
from app.config import Settings, get_settings
from app.db import repo
from app.db.session import sessionmaker
from app.i18n import fmt_date, t
from app.modules.job_safety.rules import looks_like_offer
from app.security.crypto import hash_identity
from app.security.injection import clean_input, scan
from app.security.output_guard import check_output
from app.security.ratelimit import KV, Limiter

log = logging.getLogger(__name__)

Send = Callable[[str, Outgoing], Awaitable[None]]
# Sends to someone other than the person chatting: (channel, address, message, whatsapp template).
# Only the SOS feature uses it, and only towards a trusted contact who opted in.
Relay = Callable[[str, str, Outgoing, "tuple[str, list[str]] | None"], Awaitable[None]]


def _own_values(user: Any) -> set[str]:
    """Personal values that belong to THIS user and may appear in their replies."""
    vals: set[str] = set()
    if name := repo.get_display_name(user):
        vals.add(name)
    if expiry := repo.get_visa_expiry(user):
        vals |= {expiry.isoformat(), fmt_date(expiry)}
    kit = repo.toolkit(user)
    for key in ("employer", "contact_name"):
        if isinstance(kit.get(key), str) and len(kit[key]) >= 2:
            vals.add(kit[key])
    return vals


def guard_replies(replies: list[Outgoing], own: set[str], lang: str | None) -> tuple[list[Outgoing], list[str]]:
    safe: list[Outgoing] = []
    reasons: list[str] = []
    for r in replies:
        chk = check_output(r.text, user_own_values=own)
        reasons += chk.reasons
        if chk.blocked:
            log.error("Outgoing message blocked by output guard: %s", ",".join(chk.reasons))
            safe.append(Outgoing(text=t("error", lang)))
            continue
        safe.append(r.model_copy(update={"text": chk.text}))
    return safe, reasons


async def _voice_note(msg: Incoming, user: Any, session: Any, *, kv: KV, ident: str, settings: Settings,
                      today: date | None, agent_context: dict[str, Any] | None) -> str | Outgoing:
    """Returns the transcript, or a reply explaining why the voice note can't be used."""
    lang = user.language
    if not settings.voice_enabled:
        return Outgoing(text=t("voice_off", lang))
    if user.consent_status != "granted":          # voice goes to Gemini: only with consent
        return Outgoing(text=t("voice_needs_consent", lang))
    if msg.duration and msg.duration > settings.voice_max_seconds:
        return Outgoing(text=t("voice_err_too_long", lang))
    key = f"voice:{ident}:{(today or date.today()).isoformat()}"
    count = await kv.incr(key)
    if count == 1:
        await kv.expire(key, 90_000)
    if count > settings.voice_per_day:
        return Outgoing(text=t("voice_limit", lang))
    ctxs = agent_context or {}
    res = await voice_to_text(msg.channel, msg.media_id or "", settings=settings,
                              loader=ctxs.get("media_loader"), model=ctxs.get("doc_model", "default"))
    if res.error or not res.text:
        await repo.audit(session, user.id, "voice_failed", res.error or "empty")
        return Outgoing(text=t(f"voice_err_{res.error or 'no_speech'}", lang))
    await repo.audit(session, user.id, "voice_transcribed")       # never the words themselves
    return res.text


async def process_message(
    msg: Incoming,
    *,
    kv: KV,
    send: Send,
    settings: Settings | None = None,
    today: date | None = None,
    agent_context: dict[str, Any] | None = None,
    relay: Relay | None = None,
) -> list[Outgoing]:
    """Run one incoming message through the full pipeline. Returns what was sent."""
    settings = settings or get_settings()
    limiter = Limiter(kv, settings.rate_limit_per_minute, settings.rate_limit_per_day)
    ident = hash_identity(msg.channel, msg.external_id)

    async def deliver(out: list[Outgoing]) -> list[Outgoing]:
        for o in out:
            await send(msg.external_id, o)
        return out

    # 1. duplicates
    if not await limiter.first_time_seen(f"{msg.channel}:{msg.message_id}"):
        return []

    # 2. cool-down and rate limits (before touching the database)
    if await limiter.in_cooldown(ident):
        if await kv.set(f"cooldown_notice:{ident}", "1", ex=settings.guard_cooldown_minutes * 60, nx=True):
            return await deliver([Outgoing(text=t("cooldown", None, minutes=settings.guard_cooldown_minutes))])
        return []
    allowed, first_block = await limiter.allow(ident)
    if not allowed:
        return await deliver([Outgoing(text=t("rate_limited", None))]) if first_block else []

    # 3. clean input
    text = clean_input(msg.text) if msg.kind == "text" else ""
    if msg.kind == "button":
        text = ""  # button ids are validated by the nodes; the visible title is ignored

    async with sessionmaker()() as session:
        user, is_new = await repo.get_or_create_user(session, msg.channel, msg.external_id)
        lang = user.language

        # 3b. Voice note -> English text (any spoken language). From here on it is
        #     treated EXACTLY like a typed message: same scan, checks and routing.
        heard: Outgoing | None = None
        if msg.kind == "media" and msg.media_type in ("audio", "voice"):
            voice = await _voice_note(msg, user, session, kv=kv, ident=ident, settings=settings,
                                      today=today, agent_context=agent_context)
            if isinstance(voice, Outgoing):
                await session.commit()
                return await deliver([voice])
            text = clean_input(voice)
            msg = msg.model_copy(update={"kind": "text", "text": text, "media_type": None, "media_id": None})
            heard = Outgoing(text=t("voice_heard", lang, text=text if len(text) <= 300 else text[:297] + "…"))

        if len(text) > settings.max_message_chars:
            await session.commit()
            return await deliver([Outgoing(text=t("too_long", lang, max=settings.max_message_chars))])

        # 4. attack scan (typed text only; button ids are never free text).
        #    A pasted job offer is a third-party DOCUMENT: suspicious text in it is
        #    reported to the user as a warning sign, never held against them.
        content_guard = None
        doc_mode = bool(text) and user.consent_status == "granted" and (
            user.step == "job:await_offer" or (user.step == "ready" and looks_like_offer(text))
        )
        if text and doc_mode:
            content_guard = scan(text, block_threshold=99)
            if content_guard.score >= 6:
                await repo.audit(session, user.id, "offer_injection_detected", ",".join(content_guard.categories))
        elif text:
            guard = scan(text)
            if guard.blocked:
                await repo.audit(session, user.id, "input_blocked", ",".join(guard.categories))
                cooled = await limiter.add_strike(ident, settings.guard_strikes_before_cooldown, settings.guard_cooldown_minutes)
                if cooled:
                    await repo.audit(session, user.id, "cooldown_started")
                    await kv.set(f"cooldown_notice:{ident}", "1", ex=settings.guard_cooldown_minutes * 60)
                await session.commit()
                key = "cooldown" if cooled else "blocked"
                return await deliver([Outgoing(text=t(key, lang, minutes=settings.guard_cooldown_minutes))])
            if guard.verdict == "flag":
                await repo.audit(session, user.id, "input_flagged", ",".join(guard.categories))

        # 5. agent
        state: AgentState = {"incoming": msg, "text": text, "user": user, "is_new": is_new, "replies": [], "events": [],
                             "content_guard": content_guard}
        config = {"configurable": {"settings": settings, "today": today, "kv": kv, "db": session, **(agent_context or {})}}
        try:
            result = await build_graph().ainvoke(state, config=config)
        except Exception:
            log.exception("Agent failed")
            await session.rollback()
            return await deliver([Outgoing(text=t("error", lang))])

        for event, detail in result.get("events", []):
            await repo.audit(session, user.id, event, detail)

        # 5b. Rule Monitor: if an official source for this topic changed and a
        #     person hasn't reviewed it yet, say so (never on safety screens).
        route = result.get("route")
        if route and result.get("replies") and state.get("command") not in ("crisis", "unsafe_detected") \
                and result.get("command") not in ("crisis", "unsafe_detected"):
            if route in await modules_under_review(session):
                result["replies"] = [*result["replies"], Outgoing(text=t("rule_review_notice", user.language))]

        # 5c. If the AI (not the rules) chose the topic, say so, so the user knows why they see this.
        if result.get("inferred_topic") and result.get("replies"):
            result["replies"] = [Outgoing(text=t("intent_guess", user.language, topic=result["inferred_topic"])),
                                 *result["replies"]]

        # 6. output guard (computed BEFORE a deletion, so own values are known)
        lang = user.language
        replies, reasons = guard_replies([*([heard] if heard else []), *result.get("replies", [])], _own_values(user), lang)
        if reasons:
            await repo.audit(session, user.id, "output_guard", ",".join(sorted(set(reasons)))[:255])

        # 6b. Messages for a trusted contact (SOS only) pass the same output guard.
        outbox: list[tuple[str, str, Outgoing, Any, bool]] = []
        for item in result.get("outbox", []) or []:
            safe_out, why = guard_replies([item["out"]], _own_values(user), lang)
            if why:
                await repo.audit(session, user.id, "output_guard_relay", ",".join(sorted(set(why)))[:255])
            outbox.append((item["channel"], item["to"], safe_out[0], item.get("template"), bool(item.get("is_sos"))))

        if result.get("delete_user"):
            await repo.delete_user(session, user)
        await session.commit()

    # 7. send
    sent = await deliver(replies)
    if outbox:
        if relay is None:
            from app.channels.sender import relay as default_relay

            relay = default_relay
        for channel, to, out, template, is_sos in outbox:
            try:
                await relay(channel, to, out, template)
            except Exception:
                log.exception("Relay to trusted contact failed")
                if is_sos:   # the user must know their alert didn't arrive
                    sent = [*sent, *await deliver([Outgoing(text=t("sos_relay_failed", lang))])]
    return sent
