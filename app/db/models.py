"""Database tables. Personal fields are encrypted (suffix _enc); identities
are stored only as keyed hashes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    channel: Mapped[str] = mapped_column(String(16))                       # whatsapp | telegram
    identity_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    address_enc: Mapped[str | None] = mapped_column(Text)                  # encrypted phone / chat id

    language: Mapped[str | None] = mapped_column(String(8))                # en | sw
    consent_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|granted|declined
    consent_version: Mapped[str | None] = mapped_column(String(32))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # conversation position (Module 1 flow)
    step: Mapped[str] = mapped_column(String(32), default="new")
    return_to: Mapped[str | None] = mapped_column(String(32))              # where to go after editing a field
    pending_action: Mapped[str | None] = mapped_column(String(64))         # e.g. "delete:<nonce>"

    # profile
    display_name_enc: Mapped[str | None] = mapped_column(Text)
    journey_stage: Mapped[str | None] = mapped_column(String(24))          # planning|offer|arrived|resident
    home_country: Mapped[str | None] = mapped_column(String(64))
    visa_type: Mapped[str | None] = mapped_column(String(24))
    visa_expiry_enc: Mapped[str | None] = mapped_column(Text)              # ISO date, encrypted
    sector: Mapped[str | None] = mapped_column(String(24))
    notifications_paused: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Module 4: one optional departure checklist per user (loaded with the user).
    plan: Mapped["DeparturePlan | None"] = relationship(
        back_populates="user", uselist=False, lazy="selectin", cascade="all, delete-orphan", passive_deletes=True,
    )
    # Module 6: salary watch (opt-in monthly check-in + encrypted record).
    pay: Mapped["PayRecord | None"] = relationship(
        back_populates="user", uselist=False, lazy="selectin", cascade="all, delete-orphan", passive_deletes=True,
    )
    # Module 7: wellbeing check-in preference (answers are never stored).
    social: Mapped["SocialPrefs | None"] = relationship(
        back_populates="user", uselist=False, lazy="selectin", cascade="all, delete-orphan", passive_deletes=True,
    )
    # Module 5: one optional arrival checklist per user.
    arrival: Mapped["ArrivalPlan | None"] = relationship(
        back_populates="user", uselist=False, lazy="selectin", cascade="all, delete-orphan", passive_deletes=True,
    )


class DeparturePlan(Base):
    """Module 4 (Departure Planner). Its own table, so adding it needs no
    change to the users table. The travel date is encrypted; `done` holds only
    checklist item keys (e.g. "passport,medicines"), never free text."""

    __tablename__ = "departure_plans"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    travel_date_enc: Mapped[str | None] = mapped_column(Text)
    done: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="plan")


class ArrivalPlan(Base):
    """Module 5 (Arrival Guide). Same shape as DeparturePlan: an encrypted
    arrival date and the keys of ticked items."""

    __tablename__ = "arrival_plans"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    arrival_date_enc: Mapped[str | None] = mapped_column(Text)
    done: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="arrival")


class PayRecord(Base):
    """Module 6 (Pay & Rights). Whether monthly salary check-ins are on, and an
    encrypted record of "paid / part / unpaid" per month (no amounts)."""

    __tablename__ = "pay_records"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    watch: Mapped[int] = mapped_column(Integer, default=0)
    log_enc: Mapped[str | None] = mapped_column(Text)        # encrypted JSON {"2026-10": "paid", ...}
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="pay")


class SocialPrefs(Base):
    """Module 7 (Friends & wellbeing). Only whether weekly check-ins are on.
    How someone feels is never stored."""

    __tablename__ = "social_prefs"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    checkin: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="social")


class SourceCheck(Base):
    """Rule Monitor state for one fact in app/knowledge/registry.py. Holds only
    extracted numbers from public official pages, never page text."""

    __tablename__ = "source_checks"

    fact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    module: Mapped[str] = mapped_column(String(24), index=True)
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="new")       # new | ok | changed | unreachable
    detail: Mapped[str | None] = mapped_column(String(255))
    tokens: Mapped[str | None] = mapped_column(Text)                      # reviewed baseline (JSON list)
    pending_tokens: Mapped[str | None] = mapped_column(Text)              # latest, until a person reviews
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    """Security and privacy events. Never stores message text or personal data."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_ref: Mapped[str | None] = mapped_column(String(64), index=True)   # user id or identity hash
    event: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
