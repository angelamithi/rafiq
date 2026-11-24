"""Database tables. Personal fields are encrypted (suffix _enc); identities
are stored only as keyed hashes."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text
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
    # "Do it for me": details the user gave for tasks (employer, salary, trusted contact, rate alert).
    toolkit: Mapped["Toolkit | None"] = relationship(
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


class Toolkit(Base):
    """"Do it for me" tasks. Everything personal is in one encrypted JSON blob
    (employer, salary, job start, trusted contact, rate alert, a form being
    filled). Two plain columns exist only so background jobs can find rows:
    `contact_hash` (keyed hash of the trusted contact, so they can remove
    themselves) and `rate_on` (an exchange-rate alert is waiting)."""

    __tablename__ = "toolkits"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data_enc: Mapped[str | None] = mapped_column(Text)
    contact_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    rate_on: Mapped[int] = mapped_column(Integer, default=0, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="toolkit")


class VaultDoc(Base):
    """Document vault: the user's own copies of their passport, visa, Emirates ID,
    contract... The file and its expiry date are encrypted. Not loaded with the
    user (files can be large): queried only when the vault is opened."""

    __tablename__ = "vault_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))                 # passport | visa | eid | contract | offer | other
    expiry_enc: Mapped[str | None] = mapped_column(Text)          # ISO date, encrypted
    file_enc: Mapped[bytes] = mapped_column(LargeBinary)          # Fernet-encrypted file bytes
    mime: Mapped[str] = mapped_column(String(40))
    size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Case(Base):
    """Dispute case manager and incident records. Everything the worker wrote
    (notes, reference number, outcome) is in one encrypted JSON blob. Plain
    columns only say what kind of case it is, where it stands and when to
    follow up, so the reminder job can find it."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))          # wages | passport | contract | safety | other
    status: Mapped[str] = mapped_column(String(16), default="open")   # open | filed | resolved | closed
    data_enc: Mapped[str | None] = mapped_column(Text)
    next_check: Mapped[date | None] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserReminder(Base):
    """Reminders the user asked for (rent day, a doctor's appointment, a job
    interview, a savings check-in). The wording is encrypted; only the kind and
    the date are plain so the daily job can find what's due."""

    __tablename__ = "user_reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))           # rent | appointment | interview | savings
    due: Mapped[date] = mapped_column(Date, index=True)
    text_enc: Mapped[str | None] = mapped_column(Text)
    repeat_monthly: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
