"""'Finish your residence visa' reminders, sent by the worker's daily cron.

Sent on day 21 and day 28 after arrival, only while the medical / Emirates ID
step is still open. Arrival dates are encrypted, so they're compared here in
memory, never in SQL. Each reminder is sent once (Redis key).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date, timedelta

from sqlalchemy import select

from app.db import repo
from app.db.models import ArrivalPlan, User
from app.i18n import fmt_date, t
from app.modules.arrival.checklist import KIND
from app.modules.arrival.content import REMINDER_DAYS_SINCE, RESIDENCY_DAYS
from app.modules.stay_legal.visa import Reminder
from app.security.crypto import decrypt
from app.security.ratelimit import KV

log = logging.getLogger(__name__)


async def due_arrival_reminders(session, today: date) -> list[Reminder]:  # type: ignore[no-untyped-def]
    users = (await session.execute(
        select(User).join(ArrivalPlan, ArrivalPlan.user_id == User.id).where(
            User.consent_status == "granted", User.notifications_paused == 0, ArrivalPlan.arrival_date_enc.is_not(None),
        )
    )).scalars().all()
    out: list[Reminder] = []
    for u in users:
        arrived = repo.get_plan_date(u, KIND)
        to = decrypt(u.address_enc)
        if not arrived or not to or u.visa_type == "visit" or "residency" in repo.plan_done(u, KIND):
            continue
        since = (today - arrived).days
        if since not in REMINDER_DAYS_SINCE:
            continue
        due = arrived + timedelta(days=RESIDENCY_DAYS)
        text = t("arr_reminder", u.language, n=since, due=fmt_date(due, u.language))
        name = repo.get_display_name(u) or "there"
        out.append(Reminder(u.id, u.channel, to, since, text,
                            [name, fmt_date(due, u.language), str(max((due - today).days, 0))], kind="arrival"))
    return out


Sender = Callable[[Reminder], Awaitable[bool]]


async def send_due_arrival_reminders(session, kv: KV, send: Sender, today: date) -> int:  # type: ignore[no-untyped-def]
    sent = 0
    for r in await due_arrival_reminders(session, today):
        key = f"arr_rem:{r.user_id}:{today.toordinal() - r.days}:{r.days}"
        if not await kv.set(key, "1", ex=40 * 86_400, nx=True):
            continue
        try:
            if await send(r):
                sent += 1
                await repo.audit(session, r.user_id, "arrival_reminder_sent", f"day={r.days}")
            else:
                await kv.delete(key)
        except Exception:
            log.warning("Arrival reminder failed for one user")
            await kv.delete(key)
    await session.commit()
    return sent
