""""You fly in N days" reminders, sent by the worker's daily cron.

Travel dates are encrypted, so they're compared here in memory, never in SQL.
Each reminder is sent once (Redis key per user / travel date / day).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date

from sqlalchemy import select

from app.db import repo
from app.db.models import DeparturePlan, User
from app.i18n import fmt_date, t
from app.modules.departure.checklist import progress, title
from app.modules.departure.content import REMINDER_DAYS
from app.modules.stay_legal.visa import Reminder
from app.security.crypto import decrypt
from app.security.ratelimit import KV

log = logging.getLogger(__name__)
MAX_LISTED = 4


def reminder_text(user: User, travel: date, days: int) -> tuple[str, int]:
    lang = user.language
    _done, _total, left = progress(user)
    d = fmt_date(travel, lang)
    suffix = "_1" if days == 1 else ""
    if not left:
        return t(f"plan_reminder_done{suffix}", lang, days=days, date=d), 0
    names = [title(i, lang) for i in left[:MAX_LISTED]]
    if len(left) > MAX_LISTED:
        names.append(f"+{len(left) - MAX_LISTED} more")
    return t(f"plan_reminder{suffix}", lang, days=days, date=d, left=", ".join(names)), len(left)


async def due_departure_reminders(session, today: date) -> list[Reminder]:  # type: ignore[no-untyped-def]
    users = (await session.execute(
        select(User).join(DeparturePlan, DeparturePlan.user_id == User.id).where(
            User.consent_status == "granted", User.notifications_paused == 0, DeparturePlan.travel_date_enc.is_not(None),
        )
    )).scalars().all()
    out: list[Reminder] = []
    for u in users:
        travel = repo.get_travel_date(u)
        to = decrypt(u.address_enc)
        if not travel or not to:
            continue
        days = (travel - today).days
        if days not in REMINDER_DAYS:
            continue
        text, left = reminder_text(u, travel, days)
        name = repo.get_display_name(u) or "there"
        out.append(Reminder(u.id, u.channel, to, days, text, [name, fmt_date(travel, u.language), str(days), str(left)],
                            kind="departure"))
    return out


Sender = Callable[[Reminder], Awaitable[bool]]


async def send_due_departure_reminders(session, kv: KV, send: Sender, today: date) -> int:  # type: ignore[no-untyped-def]
    sent = 0
    for r in await due_departure_reminders(session, today):
        travel = today.toordinal() + r.days
        key = f"plan_rem:{r.user_id}:{travel}:{r.days}"
        if not await kv.set(key, "1", ex=40 * 86_400, nx=True):
            continue
        try:
            if await send(r):
                sent += 1
                await repo.audit(session, r.user_id, "plan_reminder_sent", f"days={r.days}")
            else:
                await kv.delete(key)
        except Exception:
            log.warning("Departure reminder failed for one user")
            await kv.delete(key)
    await session.commit()
    return sent
