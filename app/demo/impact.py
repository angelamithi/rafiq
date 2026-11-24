"""Anonymised impact numbers, counted from the audit log (which never holds
message text or personal data). Only totals are shown; nothing per person."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from app.db.models import AuditLog, User, utcnow

METRICS: tuple[tuple[str, str, str, str | None], ...] = (
    # (key, label, event, detail LIKE filter)
    ("offers", "Job offers checked", "offer_checked", None),
    ("offers_high", "High-risk offers flagged", "offer_checked", "risk=high%"),
    ("contracts_worse", "Contracts worse than the offer", "contract_checked", "worse"),
    ("gaps", "Salary gaps found", "salary_gap_found", None),
    ("packs", "Evidence packs built", "task_pack_built", None),
    ("letters", "Letters prepared", "task_letter_built", None),
    ("cases", "Cases opened", "case_opened", None),
    ("filed", "Complaints filed (reported by workers)", "case_filed", None),
    ("resolved", "Cases resolved (reported by workers)", "case_resolved", None),
    ("warnings", "Exploitation warnings raised", "protection_warning", None),
    ("records", "Incident records started", "incident_record_started", None),
    ("contacts", "Trusted contacts linked", "sos_contact_joined", None),
    ("sos", "SOS alerts sent", "sos_sent", None),
    ("docs", "Documents saved", "vault_saved", None),
)


async def compute(session: Any, days: int | None = None) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days) if days else None

    async def count(event: str, like: str | None) -> int:
        q = select(func.count()).select_from(AuditLog).where(AuditLog.event == event)
        if like:
            q = q.where(AuditLog.detail.like(like))
        if since:
            q = q.where(AuditLog.created_at >= since)
        return int((await session.execute(q)).scalar() or 0)

    users_q = select(User.channel, func.count()).where(User.consent_status == "granted").group_by(User.channel)
    by_channel = {c: int(n) for c, n in (await session.execute(users_q)).all()}
    agent_q = select(AuditLog.detail, func.count()).where(AuditLog.event == "handled_by")
    if since:
        agent_q = agent_q.where(AuditLog.created_at >= since)
    agents = {d or "?": int(n) for d, n in (await session.execute(agent_q.group_by(AuditLog.detail))).all()}
    return {
        "workers": sum(n for c, n in by_channel.items() if c != "web"),
        "demo_sessions": by_channel.get("web", 0),
        "metrics": [{"key": k, "label": label, "value": await count(ev, like)} for k, label, ev, like in METRICS],
        "agents": dict(sorted(agents.items(), key=lambda kv: -kv[1])),
        "window_days": days,
    }
