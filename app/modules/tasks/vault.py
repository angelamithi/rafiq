"""Document vault: encrypted copies of the user's own papers, with expiry reminders.

- Files are encrypted with the same key as other personal fields (Fernet).
- The AI only *transcribes* the page; the expiry date is picked from that text by
  rules below and the user confirms it before anything is saved.
- Only the owner can get a copy back: every lookup is filtered by their user id.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, func, select

from app.agent.parsing import parse_date
from app.db.models import User, VaultDoc
from app.i18n import fmt_date, t
from app.modules.tasks.content import VAULT_KINDS, VAULT_REMIND_DAYS
from app.security.crypto import _fernet, decrypt, encrypt

_EXPIRY_WORDS = re.compile(r"expir|valid\s*(until|till|thru|through|to)|date\s*of\s*exp|exp\.?\s*date|valid\s*up\s*to", re.I)
_DATE = re.compile(
    r"\b(\d{1,2}[-/. ]\d{1,2}[-/. ]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{2,4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})\b")


def _dates_in(text: str) -> list[date]:
    found = []
    for m in _DATE.finditer(text or ""):
        if d := parse_date(m.group(0).replace(".", " ") if re.search(r"[A-Za-z]", m.group(0)) else m.group(0)):
            found.append(d)
    return found


def find_expiry(text: str, today: date) -> date | None:
    """Best guess at a document's expiry date from its transcribed text.
    Prefers a date on a line that mentions expiry; otherwise the latest
    plausible date (expiry is usually the last date on an ID)."""
    lines = (text or "").splitlines()
    for i, line in enumerate(lines):
        if _EXPIRY_WORDS.search(line):
            near = _dates_in(line) or _dates_in(" ".join(lines[i + 1:i + 2]))
            near = [d for d in near if today - timedelta(days=3650) <= d <= today + timedelta(days=365 * 15)]
            if near:
                return max(near)
    plausible = [d for d in _dates_in(text) if today - timedelta(days=365) <= d <= today + timedelta(days=365 * 15)]
    return max(plausible) if plausible else None


def kind_label(kind: str, lang: str | None) -> str:
    return t(f"vault_k_{kind if kind in VAULT_KINDS else 'other'}", lang)


def encrypt_file(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_file(blob: bytes) -> bytes | None:
    try:
        return _fernet().decrypt(blob)
    except Exception:
        return None


async def count(session: Any, user_id: str) -> int:
    return int((await session.execute(select(func.count()).select_from(VaultDoc).where(VaultDoc.user_id == user_id))).scalar() or 0)


async def list_docs(session: Any, user_id: str) -> list[tuple[str, str, date | None]]:
    """(id, kind, expiry) for the user's documents, without loading the files."""
    rows = (await session.execute(
        select(VaultDoc.id, VaultDoc.kind, VaultDoc.expiry_enc).where(VaultDoc.user_id == user_id)
        .order_by(VaultDoc.created_at))).all()
    out = []
    for doc_id, kind, exp in rows:
        raw = decrypt(exp)
        out.append((doc_id, kind, date.fromisoformat(raw) if raw else None))
    return out


async def save(session: Any, user_id: str, kind: str, data: bytes, mime: str, expiry: date | None) -> str:
    doc = VaultDoc(user_id=user_id, kind=kind if kind in VAULT_KINDS else "other", mime=mime, size=len(data),
                   file_enc=encrypt_file(data), expiry_enc=encrypt(expiry.isoformat()) if expiry else None)
    session.add(doc)
    await session.flush()
    return doc.id


async def get(session: Any, user_id: str, doc_id: str) -> VaultDoc | None:
    if not re.fullmatch(r"[0-9a-f\-]{36}", doc_id or ""):
        return None
    return (await session.execute(
        select(VaultDoc).where(VaultDoc.id == doc_id, VaultDoc.user_id == user_id))).scalar_one_or_none()


async def remove(session: Any, user_id: str, doc_id: str) -> bool:
    if not re.fullmatch(r"[0-9a-f\-]{36}", doc_id or ""):
        return False
    res = await session.execute(delete(VaultDoc).where(VaultDoc.id == doc_id, VaultDoc.user_id == user_id))
    return bool(res.rowcount)


def filename_for(kind: str, mime: str) -> str:
    ext = {"application/pdf": "pdf", "image/png": "png", "image/webp": "webp"}.get(mime, "jpg")
    return f"rafiq-{kind}.{ext}"


# ---------------------------------------------------------------- reminders

async def send_due_vault_reminders(session: Any, kv: Any, send: Any, today: date) -> int:
    from app.modules.stay_legal.visa import Reminder

    sent = 0
    rows = (await session.execute(
        select(VaultDoc.id, VaultDoc.kind, VaultDoc.expiry_enc, User)
        .join(User, User.id == VaultDoc.user_id)
        .where(VaultDoc.expiry_enc.is_not(None), User.consent_status == "granted",
               User.notifications_paused == 0))).all()
    for doc_id, kind, exp, user in rows:
        raw = decrypt(exp)
        if not raw:
            continue
        expiry = date.fromisoformat(raw)
        days = (expiry - today).days
        if days not in VAULT_REMIND_DAYS:
            continue
        if not await kv.set(f"vault_rem:{doc_id}:{days}", "1", ex=60 * 60 * 24 * 120, nx=True):
            continue
        to = decrypt(user.address_enc)
        if not to:
            continue
        lang = user.language
        label = kind_label(kind, lang)
        key = "vault_reminder_soon" if days <= 7 else "vault_reminder"
        r = Reminder(user_id=user.id, channel=user.channel, to=to, days=days,
                     text=t(key, lang, kind=label, date=fmt_date(expiry, lang), days=days),
                     template_params=[label, fmt_date(expiry, lang), str(days)], kind="vault")
        try:
            if await send(r):
                sent += 1
        except Exception:
            await kv.delete(f"vault_rem:{doc_id}:{days}")
    return sent
