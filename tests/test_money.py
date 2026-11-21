"""Module 8: Money home."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agent import ui
from app.db.models import AuditLog
from app.db.session import sessionmaker
from app.modules.money import node as mn
from app.security.output_guard import check_output
from app.security.tool_policy import ToolNotAllowed, authorize
from tests.conftest import Chat, onboard


def rows(out) -> list:
    return out.menu.rows if out.menu else []


async def test_main_menu_is_at_whatsapps_limit_and_includes_money(chat: Chat):
    await onboard(chat)
    r = await chat.say("menu")
    assert "menu:money" in chat.ids_of(r)
    assert len(ui.MENU_ITEMS) <= 10                # WhatsApp list maximum


async def test_menu_and_typed_commands(chat: Chat):
    await onboard(chat)
    r = await chat.tap("menu:money")
    assert [row.id for row in rows(r[0])] == [f"money:{k}" for k in mn.MENU]
    for typed, expect in (("send money", "licensed *exchange house*"), ("hawala", "registered with the Central Bank"),
                          ("loan", "3 missed instalments"), ("otp", "Banks don't use WhatsApp"),
                          ("money", "Money home")):
        r = await chat.say(typed)
        assert expect in r[0].text, typed


def test_every_screen_is_safe_and_fits():
    outs = [mn.money_menu("en"), mn.send_message("en"), mn.loans_message("en"), mn.scams_message("en"),
            mn.compare_offers("1000 15 23500\n1000 0 23300", "KES", "en"),
            mn.money_plan("salary 2000, rent 450, food 500, home 700", "en")]
    for out in outs:
        chk = check_output(out.text)
        assert not chk.blocked and not chk.reasons, (out.text[:40], chk.reasons)
        assert len(out.text) <= 1024 and len(out.buttons) <= 3
        assert all(len(b.title) <= 20 for b in out.buttons)
        for row in rows(out):
            assert len(row.title) <= 24 and len(row.description or "") <= 72


# ------------------------------------------------------------------ "rent your account" danger


@pytest.mark.parametrize("text", [
    "A man says he will pay me 500 if I rent my bank account to him",
    "can my friend use my account to receive money for his business?",
    "job asks me to receive money and send it to another person",
    "money mule",
    "my cousin wants to use my card for online payments",
    "should I let him use my wallet",
])
async def test_account_renting_gets_an_immediate_warning(chat: Chat, text):
    await onboard(chat)
    r = await chat.say(text)
    assert "never let anyone use your bank account" in r[0].text and "money laundering" in r[0].text


def test_ordinary_money_talk_is_not_flagged():
    for text in ("how do I open a bank account", "my account is blocked", "I use my card at the shop",
                 "can I use my card abroad"):
        assert mn.money_intent(text) is None


# ------------------------------------------------------------------ compare calculator


async def test_compare_two_offers_in_home_currency(chat: Chat):
    await onboard(chat, country="Kenya")
    r = await chat.tap("money:compare")
    assert "KES" in r[0].text
    r = await chat.say("1000 15 23500\n1000 0 23300")
    text = r[0].text
    assert "Offer 1: you pay *AED 1,015* → *23,500 KES*" in text
    assert "*Offer 2* gets your family the most" in text          # low fee beats the better-looking rate
    assert "per AED" in text


def test_compare_maths():
    out = mn.compare_offers("1000 0 23000\n1000 0 23000", "INR", "en")
    assert "about the same" in out.text
    single = mn.compare_offers("AED 500, fee 10, 11,900", "PHP", "en")
    assert "second offer" in single.text and "*11,900 PHP*" in single.text


@pytest.mark.parametrize("bad", ["a lot", "1000 15", "1000 2000 50", "0 0 100", "1 2 3 4"])
def test_compare_rejects_nonsense(bad):
    assert mn.compare_offers(bad, "KES", "en") is None


async def test_compare_bad_input_and_escape(chat: Chat):
    await onboard(chat)
    await chat.tap("money:compare")
    r = await chat.say("cheap one please")
    assert "3 numbers" in r[0].text
    r = await chat.say("loans")                                   # a command is not calculator input
    assert "3 missed instalments" in r[0].text
    r = await chat.say("1000 15 23500")                           # no longer waiting
    assert "Offer 1" not in r[0].text


# ------------------------------------------------------------------ money plan


def test_money_plan_left_over_and_share_sent_home():
    out = mn.money_plan("salary 2000, rent 450, food 500, transport 150, home 700", "en")
    assert "*Spending:* 1,800" in out.text and "*Left over:* 200" in out.text
    assert "35%" in out.text and "emergencies" in out.text


def test_money_plan_overspending_warns_about_debt():
    out = mn.money_plan("salary 1500 rent 800 food 600 family 500", "en")
    assert "*Left over:* -400" in out.text and "travel bans" in out.text


def test_money_plan_needs_salary_and_words():
    assert "include your salary" in mn.money_plan("rent 450 food 500", "en").text
    assert mn.money_plan("2000 450 500", "en") is None


async def test_nothing_typed_is_stored_or_logged(chat: Chat):
    await onboard(chat)
    await chat.tap("money:budget")
    await chat.say("salary 2345, rent 678")
    await chat.tap("money:compare")
    await chat.say("1000 15 23456")
    async with sessionmaker()() as s:
        details = [d or "" for (d,) in (await s.execute(select(AuditLog.detail))).all()]
    assert not any(n in d for d in details for n in ("2345", "678", "23456", "23,456"))


def test_money_node_least_privilege():
    authorize("money", "get_own_profile")
    for tool in ("update_own_profile", "update_own_pay", "export_own_data", "delete_own_data", "draft_complaint"):
        with pytest.raises(ToolNotAllowed):
            authorize("money", tool)
