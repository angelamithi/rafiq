"""Overtime calculator: MOHRE's formula (basic / 30 / 8), Article 19 rates."""

from __future__ import annotations

from app.modules.pay import overtime as ot
from tests.conftest import Chat, onboard
from tests.test_guardian import events


def test_formula_matches_mohre():
    o = ot.parse("5000 3 3 1")
    assert round(o.hourly, 2) == 20.83                       # 5000 / 30 / 8
    assert abs(o.normal_pay - 78.125) < 0.001                # 3 h x 20.833 x 1.25
    assert round(o.night_pay, 2) == 93.75                    # 3 h x 20.83 x 1.5
    assert round(o.rest_pay, 2) == 250.0                     # 5000 / 30 x 1.5
    assert not o.over_limit


def test_bad_input_and_limit_warning():
    assert ot.parse("hello") is None and ot.parse("50 2") is None and ot.parse("1500 0 0 0") is None
    assert ot.parse("1500 60").over_limit


async def test_calculator_in_chat(chat: Chat):
    await onboard(chat)                                    # hospitality: private sector
    r = await chat.say("overtime calculator")
    assert "basic" in r[0].text
    r = await chat.say("1500 20 4 1")
    text = r[0].text
    assert "1500 ÷ 30 ÷ 8 = *AED 6.25*" in text.replace(",", "")
    assert "AED 156.25" in text and "AED 37.5" in text and "AED 75" in text and "AED 268.75" in text
    assert "pay:c:hours" in chat.ids_of(r)
    assert await events("overtime_estimate")
