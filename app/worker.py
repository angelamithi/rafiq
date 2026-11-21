"""Background worker (arq + Redis).

Run with:  arq app.worker.WorkerSettings
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from arq import cron
from arq.connections import ArqRedis, RedisSettings, create_pool
from redis.asyncio import Redis
from sqlalchemy import delete, select

from app.channels.base import Incoming, Outgoing
from app.channels.sender import _client, keep_typing, sender_for
from app.channels.whatsapp import send_template
from app.config import get_settings
from app.db.models import ArrivalPlan, AuditLog, DeparturePlan, PayRecord, SocialPrefs, Toolkit, User, VaultDoc, utcnow
from app.db.session import init_db, sessionmaker
from app.logging_setup import setup_logging
from app.security.ratelimit import KV
from app.service import process_message

log = logging.getLogger(__name__)

PENDING_CONSENT_TTL = timedelta(days=7)
AUDIT_RETENTION = timedelta(days=180)

_pool: ArqRedis | None = None
_kv: "RedisKV | None" = None


class RedisKV:
    """Adapter so the security limiter can use Redis."""

    def __init__(self, r: Redis) -> None:
        self.r = r

    async def incr(self, key: str) -> int:
        return int(await self.r.incr(key))

    async def expire(self, key: str, seconds: int) -> None:
        await self.r.expire(key, seconds)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None:
        return await self.r.set(key, value, ex=ex, nx=nx)

    async def get(self, key: str) -> str | None:
        v = await self.r.get(key)
        return v.decode() if isinstance(v, bytes) else v

    async def delete(self, *keys: str) -> None:
        if keys:
            await self.r.delete(*keys)


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


async def _get_kv() -> KV:
    global _kv
    if _kv is None:
        _kv = RedisKV(Redis.from_url(get_settings().redis_url))
    return _kv


async def enqueue(msg: Incoming) -> None:
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())
    # Job id = message id: Redis refuses duplicates, a second layer against webhook retries.
    await _pool.enqueue_job("process_incoming", msg.model_dump(), _job_id=f"msg:{msg.channel}:{msg.message_id}")


async def _handle(msg: Incoming, kv: KV) -> None:
    async with keep_typing(msg):
        await process_message(msg, kv=kv, send=sender_for(msg.channel))


async def handle_inline(msg: Incoming) -> None:
    """Used when USE_QUEUE=false (local development)."""
    await _handle(msg, await _get_kv())


# ---------------------------------------------------------------- arq jobs

async def process_incoming(ctx: dict[str, Any], data: dict[str, Any]) -> None:
    await _handle(Incoming(**data), ctx["kv"])


async def cleanup(ctx: dict[str, Any]) -> None:
    """Data retention: remove inactive users, abandoned sign-ups, old audit rows."""
    s = get_settings()
    now = utcnow()
    async with sessionmaker()() as session:
        stale = (await session.execute(
            select(User.id).where(
                (User.last_seen_at < now - timedelta(days=s.data_retention_days_inactive))
                | ((User.consent_status != "granted") & (User.created_at < now - PENDING_CONSENT_TTL))
            )
        )).scalars().all()
        if stale:
            await session.execute(delete(DeparturePlan).where(DeparturePlan.user_id.in_(stale)))
            await session.execute(delete(ArrivalPlan).where(ArrivalPlan.user_id.in_(stale)))
            await session.execute(delete(PayRecord).where(PayRecord.user_id.in_(stale)))
            await session.execute(delete(SocialPrefs).where(SocialPrefs.user_id.in_(stale)))
            await session.execute(delete(Toolkit).where(Toolkit.user_id.in_(stale)))
            await session.execute(delete(VaultDoc).where(VaultDoc.user_id.in_(stale)))
            await session.execute(delete(User).where(User.id.in_(stale)))
            session.add(AuditLog(user_ref=None, event="retention_cleanup", detail=f"removed {len(stale)} users"))
        await session.execute(delete(AuditLog).where(AuditLog.created_at < now - AUDIT_RETENTION))
        await session.commit()
    log.info("Retention cleanup removed %s users", len(stale))


async def send_reminder(r) -> bool:  # type: ignore[no-untyped-def]
    """Deliver one reminder (visa or departure). WhatsApp needs an approved
    template, because reminders are sent outside the 24-hour reply window."""
    s = get_settings()
    if r.channel == "whatsapp":
        kind = getattr(r, "kind", "visa")
        template = {"departure": s.whatsapp_departure_template, "arrival": s.whatsapp_arrival_template,
                    "pay": s.whatsapp_pay_template, "social": s.whatsapp_social_template,
                    "vault": s.whatsapp_vault_template, "rate": s.whatsapp_rate_template}.get(kind, s.whatsapp_visa_template)
        if not template:
            log.info("No WhatsApp template set for %s reminders; skipping", kind)
            return False
        await send_template(_client("whatsapp"), r.to, template, s.whatsapp_template_language, r.template_params)
        return True
    await _client(r.channel).send(r.to, Outgoing(text=r.text))
    return True


async def visa_reminders(ctx: dict[str, Any]) -> None:
    from datetime import date

    from app.modules.stay_legal.visa import send_due_reminders

    async with sessionmaker()() as session:
        n = await send_due_reminders(session, ctx["kv"], send_reminder, date.today())
    log.info("Visa reminders sent: %s", n)


async def departure_reminders(ctx: dict[str, Any]) -> None:
    from datetime import date

    from app.modules.departure.reminders import send_due_departure_reminders

    async with sessionmaker()() as session:
        n = await send_due_departure_reminders(session, ctx["kv"], send_reminder, date.today())
    log.info("Departure reminders sent: %s", n)


async def arrival_reminders(ctx: dict[str, Any]) -> None:
    from datetime import date

    from app.modules.arrival.reminders import send_due_arrival_reminders

    async with sessionmaker()() as session:
        n = await send_due_arrival_reminders(session, ctx["kv"], send_reminder, date.today())
    log.info("Arrival reminders sent: %s", n)


async def salary_checkins(ctx: dict[str, Any]) -> None:
    from datetime import date

    from app.modules.pay.checkins import send_due_checkins

    async with sessionmaker()() as session:
        n = await send_due_checkins(session, ctx["kv"], send_reminder, date.today())
    log.info("Salary check-ins sent: %s", n)


async def wellbeing_checkins(ctx: dict[str, Any]) -> None:
    from datetime import date

    from app.modules.social.checkins import send_due_checkins

    async with sessionmaker()() as session:
        n = await send_due_checkins(session, ctx["kv"], send_reminder, date.today())
    log.info("Wellbeing check-ins sent: %s", n)


async def vault_reminders(ctx: dict[str, Any]) -> None:
    from datetime import date

    from app.modules.tasks.vault import send_due_vault_reminders

    async with sessionmaker()() as session:
        n = await send_due_vault_reminders(session, ctx["kv"], send_reminder, date.today())
    log.info("Document expiry reminders sent: %s", n)


async def rate_alerts(ctx: dict[str, Any]) -> None:
    from app.modules.tasks.rates import check_rate_alerts

    async with sessionmaker()() as session:
        n = await check_rate_alerts(session, ctx["kv"], send_reminder, get_settings().fx_url)
    log.info("Rate alerts sent: %s", n)


async def notify_admin(text: str) -> None:
    """Team alerts only (never users). Telegram chat set in ADMIN_TELEGRAM_CHAT_ID."""
    s = get_settings()
    if s.admin_telegram_chat_id and s.telegram_bot_token:
        await _client("telegram").send(s.admin_telegram_chat_id, Outgoing(text=text))
    else:
        log.warning("Rule monitor alert (no admin chat configured):\n%s", text)


async def rule_monitor(ctx: dict[str, Any]) -> None:
    from app.knowledge.fetch import fetch_text
    from app.knowledge.monitor import run_checks

    if not get_settings().rule_monitor_enabled:
        return
    async with sessionmaker()() as session:
        results = await run_checks(session, fetch_text, notify_admin)
    log.info("Rule monitor checked %s sources", len(results))


async def startup(ctx: dict[str, Any]) -> None:
    setup_logging(get_settings().log_level)
    await init_db()
    ctx["kv"] = RedisKV(Redis.from_url(get_settings().redis_url))


class WorkerSettings:
    functions = [process_incoming]
    cron_jobs = [
        cron(cleanup, hour={2}, minute={30}),
        cron(visa_reminders, hour={5}, minute={0}),   # 05:00 UTC = 09:00 in the UAE
        cron(departure_reminders, hour={5}, minute={10}),
        cron(arrival_reminders, hour={5}, minute={20}),
        cron(salary_checkins, hour={14}, minute={0}),   # 18:00 in the UAE, after most shifts
        cron(wellbeing_checkins, weekday={4}, hour={14}, minute={15}),   # Fridays, 18:15 in the UAE
        cron(rule_monitor, weekday={0}, hour={3}, minute={0}),            # Mondays, 07:00 in the UAE
        cron(vault_reminders, hour={5}, minute={30}),                     # 09:30 in the UAE
        cron(rate_alerts, hour={4, 8, 12, 16}, minute={45}),              # 4 times a day
    ]
    on_startup = startup
    redis_settings = _redis_settings()
    max_jobs = 20
    job_timeout = 60
    keep_result = 0
