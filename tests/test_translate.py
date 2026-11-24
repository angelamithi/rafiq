"""Replies in the worker's language: translate in, run the English rules, translate out, check again."""

from __future__ import annotations

import json

from app.media import translate as tr
from tests.conftest import Chat, onboard
from tests.test_guardian import events

SW = "Mwajiri wangu alitakiwa kunilipa AED 1,800 lakini nimepokea AED 1,000 tu. Nifanye nini?"
EN = "My employer was supposed to pay me AED 1,800 but I only received AED 1,000. What should I do?"


class FakeTranslator:
    """In: Swahili -> English. Out: prefixes each item with 'SW: ' (numbers kept), or tampers if told to."""

    def __init__(self, tamper: bool = False) -> None:
        self.tamper, self.calls = tamper, 0

    async def ainvoke(self, msgs):
        self.calls += 1
        system, human = msgs[0].content, msgs[1].content
        if "translate messages sent to" in system:
            return type("R", (), {"content": json.dumps({"lang": "sw", "english": EN})})()
        items = json.loads(human)
        out = [("SW: " + x if x else x) for x in items]
        if self.tamper:
            out = [x.replace("800", "900") for x in out]
        return type("R", (), {"content": json.dumps(out, ensure_ascii=False)})()


def test_detection_and_switch():
    assert tr.looks_foreign(SW) and tr.looks_foreign("मेरी सैलरी नहीं आई")
    assert not tr.looks_foreign(EN) and not tr.looks_foreign("1800")
    assert tr.switch_request("reply in Swahili") == "sw" and tr.switch_request("English") == "en"
    assert tr.switch_request("I speak English and Hindi at work") is None


async def test_swahili_message_gets_swahili_replies_with_facts_kept(chat: Chat):
    chat.translate_model = FakeTranslator()
    await onboard(chat)
    r = await chat.say(SW)
    assert r[0].text.startswith("🌐 I understood (in English)") and "1,800" in r[0].text
    body = r[1].text
    assert body.startswith("SW: ") and "AED 800" in body                # translated, amount unchanged
    assert any(b.title.startswith("SW: ") for m in r for b in m.buttons)
    assert "Translated by AI" in r[-1].text                              # once a day
    assert await events("translated_in") and await events("translated_out")
    # the draft complaint stays in English for MOHRE
    await chat.tap("pay:wc_ded:no")
    r = await chat.tap("pay:wc_draft")
    draft = next(m for m in r if "To:" in m.text or "Subject" in m.text or "Dear" in m.text)
    assert not draft.text.startswith("SW: ")


async def test_changed_numbers_fall_back_to_english(chat: Chat):
    chat.translate_model = FakeTranslator(tamper=True)
    await onboard(chat)
    r = await chat.say(SW)
    body = r[1].text
    assert not body.startswith("SW: ") and "AED 800" in body and "900" not in body


async def test_english_switches_back(chat: Chat):
    chat.translate_model = FakeTranslator()
    await onboard(chat)
    await chat.say(SW)
    r = await chat.say("English")
    assert "reply in English" in r[0].text
    r = await chat.say("menu")
    assert not r[0].text.startswith("SW: ")


async def test_no_model_means_english(chat: Chat):
    await onboard(chat)                                                  # translate_model unset -> no AI in tests
    r = await chat.say(SW)
    assert not r[0].text.startswith("SW: ")
