"""Module 6: Pay & Rights."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db import repo
from app.db.models import AuditLog, PayRecord, User, utcnow
from app.db.session import sessionmaker
from app.modules.pay import node as paynode
from app.modules.pay.checkins import send_due_checkins
from app.security.output_guard import check_output
from app.security.ratelimit import MemoryKV
from app.security.tool_policy import TOOLS, ToolNotAllowed, authorize
from tests.conftest import TODAY, Chat


async def onboard_worker(c: Chat, *, sector: str = "construction", name: str = "Ravi") -> None:
    await c.say("hi")
    await c.tap("consent:yes")
    await c.say(name)
    await c.tap("stage:resident")
    await c.tap("country:India")
    await c.tap("visa:employment")
    await c.tap("expiry:skip")
    await c.tap(f"sector:{sector}")
    await c.tap("summary:ok")


async def db_user(c: Chat) -> User:
    async with sessionmaker()() as s:
        return (await s.execute(select(User).where(User.identity_hash == repo.hash_identity(c.channel, c.phone)))).scalar_one()


def rows(out) -> list:
    return out.menu.rows if out.menu else []


# ------------------------------------------------------------------ menu & screens


async def test_menu_and_typed_commands(chat: Chat):
    await onboard_worker(chat)
    r = await chat.say("menu")
    assert "menu:pay" in chat.ids_of(r)
    r = await chat.tap("menu:pay")
    assert [row.id for row in rows(r[0])] == [f"pay:{k}" for k in paynode.MENU]
    for typed, expect in (("my rights", "Pay & rights"), ("salary late", "1 June 2026"), ("complaint", "What is the problem"),
                          ("gratuity", "21 days"), ("overtime", "25%"), ("salary watch", "Salary watch")):
        r = await chat.say(typed)
        assert expect in r[0].text, typed


async def test_all_screens_fit_and_pass_output_guard(chat: Chat):
    await onboard_worker(chat)
    user = await db_user(chat)
    repo.set_pay_status(user, "2026-10", "unpaid")
    for sector in ("construction", "domestic"):
        user.sector = sector
        outs = [paynode.pay_menu("en"), paynode.watch_screen(user, TODAY, "en"), paynode.late_message(user, "en"),
                paynode.how_message("en"), paynode.complaint_menu("en"), paynode.rights_message(user, "en"),
                paynode.proof_message("en")]
        for p in paynode.PROBLEMS:
            outs += paynode.complaint_draft(user, p, "en")
        for out in outs:
            chk = check_output(out.text, user_own_values={"Ravi"})
            assert not chk.blocked and not chk.reasons, (out.text[:40], chk.reasons)
            assert len(out.text) <= 1024 and len(out.buttons) <= 3
            assert all(len(b.title) <= 20 for b in out.buttons)
            for row in rows(out):
                assert len(row.title) <= 24 and len(row.description or "") <= 72, row.title


# ------------------------------------------------------------------ salary watch


def test_pay_month_is_last_month():
    assert paynode.pay_month(date(2026, 11, 19)) == "2026-10"
    assert paynode.pay_month(date(2027, 1, 3)) == "2026-12"


async def test_salary_watch_record_and_toggle(chat: Chat):
    await onboard_worker(chat)
    r = await chat.tap("pay:watch")
    assert "Check-ins are *off*" in r[0].text and "the 3rd" in r[0].text and "October 2026" in r[0].text
    assert "pay:on" in chat.ids_of(r)
    r = await chat.tap("pay:on")
    assert "Check-ins are *on*" in r[0].text and "pay:off" in chat.ids_of(r)
    r = await chat.say("PAID")
    assert "October 2026* salary was paid in full" in r[0].text and "October 2026: paid" in r[0].text
    r = await chat.say("not paid")
    assert "has not been paid" in r[0].text and "1 June 2026" in r[1].text
    assert "pay:complaint" in chat.ids_of(r)
    user = await db_user(chat)
    assert repo.pay_log(user) == {"2026-10": "unpaid"} and repo.pay_watch_on(user)


async def test_part_payment_explains_85_percent(chat: Chat):
    await onboard_worker(chat)
    r = await chat.tap("pay:part")
    assert "only part" in r[0].text and "85%" in r[1].text


async def test_domestic_worker_gets_their_own_rules(kv):
    c = Chat(kv, phone="919800000001")
    await onboard_worker(c, sector="domestic")
    r = await c.tap("pay:watch")
    assert "within *10 days*" in r[0].text and "the 11th" in r[0].text
    r = await c.say("salary late")
    assert "10 days" in r[0].text and "1 June 2026" not in r[0].text
    r = await c.say("days off")
    assert "12 hours" in r[0].text and "ticket every 2 years" in r[0].text
    r = await c.say("gratuity")
    assert "own end-of-service rules" in r[0].text


async def test_salary_record_is_encrypted_and_minimal(chat: Chat):
    await onboard_worker(chat)
    await chat.say("not paid")
    async with sessionmaker()() as s:
        rec = (await s.execute(select(PayRecord))).scalar_one()
    assert rec.log_enc and "unpaid" not in rec.log_enc and "2026" not in rec.log_enc


def test_bad_salary_record_values_rejected():
    u = User(channel="whatsapp", identity_hash="x")
    u.pay = None
    for month, status in (("2026-13", "paid"), ("26-10", "paid"), ("2026-10", "maybe"), ("2026-10; drop", "paid")):
        with pytest.raises(ValueError):
            repo.set_pay_status(u, month, status)


async def test_record_keeps_last_12_months(chat: Chat):
    await onboard_worker(chat)
    user = await db_user(chat)
    for i in range(15):
        d = date(2025, 1, 1) + timedelta(days=31 * i)
        repo.set_pay_status(user, f"{d.year}-{d.month:02d}", "paid")
    assert len(repo.pay_log(user)) == 12


# ------------------------------------------------------------------ complaints


async def test_complaint_draft_uses_own_record_and_placeholders(chat: Chat):
    await onboard_worker(chat, name="Ravi Kumar")
    user = await db_user(chat)
    await chat.say("not paid")                                 # October unpaid
    r = await chat.tap("pay:c:unpaid")
    head, body, tail = r[0].text, r[1].text, r[2].text
    assert "[brackets]" in head
    assert "Name: Ravi Kumar" in body and "October 2026" in body and "[your number]" in body
    assert "Employer: [company or employer name]" in body
    assert "don't send anything for you" in tail and "pay:how" in chat.ids_of(r)
    async with sessionmaker()() as s:
        events = list((await s.execute(select(AuditLog.event, AuditLog.detail))).all())
    assert ("complaint_drafted", "unpaid") in events
    assert not any("Ravi" in (d or "") for _, d in events)         # nothing personal in the audit log
    assert user is not None


async def test_every_complaint_type_has_a_draft(chat: Chat):
    await onboard_worker(chat, name="")
    user = await db_user(chat)
    for p in paynode.PROBLEMS:
        msgs = paynode.complaint_draft(user, p, "en")
        assert "Labour complaint" in msgs[1].text and "I request:" in msgs[1].text
        assert "[your full name" in msgs[1].text or "Name:" in msgs[1].text


async def test_forged_complaint_ids_fall_back_to_menu(chat: Chat):
    await onboard_worker(chat)
    for bad in ("pay:c:other_users", "pay:c:", "pay:c:../../etc", "pay:delete"):
        r = await chat.tap(bad)
        assert "Pay & rights" in r[0].text


def test_rafiq_has_no_outward_tool_for_complaints():
    assert not TOOLS["draft_complaint"].outward and not TOOLS["draft_complaint"].destructive
    # The ONLY outward tool is the SOS to the user's own opted-in trusted contact, and only the tasks node has it.
    assert {name for name, spec in TOOLS.items() if spec.outward} == {"send_sos"}
    with pytest.raises(ToolNotAllowed):
        authorize("pay", "send_sos")
    with pytest.raises(ToolNotAllowed):
        authorize("tasks", "send_sos")          # never without a confirmation nonce
    authorize("pay", "draft_complaint")
    for tool in ("delete_own_data", "update_own_plan", "check_job_offer", "update_own_profile"):
        with pytest.raises(ToolNotAllowed):
            authorize("pay", tool)


# ------------------------------------------------------------------ gratuity


@pytest.mark.parametrize(
    "typed,expect",
    [
        ("2000 3", "AED 4,200"),             # 2000/30*63
        ("AED 3,000 for 7 years", "AED 16,500"),  # 100*(105+60)
        ("1500 30", "AED 36,000"),           # capped at 24 months
        ("2000 0.5", "none yet"),
    ],
)
async def test_gratuity_calculator(chat: Chat, typed, expect):
    await onboard_worker(chat)
    await chat.tap("pay:gratuity")
    r = await chat.say(typed)
    assert expect in r[0].text


async def test_gratuity_bad_input_reprompts_and_escape(chat: Chat):
    await onboard_worker(chat)
    await chat.tap("pay:gratuity")
    r = await chat.say("a lot")
    assert "for example" in r[0].text
    r = await chat.say("50 2")                                 # salary too small to be real
    assert "for example" in r[0].text
    r = await chat.say("menu")                                 # global command escapes
    assert "menu:pay" in chat.ids_of(r)
    r = await chat.say("2000 3")                               # no longer waiting: not a calculation
    assert "AED 4,200" not in r[0].text


# ------------------------------------------------------------------ privacy


async def test_export_and_delete_cover_salary_record(chat: Chat):
    await onboard_worker(chat)
    await chat.tap("pay:on")
    await chat.say("paid")
    r = await chat.say("my data")
    assert "Salary check-ins: On" in r[0].text and "Salary record: 2026-10: paid" in r[0].text
    r = await chat.say("delete")
    await chat.tap(next(i for i in chat.ids_of(r) if i.startswith("delete:yes:")))
    async with sessionmaker()() as s:
        assert (await s.execute(select(PayRecord))).first() is None


async def test_retention_cleanup_removes_salary_records(chat: Chat):
    from app import worker

    await onboard_worker(chat)
    await chat.say("paid")
    async with sessionmaker()() as s:
        u = (await s.execute(select(User))).scalar_one()
        u.last_seen_at = utcnow() - timedelta(days=800)
        await s.commit()
    await worker.cleanup({})
    async with sessionmaker()() as s:
        assert (await s.execute(select(PayRecord))).first() is None


# ------------------------------------------------------------------ check-ins


async def _watcher(kv, phone: str, *, sector: str = "construction", on: bool = True, status: str | None = None,
                   paused: bool = False) -> None:
    c = Chat(kv, phone=phone)
    await onboard_worker(c, sector=sector)
    if on:
        await c.tap("pay:on")
    if status:
        await c.tap(f"pay:{status}")
    if paused:
        await c.say("stop")


async def test_checkins_on_the_right_days_once(kv):
    await _watcher(kv, "919800000101")                       # private, no answer yet
    await _watcher(kv, "919800000102", status="paid")        # already paid: no follow-up
    await _watcher(kv, "919800000103", status="unpaid")      # unpaid: follow-up
    await _watcher(kv, "919800000104", on=False)             # check-ins off
    await _watcher(kv, "919800000105", paused=True)          # typed stop
    await _watcher(kv, "919800000106", sector="domestic")    # different days
    sent = []

    async def send(r):
        sent.append(r)
        return True

    rkv = MemoryKV()
    nov3, nov10, nov11 = date(2026, 11, 3), date(2026, 11, 10), date(2026, 11, 11)
    async with sessionmaker()() as s:
        assert await send_due_checkins(s, rkv, send, nov3) == 2          # 101 and 103 (not marked paid)
    assert {r.to for r in sent} == {"919800000101", "919800000103"}
    assert "October 2026" in sent[0].text and sent[0].kind == "pay"
    async with sessionmaker()() as s:
        assert await send_due_checkins(s, rkv, send, nov3) == 0          # no duplicates
        assert await send_due_checkins(s, rkv, send, nov10) == 2         # follow-ups: 101 and 103
        assert await send_due_checkins(s, rkv, send, nov11) == 1         # domestic worker's day
    assert "has your salary" in sent[2].text
    assert sent[-1].to == "919800000106"


async def test_whatsapp_checkin_uses_its_own_template(monkeypatch):
    from app import worker
    from app.config import get_settings
    from app.modules.stay_legal.visa import Reminder

    calls = []

    async def fake_template(client, to, name, language, params):
        calls.append(name)

    monkeypatch.setattr(worker, "send_template", fake_template)
    monkeypatch.setattr(worker, "_client", lambda ch: object())
    monkeypatch.setenv("WHATSAPP_PAY_TEMPLATE", "rafiq_salary_check")
    get_settings.cache_clear()
    r = Reminder("u1", "whatsapp", "919800000001", 3, "text", ["Ravi", "October 2026"], kind="pay")
    assert await worker.send_reminder(r) is True and calls == ["rafiq_salary_check"]
    get_settings.cache_clear()
