"""Module 9: Help & emergency, and the "not safe" safety net."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import repo
from app.db.models import AuditLog, User
from app.db.session import sessionmaker
from app.modules.help import node as hn
from app.modules.help.content import EMBASSIES
from app.security.injection import scan
from app.security.output_guard import check_output
from app.security.tool_policy import ToolNotAllowed, authorize
from tests.conftest import Chat, onboard


def rows(out) -> list:
    return out.menu.rows if out.menu else []


async def db_user(c: Chat) -> User:
    async with sessionmaker()() as s:
        return (await s.execute(select(User).where(User.identity_hash == repo.hash_identity(c.channel, c.phone)))).scalar_one()


# ------------------------------------------------------------------ "not safe" safety net


@pytest.mark.parametrize("text", [
    "my madam beats me every day",
    "The employer locked me in the house",
    "they won't let me leave and took my phone",
    "I am not allowed to go out at all",
    "my sponsor raped me",
    "they forced me to work 18 hours with no food for two days",
    "the agent sold me to another family",
    "He threatened to kill me",
])
def test_unsafe_phrases_detected(text):
    assert hn.unsafe_intent(text)
    assert scan(text).verdict != "block"


@pytest.mark.parametrize("text", ["I locked my phone", "my team beat them at cricket", "it hit me how expensive rent is",
                                  "can I leave work early on Friday", "check job offer"])
def test_ordinary_messages_are_not_flagged(text):
    assert not hn.unsafe_intent(text)


async def test_unsafe_support_from_any_state(chat: Chat):
    r = await chat.say("my employer beats me")                   # even before setup
    assert "800 7283" in r[0].text and "999" in r[0].text
    await onboard(chat)
    await chat.tap("plan:date")
    before = (await db_user(chat)).step
    r = await chat.say("they locked me in the room")
    assert "800 7283" in r[0].text and "absconding" in r[0].text
    assert (await db_user(chat)).step == before                  # their place in the flow is kept
    async with sessionmaker()() as s:
        events = list((await s.execute(select(AuditLog.event, AuditLog.detail))).all())
    assert ("unsafe_support_shown", None) in events                # no message text stored


async def test_crisis_takes_priority_over_unsafe(chat: Chat):
    await onboard(chat)
    r = await chat.say("my employer beats me and I want to kill myself")
    assert "800 4673" in r[0].text                                # suicide support first


# ------------------------------------------------------------------ menu & screens


async def test_help_menu_from_button_and_typing(chat: Chat):
    await onboard(chat)
    for opener in (lambda: chat.tap("menu:help"), lambda: chat.say("help"), lambda: chat.say("SOS")):
        r = await opener()
        assert "999" in r[0].text and [row.id for row in rows(r[0])] == [f"help:{k}" for k in hn.MENU]
    r = await chat.tap("help:about")
    assert "*menu*" in r[0].text and "*delete*" in r[0].text


async def test_help_during_setup_still_reprompts(chat: Chat):
    await chat.say("hi")
    await chat.tap("consent:yes")
    r = await chat.say("help")
    assert "999" in r[0].text and len(r) == 2                     # help, then the setup question again


@pytest.mark.parametrize("typed,expect", [
    ("lost passport", "lost passport certificate"),
    ("report a crime", "800 4888"),
    ("arrested", "interpreter"),
    ("useful numbers", "116111"),
    ("not safe", "800 7283"),
    ("embassy", "cgidubai.gov.in"),
])
async def test_typed_topics(chat: Chat, typed, expect):
    await onboard(chat, country="India")
    r = await chat.say(typed)
    assert expect in r[0].text


@pytest.mark.parametrize("country", [*EMBASSIES, "Nigeria", "Egypt"])
async def test_embassy_for_every_country(kv, country):
    c = Chat(kv, phone="2547" + str(abs(hash(country)) % 10**8).zfill(8))
    await onboard(c, country=country)
    r = await c.say("my embassy")
    text = r[0].text
    if country in EMBASSIES:
        assert all(url in text for _, url in EMBASSIES[country])   # links survive the output guard
    else:
        assert "mofa.gov.ae" in text
    assert "[link removed]" not in text


def test_every_screen_is_safe_and_fits():
    u = User(channel="whatsapp", identity_hash="x")
    outs = [hn.help_menu("en"), hn.unsafe_message("en"), hn.passport_message("en"), hn.report_message("en"),
            hn.police_message("en"), hn.numbers_message("en")]
    for country in [*EMBASSIES, "Somewhere"]:
        u.home_country = country
        outs.append(hn.embassy_message(u, "en"))
    for out in outs:
        chk = check_output(out.text)
        assert not chk.blocked and not chk.reasons, (out.text[:40], chk.reasons)
        assert len(out.text) <= 1024 and len(out.buttons) <= 3
        assert all(len(b.title) <= 20 for b in out.buttons)
        for row in rows(out):
            assert len(row.title) <= 24 and len(row.description or "") <= 72


def test_help_node_least_privilege():
    authorize("help", "get_own_profile")
    for tool in ("update_own_profile", "export_own_data", "delete_own_data", "update_own_pay"):
        with pytest.raises(ToolNotAllowed):
            authorize("help", tool)


def test_output_guard_ignores_punctuation_after_links():
    out = check_output("Dubai: https://www.gdrfad.gov.ae, others: https://smartservices.icp.gov.ae. Fake: https://evil.example.com!")
    assert "https://www.gdrfad.gov.ae," in out.text and "https://smartservices.icp.gov.ae." in out.text
    assert "evil.example.com" not in out.text and "[link removed]!" in out.text
