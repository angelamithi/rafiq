"""All data access goes through here. Every function is scoped to ONE user
object that was resolved from the verified webhook identity, so no code path
can read or change another user's data."""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import json
import re

from app.db.models import ArrivalPlan, AuditLog, DeparturePlan, PayRecord, SocialPrefs, User, utcnow
from app.security.crypto import decrypt, encrypt, hash_identity

EDITABLE_FIELDS = {"display_name", "journey_stage", "home_country", "visa_type", "visa_expiry", "sector", "language"}


async def get_or_create_user(s: AsyncSession, channel: str, external_id: str) -> tuple[User, bool]:
    h = hash_identity(channel, external_id)
    user = (await s.execute(select(User).where(User.identity_hash == h))).scalar_one_or_none()
    if user:
        user.last_seen_at = utcnow()
        return user, False
    user = User(channel=channel, identity_hash=h, address_enc=encrypt(external_id))
    user.plan = None     # initialise the relationships so they are never lazy-loaded
    user.arrival = None
    user.pay = None
    user.social = None
    s.add(user)
    await s.flush()
    return user, True


def get_display_name(u: User) -> str | None:
    return decrypt(u.display_name_enc)


def get_visa_expiry(u: User) -> date | None:
    raw = decrypt(u.visa_expiry_enc)
    return date.fromisoformat(raw) if raw else None


def set_field(u: User, field: str, value: object) -> None:
    if field not in EDITABLE_FIELDS:
        raise ValueError(f"Field {field!r} cannot be edited")
    if field == "display_name":
        u.display_name_enc = encrypt(value) if value else None
    elif field == "visa_expiry":
        u.visa_expiry_enc = encrypt(value.isoformat()) if isinstance(value, date) else None
    else:
        setattr(u, field, value)


# ---------------------------------------------------------------- Modules 4-5: checklists
# kind -> (relationship on User, table class, encrypted date column)
_CHECKLISTS = {
    "departure": ("plan", DeparturePlan, "travel_date_enc"),
    "arrival": ("arrival", ArrivalPlan, "arrival_date_enc"),
}
_ITEM_KEY = re.compile(r"^[a-z_]{1,16}$")


def _rel(u: User, kind: str):  # type: ignore[no-untyped-def]
    return getattr(u, _CHECKLISTS[kind][0])


def _plan(u: User, kind: str):  # type: ignore[no-untyped-def]
    rel, model, _col = _CHECKLISTS[kind]
    if getattr(u, rel) is None:
        setattr(u, rel, model(done=""))
    return getattr(u, rel)


def plan_done(u: User, kind: str = "departure") -> set[str]:
    p = _rel(u, kind)
    return {k for k in (p.done.split(",") if p and p.done else []) if k}


def get_plan_date(u: User, kind: str) -> date | None:
    p = _rel(u, kind)
    raw = decrypt(getattr(p, _CHECKLISTS[kind][2])) if p else None
    return date.fromisoformat(raw) if raw else None


def set_plan_item(u: User, key: str, done: bool, kind: str = "departure") -> None:
    """Tick or untick one checklist item. Keys are validated by the caller
    against the user's own items AND here against a strict pattern."""
    if not _ITEM_KEY.match(key):
        raise ValueError("Bad checklist key")
    items = plan_done(u, kind)
    (items.add if done else items.discard)(key)
    _plan(u, kind).done = ",".join(sorted(items))[:255]


def set_plan_date(u: User, kind: str, value: date | None) -> None:
    setattr(_plan(u, kind), _CHECKLISTS[kind][2], encrypt(value.isoformat()) if value else None)


def get_travel_date(u: User) -> date | None:
    return get_plan_date(u, "departure")


def set_travel_date(u: User, value: date | None) -> None:
    set_plan_date(u, "departure", value)


# ---------------------------------------------------------------- Module 6: salary record
PAY_STATUSES = {"paid", "part", "unpaid"}
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
PAY_KEEP_MONTHS = 12


def pay_log(u: User) -> dict[str, str]:
    raw = decrypt(u.pay.log_enc) if u.pay else None
    if not raw:
        return {}
    data = json.loads(raw)
    return {k: v for k, v in data.items() if _MONTH.match(k) and v in PAY_STATUSES}


def set_pay_status(u: User, month: str, status: str) -> None:
    if not _MONTH.match(month) or status not in PAY_STATUSES:
        raise ValueError("Bad salary record")
    log = pay_log(u)
    log[month] = status
    keep = dict(sorted(log.items())[-PAY_KEEP_MONTHS:])
    if u.pay is None:
        u.pay = PayRecord(watch=0)
    u.pay.log_enc = encrypt(json.dumps(keep))


def pay_watch_on(u: User) -> bool:
    return bool(u.pay and u.pay.watch)


def set_pay_watch(u: User, on: bool) -> None:
    if u.pay is None:
        u.pay = PayRecord(watch=0)
    u.pay.watch = 1 if on else 0


# ---------------------------------------------------------------- Module 7: wellbeing check-ins

def social_checkin_on(u: User) -> bool:
    return bool(u.social and u.social.checkin)


def set_social_checkin(u: User, on: bool) -> None:
    if u.social is None:
        u.social = SocialPrefs(checkin=0)
    u.social.checkin = 1 if on else 0


def export_data(u: User) -> dict[str, str | None]:
    expiry = get_visa_expiry(u)
    travel = get_travel_date(u)
    arrived = get_plan_date(u, "arrival")
    return {
        "name": get_display_name(u),
        "language": u.language,
        "journey_stage": u.journey_stage,
        "home_country": u.home_country,
        "visa_type": u.visa_type,
        "visa_expiry": expiry.isoformat() if expiry else None,
        "sector": u.sector,
        "consent": f"{u.consent_status} ({u.consent_version or '-'})",
        "joined": u.created_at.date().isoformat() if u.created_at else None,
        "travel_date": travel.isoformat() if travel else None,
        "checklist_done": ", ".join(sorted(plan_done(u))) or None,
        "arrival_date": arrived.isoformat() if arrived else None,
        "arrival_done": ", ".join(sorted(plan_done(u, "arrival"))) or None,
        "salary_watch": ("on" if pay_watch_on(u) else "off") if u.pay else None,
        "wellbeing_checkins": ("on" if social_checkin_on(u) else "off") if u.social else None,
        "salary_record": ", ".join(f"{m}: {st}" for m, st in sorted(pay_log(u).items())) or None,
    }


async def delete_user(s: AsyncSession, u: User) -> None:
    uid = u.id
    await s.execute(delete(DeparturePlan).where(DeparturePlan.user_id == uid))
    await s.execute(delete(ArrivalPlan).where(ArrivalPlan.user_id == uid))
    await s.execute(delete(PayRecord).where(PayRecord.user_id == uid))
    await s.execute(delete(SocialPrefs).where(SocialPrefs.user_id == uid))
    await s.execute(delete(User).where(User.id == uid))
    # Keep a minimal, anonymous record that a deletion happened (no personal data).
    s.add(AuditLog(user_ref=uid, event="data_deleted", detail="user requested deletion"))


async def audit(s: AsyncSession, user_ref: str | None, event: str, detail: str | None = None) -> None:
    s.add(AuditLog(user_ref=user_ref, event=event[:48], detail=(detail or "")[:255] or None))
