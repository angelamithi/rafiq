"""Monthly 'did you get your salary?' check-ins (opt-in), sent by the worker's cron.

Private sector: on the 3rd, then again on the 10th and 17th while the month
isn't recorded as paid. Domestic workers: the 11th and 18th. Respects *stop*.
Each check-in is sent once (Redis key per user / month / day).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date

from sqlalchemy import select

from app.db import repo
from app.db.models import PayRecord, User
from app.i18n import t
from app.modules.pay.content import CHECKIN_DAYS
from app.modules.pay.node import is_domestic, month_label, pay_month
from app.modules.stay_legal.visa import Reminder
from app.security.crypto import decrypt
from app.security.ratelimit import KV

log = logging.getLogger(__name__)


async def due_checkins(session, today: date) -> list[Reminder]:  # type: ignore[no-untyped-def]
    users = (await session.execute(
        select(User).join(PayRecord, PayRecord.user_id == User.id).where(
            User.consent_status == "granted", User.notifications_paused == 0, PayRecord.watch == 1,
        )
    )).scalars().all()
    month = pay_month(today)
    out: list[Reminder] = []
    for u in users:
        days = CHECKIN_DAYS["domestic" if is_domestic(u) else "private"]
        if today.day not in days or repo.pay_log(u).get(month) == "paid":
            continue
        to = decrypt(u.address_enc)
        if not to:
            continue
        label = month_label(month, u.language)
        key = "pay_checkin" if today.day == days[0] else "pay_checkin_again"
        name = repo.get_display_name(u) or "there"
        out.append(Reminder(u.id, u.channel, to, today.day, t(key, u.language, month=label), [name, label], kind="pay"))
    return out


Sender = Callable[[Reminder], Awaitable[bool]]


async def send_due_checkins(session, kv: KV, send: Sender, today: date) -> int:  # type: ignore[no-untyped-def]
    sent = 0
    for r in await due_checkins(session, today):
        key = f"pay_chk:{r.user_id}:{pay_month(today)}:{r.days}"
        if not await kv.set(key, "1", ex=40 * 86_400, nx=True):
            continue
        try:
            if await send(r):
                sent += 1
                await repo.audit(session, r.user_id, "salary_checkin_sent", f"day={r.days}")
            else:
                await kv.delete(key)
        except Exception:
            log.warning("Salary check-in failed for one user")
            await kv.delete(key)
    await session.commit()
    return sent
