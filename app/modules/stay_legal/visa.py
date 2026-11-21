"""My visa: status view and expiry reminders."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from app.channels.base import Button, Outgoing
from app.db import repo
from app.db.models import User
from app.i18n import VISAS, fmt_date, t
from app.modules.stay_legal.content import GDRFA, ICP_SMART, OVERSTAY_FINE_PER_DAY, REMINDER_DAYS
from app.security.crypto import decrypt
from app.security.ratelimit import KV

log = logging.getLogger(__name__)


def _visa_word(user: User, lang: str | None) -> str:
    return VISAS[user.visa_type]["en"].lower().replace(" / ", " or ") if user.visa_type in VISAS else "visa"


def visa_status(user: User, today: date, lang: str | None) -> Outgoing:
    expiry = repo.get_visa_expiry(user)
    if not expiry:
        return Outgoing(
            text=t("visa_none", lang),
            buttons=[Button(id="legal:visa_set", title=t("btn_visa_set", lang)),
                     Button(id="legal:visa_check", title=t("btn_visa_check", lang)),
                     Button(id="menu:legal", title=t("btn_legal_menu", lang))],
        )
    days = (expiry - today).days
    kw = {"visa": _visa_word(user, lang), "date": fmt_date(expiry, lang), "days": abs(days)}
    if days < 0:
        head = t("visa_expired", lang, per_day=OVERSTAY_FINE_PER_DAY, owed=f"{abs(days) * OVERSTAY_FINE_PER_DAY:,}", **kw)
    elif days == 0:
        head = t("visa_today", lang, **kw)
    elif days <= 7:
        head = t("visa_urgent", lang, **kw)
    elif days <= 30:
        head = t("visa_soon", lang, **kw)
    else:
        head = t("visa_ok", lang, **kw)
    parts = [f"🛂 *My visa*\n\n{head}"]
    if days >= 0:
        parts.append(t("visa_reminders_off", lang) if user.notifications_paused else t("visa_reminders_on", lang))
    parts.append(t("legal_footer", lang))
    return Outgoing(
        text="\n\n".join(parts),
        buttons=[Button(id="legal:visa_check", title=t("btn_visa_check", lang)),
                 Button(id="legal:visa_set", title=t("btn_visa_update", lang)),
                 Button(id="menu:legal", title=t("btn_legal_menu", lang))],
    )


def visa_check_message(lang: str | None) -> Outgoing:
    return Outgoing(
        text=t("visa_check", lang, gdrfa=GDRFA, icp=ICP_SMART),
        buttons=[Button(id="legal:visa", title=t("legal_visa", lang)), Button(id="menu:legal", title=t("btn_legal_menu", lang))],
    )


# ---------------------------------------------------------------- reminders

@dataclass
class Reminder:
    user_id: str
    channel: str
    to: str
    days: int
    text: str
    template_params: list[str]
    kind: str = "visa"   # visa | departure (picks the WhatsApp template)


def reminder_text(days: int, expiry: date, lang: str | None) -> str:
    kw = {"date": fmt_date(expiry, lang), "days": days, "per_day": OVERSTAY_FINE_PER_DAY}
    if days < 0:
        return t("visa_reminder_expired", lang, **kw)
    if days == 0:
        return t("visa_reminder_today", lang, **kw)
    return t("visa_reminder_msg", lang, **kw)


async def due_reminders(session, today: date) -> list[Reminder]:  # type: ignore[no-untyped-def]
    """Users whose visa expiry is exactly a reminder day away. Expiry dates are
    encrypted, so they're checked here in memory, never queried in SQL."""
    users = (await session.execute(
        select(User).where(User.consent_status == "granted", User.notifications_paused == 0, User.visa_expiry_enc.is_not(None))
    )).scalars().all()
    out: list[Reminder] = []
    for u in users:
        expiry = repo.get_visa_expiry(u)
        to = decrypt(u.address_enc)
        if not expiry or not to:
            continue
        days = (expiry - today).days
        if days in REMINDER_DAYS:
            name = repo.get_display_name(u) or "there"
            out.append(Reminder(u.id, u.channel, to, days, reminder_text(days, expiry, u.language),
                                [name, fmt_date(expiry, u.language), str(max(days, 0))]))
    return out


Sender = Callable[[Reminder], Awaitable[bool]]


async def send_due_reminders(session, kv: KV, send: Sender, today: date) -> int:  # type: ignore[no-untyped-def]
    """Send each reminder once (Redis key per user/expiry/day). Returns count sent."""
    sent = 0
    for r in await due_reminders(session, today):
        key = f"visa_rem:{r.user_id}:{today.isoformat()}:{r.days}"
        if not await kv.set(key, "1", ex=40 * 86_400, nx=True):
            continue
        try:
            if await send(r):
                sent += 1
                await repo.audit(session, r.user_id, "visa_reminder_sent", f"days={r.days}")
            else:
                await kv.delete(key)
        except Exception:
            log.warning("Visa reminder failed for one user")
            await kv.delete(key)
    await session.commit()
    return sent
