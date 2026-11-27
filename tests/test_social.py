"""Module 7: Friends & wellbeing, and the crisis safety net."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db import repo
from app.db.models import AuditLog, SocialPrefs, User, utcnow
from app.db.session import sessionmaker
from app.modules.social import node as soc
from app.modules.social.checkins import send_due_checkins
from app.modules.social.content import current_events
from app.security.injection import scan
from app.security.output_guard import check_output
from app.security.ratelimit import MemoryKV
from app.security.tool_policy import ToolNotAllowed, authorize
from tests.conftest import TODAY, Chat, onboard


def rows(out) -> list:
    return out.menu.rows if out.menu else []


async def events_logged() -> list[tuple[str, str | None]]:
    async with sessionmaker()() as s:
        return list((await s.execute(select(AuditLog.event, AuditLog.detail))).all())


# ------------------------------------------------------------------ crisis safety net


@pytest.mark.parametrize(
    "text",
    [
        "I want to kill myself",
        "i dont want to live anymore",
        "I don’t want to live like this",          # curly apostrophe
        "thinking about suicide",
        "Sometimes I want to END MY LIFE",
        "I keep wanting to hurt myself",
        "everyone would be better off dead without me",
    ],
)
def test_crisis_phrases_detected(text):
    assert soc.crisis_intent(text)
    assert scan(text).verdict != "block"           # never blocked as an "attack" before support is shown


@pytest.mark.parametrize("text", ["I'm dead tired after work", "how to kill time on my day off", "this heat is killing me",
                                  "my phone died", "check job offer", "hello"])
def test_ordinary_messages_are_not_crises(text):
    assert not soc.crisis_intent(text)


async def test_crisis_support_from_ready_state(chat: Chat):
    await onboard(chat)
    r = await chat.say("I want to kill myself")
    assert "999" in r[0].text and "800 4673" in r[0].text and "800 725462" in r[0].text
    assert "[PHONE]" not in r[0].text and "[LONG_NUMBER]" not in r[0].text
    assert ("crisis_support_shown", None) in await events_logged()        # no message text stored


async def test_crisis_support_before_consent(chat: Chat):
    r = await chat.say("i want to end my life")      # very first message
    assert "999" in r[0].text and "800 4673" in r[0].text
    r = await chat.say("hi")                          # setup still works afterwards
    assert "privacy" in r[0].text.lower()


@pytest.mark.parametrize("step_button", ["plan:date", "legal:med", "menu:job", "arrive:date", "pay:gratuity"])
async def test_crisis_support_mid_flow_keeps_the_flow(chat: Chat, step_button):
    await onboard(chat)
    await chat.tap(step_button)
    before = (await db_user(chat)).step
    r = await chat.say("I feel suicidal")
    assert "800 4673" in r[0].text
    assert (await db_user(chat)).step == before       # whatever they were doing is still there


async def db_user(c: Chat) -> User:
    async with sessionmaker()() as s:
        return (await s.execute(select(User).where(User.identity_hash == repo.hash_identity(c.channel, c.phone)))).scalar_one()


# ------------------------------------------------------------------ screens


async def test_menu_and_typed_commands(chat: Chat):
    await onboard(chat)
    r = await chat.say("menu")
    assert "menu:grow" in chat.ids_of(await chat.tap("menu:more"))
    r = await chat.tap("menu:grow")                   # Friends & wellbeing lives in the hub
    assert "menu:social" in chat.ids_of(r)
    r = await chat.tap("menu:social")
    assert [row.id for row in rows(r[0])] == [f"social:{k}" for k in soc.MENU]
    for typed, expect in (("I feel lonely", "very common"), ("homesick", "very common"), ("things to do", "Happening now"),
                          ("make friends", "Never send money"), ("talk to someone", "800 HOPE"),
                          ("check in", "Weekly check-in")):
        r = await chat.say(typed)
        assert expect in r[0].text, typed


def test_every_screen_is_safe_and_fits():
    u = User(channel="whatsapp", identity_hash="x")
    u.social = None
    outs = [soc.social_menu("en"), soc.lonely_message("en"), soc.meet_message("en"), soc.talk_message("en"),
            soc.checkin_screen(u, "en"), soc.crisis_message("en")]
    for d in (TODAY, date(2026, 11, 25), date(2027, 3, 1)):
        outs += soc.free_messages(d, "en")
    for out in outs:
        chk = check_output(out.text)
        assert not chk.blocked and not chk.reasons, (out.text[:40], chk.reasons)
        assert len(out.text) <= 1024 and len(out.buttons) <= 3
        assert all(len(b.title) <= 20 for b in out.buttons)
        for row in rows(out):
            assert len(row.title) <= 24 and len(row.description or "") <= 72


def test_events_expire_on_their_own():
    assert [e.key for e in current_events(TODAY)] == ["dfc_2026"]
    assert [e.key for e in current_events(date(2026, 11, 25))] == ["dfc_2026", "national_day_2026"]
    assert [e.key for e in current_events(date(2026, 12, 10))] == []
    assert "Dubai Fitness Challenge" in soc.free_messages(TODAY, "en")[0].text
    later = soc.free_messages(date(2026, 12, 10), "en")
    assert len(later) == 1 and "Fitness Challenge" not in later[0].text


def test_meet_safely_covers_the_main_scams():
    text = soc.meet_message("en").text
    for must in ("Never send money", "job or visa for money", "Never carry a bag", "public places", "901"):
        assert must in text


# ------------------------------------------------------------------ weekly check-in & moods


async def test_checkin_toggle_and_moods(chat: Chat):
    await onboard(chat)
    r = await chat.say("ok")                          # no check-in to answer: just the menu
    assert "menu:more" in chat.ids_of(r)
    r = await chat.tap("social:on")
    assert "every Friday" in r[0].text and "social:off" in chat.ids_of(r)
    r = await chat.say("GOOD")
    assert "great to hear" in r[0].text
    r = await chat.say("ok")
    assert "Some weeks are just OK" in r[0].text
    r = await chat.say("hard week")
    assert "sorry this week was hard" in r[0].text and "800 HOPE" in r[1].text
    r = await chat.tap("social:off")
    assert "off" in r[0].text
    events = await events_logged()
    assert not any(e.startswith("mood") or (d or "").startswith(("good", "ok", "hard")) for e, d in events)  # moods never stored


async def test_hard_always_gets_support_even_without_checkins(chat: Chat):
    await onboard(chat)
    r = await chat.say("bad week")
    assert "800 HOPE" in r[1].text


def test_social_node_least_privilege():
    authorize("social", "update_own_wellbeing_pref")
    for tool in ("delete_own_data", "export_own_data", "update_own_profile", "update_own_pay", "draft_complaint"):
        with pytest.raises(ToolNotAllowed):
            authorize("social", tool)


# ------------------------------------------------------------------ privacy


async def test_export_delete_and_cleanup(chat: Chat, kv):
    from app import worker

    await onboard(chat)
    await chat.tap("social:on")
    r = await chat.say("my data")
    assert "Weekly check-ins: On" in r[0].text
    r = await chat.say("delete")
    await chat.tap(next(i for i in chat.ids_of(r) if i.startswith("delete:yes:")))
    async with sessionmaker()() as s:
        assert (await s.execute(select(SocialPrefs))).first() is None

    other = Chat(kv, phone="254700000555")
    await onboard(other)
    await other.tap("social:on")
    async with sessionmaker()() as s:
        u = (await s.execute(select(User))).scalar_one()
        u.last_seen_at = utcnow() - timedelta(days=800)
        await s.commit()
    await worker.cleanup({})
    async with sessionmaker()() as s:
        assert (await s.execute(select(SocialPrefs))).first() is None


# ------------------------------------------------------------------ check-ins


async def test_weekly_checkins_once_per_week(kv):
    on = Chat(kv, phone="254700000601")
    await onboard(on)
    await on.tap("social:on")
    off = Chat(kv, phone="254700000602")
    await onboard(off)
    paused = Chat(kv, phone="254700000603")
    await onboard(paused)
    await paused.tap("social:on")
    await paused.say("stop")
    sent = []

    async def send(r):
        sent.append(r)
        return True

    rkv = MemoryKV()
    friday = date(2026, 11, 20)
    async with sessionmaker()() as s:
        assert await send_due_checkins(s, rkv, send, friday) == 1
        assert await send_due_checkins(s, rkv, send, friday) == 0                     # once a week
        assert await send_due_checkins(s, rkv, send, friday + timedelta(days=7)) == 1
    assert sent[0].to == "254700000601" and sent[0].kind == "social" and "How was your week" in sent[0].text


async def test_whatsapp_checkin_uses_its_own_template(monkeypatch):
    from app import worker
    from app.config import get_settings
    from app.modules.stay_legal.visa import Reminder

    calls = []

    async def fake_template(client, to, name, language, params):
        calls.append(name)

    monkeypatch.setattr(worker, "send_template", fake_template)
    monkeypatch.setattr(worker, "_client", lambda ch: object())
    monkeypatch.setenv("WHATSAPP_SOCIAL_TEMPLATE", "rafiq_weekly")
    get_settings.cache_clear()
    r = Reminder("u1", "whatsapp", "254700000001", 0, "text", ["Wanjiru"], kind="social")
    assert await worker.send_reminder(r) is True and calls == ["rafiq_weekly"]
    get_settings.cache_clear()
