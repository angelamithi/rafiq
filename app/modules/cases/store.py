"""Storage for dispute cases and incident records (Employment + Protection agents).
Every lookup is filtered by the owner's user id."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select

from app.db.models import Case
from app.security.crypto import decrypt, encrypt

KINDS = ("wages", "passport", "contract", "safety", "housing", "other")
MAX_OPEN = 10
MAX_TIMELINE = 60
FIRST_FOLLOW_UP_DAYS = 7
FOLLOW_UP_EVERY_DAYS = 14
_ID = re.compile(r"[0-9a-f\-]{36}")


def data(case: Case) -> dict[str, Any]:
    raw = decrypt(case.data_enc)
    try:
        d = json.loads(raw) if raw else {}
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def save_data(case: Case, d: dict[str, Any]) -> None:
    d["timeline"] = (d.get("timeline") or [])[-MAX_TIMELINE:]
    case.data_enc = encrypt(json.dumps(d))


def add_event(case: Case, when: date, text: str) -> None:
    d = data(case)
    d.setdefault("timeline", []).append({"d": when.isoformat(), "e": text[:300]})
    save_data(case, d)


async def open_count(session: Any, user_id: str) -> int:
    q = select(func.count()).select_from(Case).where(Case.user_id == user_id, Case.status.in_(("open", "filed")))
    return int((await session.execute(q)).scalar() or 0)


async def create(session: Any, user_id: str, kind: str, today: date, first_event: str,
                 extra: dict[str, Any] | None = None) -> Case:
    case = Case(user_id=user_id, kind=kind if kind in KINDS else "other", status="open")
    save_data(case, {"opened": today.isoformat(), "timeline": [{"d": today.isoformat(), "e": first_event}], **(extra or {})})
    session.add(case)
    await session.flush()
    return case


async def get(session: Any, user_id: str, case_id: str) -> Case | None:
    if not _ID.fullmatch(case_id or ""):
        return None
    return (await session.execute(select(Case).where(Case.id == case_id, Case.user_id == user_id))).scalar_one_or_none()


async def list_for(session: Any, user_id: str) -> list[Case]:
    return list((await session.execute(
        select(Case).where(Case.user_id == user_id).order_by(Case.created_at.desc()).limit(20))).scalars())


async def find_open(session: Any, user_id: str, kind: str) -> Case | None:
    return (await session.execute(
        select(Case).where(Case.user_id == user_id, Case.kind == kind, Case.status.in_(("open", "filed")))
        .order_by(Case.created_at.desc()))).scalars().first()


def mark_filed(case: Case, today: date, ref: str | None) -> None:
    d = data(case)
    if ref:
        d["ref"] = ref
    d["filed"] = today.isoformat()
    d.setdefault("timeline", []).append({"d": today.isoformat(), "e": f"Complaint filed{f' (ref {ref})' if ref else ''}"})
    save_data(case, d)
    case.status = "filed"
    case.next_check = today + timedelta(days=FIRST_FOLLOW_UP_DAYS)


def mark_outcome(case: Case, today: date, outcome: str, recovered: int | None = None) -> None:
    d = data(case)
    d["outcome"] = outcome
    if recovered is not None:
        d["recovered"] = recovered
    d.setdefault("timeline", []).append({"d": today.isoformat(), "e": f"Outcome: {outcome}"
                                         + (f" (AED {recovered:,} recovered)" if recovered else "")})
    save_data(case, d)
    case.status = "resolved" if outcome in ("Paid in full", "Partly paid", "Passport returned", "Sorted out", "Repaired or refunded") else "closed"
    case.next_check = None


async def due_follow_ups(session: Any, today: date) -> list[Case]:
    return list((await session.execute(
        select(Case).where(Case.status == "filed", Case.next_check.is_not(None), Case.next_check <= today))).scalars())
