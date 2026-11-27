"""Flagship workflow: the Employment protection agent's wage check, end to end."""

from __future__ import annotations

from app.modules.pay import wagecheck as wc
from tests.conftest import Chat, onboard
from tests.test_guardian import events

GRACE = "My employer was supposed to pay me AED 1,800, but I only received AED 1,000. What can I do?"


def test_parse_rules():
    assert wc.looks_like_shortfall(GRACE)
    assert wc.parse(GRACE, None) == (1800, 1000, "said")
    assert wc.parse("I only got 1200 this month", 1800) == (1800, 1200, "contract")
    assert wc.parse("my salary of 1500 was not paid", None) == (1500, 0, "said")
    assert not wc.looks_like_shortfall("Hotel job in Dubai, salary AED 3000, pay KES 50,000 visa fee to agent")
    assert not wc.looks_like_shortfall("how do I renew my visa?")


async def test_one_message_to_evidence_pack_and_reviewed_draft(chat: Chat):
    await onboard(chat)
    r = await chat.say(GRACE)
    text = r[0].text
    assert "Potential shortfall: *AED 800*" in text and "isn't a legal decision" in text
    assert "pay:wc_ded:no" in chat.ids_of(r)
    r = await chat.tap("pay:wc_ded:no")
    assert "AED 800" in r[0].text and "pay:wc_pack" in chat.ids_of(r)
    r = await chat.tap("pay:wc_pack")
    assert r[0].file.startswith(b"%PDF") and "not an official complaint" in r[0].text
    r = await chat.tap("pay:wc_draft")
    joined = " ".join(m.text or "" for m in r)
    assert "Nothing has been sent" in joined and "about AED 800" in joined and "80084" in joined
    filed = next(i for i in chat.ids_of(r) if i.startswith("case:filed:"))
    r = await chat.tap(filed)                               # she filed it herself: Rafiq asks for her reference
    assert "employment" in await events("handled_by")
    for step in ("wage_check", "wage_check_deduction", "evidence_pack_built", "complaint_drafted"):
        assert await events(step), step


async def test_agreed_deduction_is_not_counted_as_owed(chat: Chat):
    await onboard(chat)
    await chat.say(GRACE)
    r = await chat.tap("pay:wc_ded:yes")
    assert "may not be owed" in r[0].text


async def test_missing_amount_asks_for_both(chat: Chat):
    await onboard(chat)
    r = await chat.say("my boss paid me less salary than agreed again")
    assert "Send both amounts" in r[0].text


async def test_wage_check_from_the_menu_and_after_missing_amounts(chat: Chat):
    await onboard(chat)
    r = await chat.say("menu")
    assert chat.ids_of(r)[0] == "pay:wc"                         # employment protection leads the menu
    r = await chat.tap("menu:pay")
    assert "pay:wc" in chat.ids_of(r)
    r = await chat.tap("pay:wc")
    assert "Send both amounts" in r[0].text
    r = await chat.say("contract 1800, received 1000")
    assert "Potential shortfall: *AED 800*" in r[0].text
    await chat.say("my boss paid me less salary than agreed again")   # missing amounts -> waits for them
    r = await chat.say("agreed 2000 got 1500")
    assert "Potential shortfall: *AED 500*" in r[0].text


async def _opens(chat: Chat, items) -> None:
    from app.i18n import t

    await onboard(chat)
    for item in items:                    # few enough taps to stay under the 20-a-minute rate limit
        r = await chat.tap(item.id)
        assert r and t("didnt_understand", None) not in (r[0].text or ""), item.id


async def test_every_main_menu_row_opens_something(chat: Chat):
    from app.agent import ui

    await _opens(chat, ui.MENU_ITEMS)


async def test_every_more_menu_row_opens_something(chat: Chat):
    from app.agent import ui

    await _opens(chat, ui.MORE_ITEMS)
