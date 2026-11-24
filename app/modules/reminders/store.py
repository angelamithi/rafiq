"""Reminders the user asked for, shared by the Career, Housing, Health and
Financial agents. Each lookup is filtered by the owner's id."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, func, select

from app.db.models import User, UserReminder
from app.security.crypto import decrypt, encrypt

MAX_PER_USER = 20


def add_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    return date(y, m, 28)


async def count(session: Any, user_id: str) -> int:
    q = select(func.count()).select_from(UserReminder).where(UserReminder.user_id == user_id)
    return int((await session.execute(q)).scalar() or 0)


async def add(session: Any, user_id: str, kind: str, due: date, text: str, monthly: bool = False) -> UserReminder | None:
    if await count(session, user_id) >= MAX_PER_USER:
        return None
    r = UserReminder(user_id=user_id, kind=kind, due=due, text_enc=encrypt(text[:300]), repeat_monthly=1 if monthly else 0)
    session.add(r)
    await session.flush()
    return r


async def replace_kind(session: Any, user_id: str, kind: str) -> None:
    await session.execute(delete(UserReminder).where(UserReminder.user_id == user_id, UserReminder.kind == kind))


async def upcoming(session: Any, user_id: str, today: date, kinds: tuple[str, ...] | None = None) -> list[tuple[str, date, str]]:
    q = select(UserReminder).where(UserReminder.user_id == user_id, UserReminder.due >= today).order_by(UserReminder.due)
    if kinds:
        q = q.where(UserReminder.kind.in_(kinds))
    return [(r.kind, r.due, decrypt(r.text_enc) or "") for r in (await session.execute(q)).scalars()]


async def send_due(session: Any, send: Any, today: date) -> int:
    from app.modules.stay_legal.visa import Reminder

    sent = 0
    rows = (await session.execute(select(UserReminder, User).join(User, User.id == UserReminder.user_id)
                                  .where(UserReminder.due <= today))).all()
    for rem, user in rows:
        to = decrypt(user.address_enc)
        ok = False
        if to and user.consent_status == "granted" and not user.notifications_paused and rem.due >= today - timedelta(days=3):
            text = decrypt(rem.text_enc) or ""
            try:
                ok = bool(await send(Reminder(user_id=user.id, channel=user.channel, to=to, days=0, kind="reminder",
                                              text=f"⏰ {text}", template_params=[text[:200]])))
            except Exception:
                ok = False
            sent += int(ok)
        if rem.repeat_monthly:
            rem.due = add_month(rem.due)
        else:
            await session.delete(rem)
    await session.commit()
    return sent
