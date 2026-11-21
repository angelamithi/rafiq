"""Opt-in weekly 'how was your week?' check-ins (Fridays), sent by the worker.

Only users who turned them on, agreed to the privacy notice and haven't typed
*stop*. One per ISO week (Redis key). Answers are never stored.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date

from sqlalchemy import select

from app.db import repo
from app.db.models import SocialPrefs, User
from app.i18n import t
from app.modules.social import content  # noqa: F401  (registers the text)
from app.modules.stay_legal.visa import Reminder
from app.security.crypto import decrypt
from app.security.ratelimit import KV

log = logging.getLogger(__name__)


async def due_checkins(session) -> list[Reminder]:  # type: ignore[no-untyped-def]
    users = (await session.execute(
        select(User).join(SocialPrefs, SocialPrefs.user_id == User.id).where(
            User.consent_status == "granted", User.notifications_paused == 0, SocialPrefs.checkin == 1,
        )
    )).scalars().all()
    out: list[Reminder] = []
    for u in users:
        to = decrypt(u.address_enc)
        if to:
            name = repo.get_display_name(u) or "there"
            out.append(Reminder(u.id, u.channel, to, 0, t("soc_checkin_msg", u.language), [name], kind="social"))
    return out


Sender = Callable[[Reminder], Awaitable[bool]]


async def send_due_checkins(session, kv: KV, send: Sender, today: date) -> int:  # type: ignore[no-untyped-def]
    year, week, _ = today.isocalendar()
    sent = 0
    for r in await due_checkins(session):
        key = f"soc_chk:{r.user_id}:{year}-W{week:02d}"
        if not await kv.set(key, "1", ex=10 * 86_400, nx=True):
            continue
        try:
            if await send(r):
                sent += 1
                await repo.audit(session, r.user_id, "wellbeing_checkin_sent")
            else:
                await kv.delete(key)
        except Exception:
            log.warning("Wellbeing check-in failed for one user")
            await kv.delete(key)
    await session.commit()
    return sent
