"""LangGraph node for Module 8: Money home.

Deterministic, fixed text plus two small calculators (transfer comparison and
a monthly plan). Nothing the user types is stored or logged: amounts are
parsed, used for one reply, and dropped. No tools touch money or accounts.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.i18n import t
from app.modules.money import content  # noqa: F401  (registers the text)
from app.modules.money.content import CBUAE, CURRENCY
from app.security.tool_policy import authorize

NODE = "money"
AWAIT_COMPARE = "money:await_compare"
AWAIT_BUDGET = "money:await_budget"
MENU = ("send", "compare", "budget", "loans", "scams")
MAX_AMOUNT = 10_000_000
MAX_LINES = 4
MAX_BUDGET_ITEMS = 15
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_PAIR = re.compile(r"([^\W\d_][^\d,;:\n]{0,30}?)\s*[:=-]?\s*(?:aed|dhs?|dirhams?)?\s*(\d[\d,]*(?:\.\d+)?)", re.I | re.U)
_HOME_WORDS = ("home", "family", "send", "remit", "parents", "wife", "husband", "kids", "children", "mother", "father")
_SALARY_WORDS = ("salary", "income", "pay", "wage", "earn")


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _back(lang: str | None, *extra: Button) -> list[Button]:
    return [*extra, Button(id="menu:money", title=t("btn_money_menu", lang)), Button(id="menu:main", title=t("btn_menu", lang))][:3]


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _fmt(n: float) -> str:
    return f"{n:,.0f}" if abs(n - round(n)) < 0.005 else f"{n:,.2f}"


_RENT_ACCOUNT = re.compile(
    r"\b(rent|renting|lend|lending|sell|selling|borrow|borrowing)\s+(out\s+)?(my|your)\s+(bank\s+)?(account|card|wallet)\b"
    r"|\b(wants?\s+to\s+|let\s+(?!me\b)(?:\w+\s+){1,3}|allow\s+(?!me\b)(?:\w+\s+){1,3}|can\s+(?!i\b)(?:\w+\s+){1,3})"
    r"use\s+my\s+(bank\s+)?(account|card|wallet)\b"
    r"|\breceive\s+money\s+(for|and\s+(send|transfer|pass))", re.I)


def money_intent(text: str) -> str | None:
    """Free-text danger signs Money home should answer straight away."""
    if text and len(text) <= 400 and _RENT_ACCOUNT.search(text):
        return "rent_account"
    return None


def currency_for(user) -> str:  # type: ignore[no-untyped-def]
    return CURRENCY.get(user.home_country or "", "home currency")


# ---------------------------------------------------------------- screens

def money_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"money:{k}", title=t(f"money_m_{k}", lang), description=t(f"money_m_{k}_d", lang)) for k in MENU]
    return Outgoing(text=t("money_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def send_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("money_send", lang, cbuae=CBUAE),
                    buttons=_back(lang, Button(id="money:compare", title=t("btn_compare", lang))))


def loans_message(lang: str | None) -> Outgoing:
    return Outgoing(text=f"{t('money_loans', lang)}\n\n{t('money_footer', lang)}", buttons=_back(lang))


def scams_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("money_scams", lang), buttons=_back(lang))


# ---------------------------------------------------------------- calculators

def compare_offers(text: str, cur: str, lang: str | None) -> Outgoing | None:
    """Each line: AED amount, AED fee, amount received. Returns None if unreadable."""
    offers: list[tuple[float, float, float]] = []
    for line in [ln for ln in re.split(r"[\n;/]+", text or "") if ln.strip()][:MAX_LINES]:
        nums = [_num(n) for n in _NUM.findall(line)]
        if len(nums) != 3:
            return None
        amount, fee, received = nums
        if not (0 < amount <= MAX_AMOUNT and 0 <= fee <= amount and 0 < received <= MAX_AMOUNT * 100_000):
            return None
        offers.append((amount, fee, received))
    if not offers:
        return None
    rates = [received / (amount + fee) for amount, fee, received in offers]
    lines = [t("money_compare_line", lang, label=t("money_offer", lang, n=i + 1), paid=_fmt(a + f), received=_fmt(r),
               rate=f"{rate:,.3f}", cur=cur) for i, ((a, f, r), rate) in enumerate(zip(offers, rates))]
    if len(offers) == 1:
        tail = t("money_compare_single", lang)
    else:
        best = max(range(len(rates)), key=rates.__getitem__)
        worst = min(rates)
        diff = (rates[best] - worst) * 1000
        tail = (t("money_compare_same", lang) if diff < 0.5 else
                t("money_compare_best", lang, label=t("money_offer", lang, n=best + 1), diff=_fmt(diff), cur=cur))
    return Outgoing(text="\n".join(lines) + "\n\n" + tail + "\n\n" + t("money_footer", lang),
                    buttons=_back(lang, Button(id="money:send", title=t("money_m_send", lang))))


def money_plan(text: str, lang: str | None) -> Outgoing | None:
    """'salary 2000, rent 450, food 500, home 700' -> what's left. None if unreadable."""
    items: list[tuple[str, float]] = []
    for label, amount in _PAIR.findall(text or "")[:MAX_BUDGET_ITEMS]:
        value = _num(amount)
        word = re.sub(r"\s+", " ", label).strip(" :=-").lower()
        if not word or value > MAX_AMOUNT:
            return None
        items.append((word[:20], value))
    if not items:
        return None
    salary = sum(v for w, v in items if any(s in w for s in _SALARY_WORDS))
    if salary <= 0:
        return Outgoing(text=t("money_budget_no_salary", lang), buttons=_back(lang))
    costs = [(w, v) for w, v in items if not any(s in w for s in _SALARY_WORDS)]
    spent = sum(v for _, v in costs)
    left = salary - spent
    home = sum(v for w, v in costs if any(h in w for h in _HOME_WORDS))
    lines = "\n".join(f"• {w.capitalize()}: {_fmt(v)}" for w, v in costs) or "•"
    if left < 0:
        advice = t("money_budget_over", lang, over=_fmt(-left))
    elif left < salary * 0.05:
        advice = t("money_budget_tight", lang)
    else:
        advice = t("money_budget_ok", lang, left=_fmt(left))
    if home:
        advice += "\n\n" + t("money_budget_home", lang, pct=round(home / salary * 100))
    body = t("money_budget_result", lang, lines=lines, spent=_fmt(spent), left=_fmt(left), advice=advice)
    return Outgoing(text=body + "\n\n" + t("money_footer", lang), buttons=_back(lang))


# ---------------------------------------------------------------- the node

async def money(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    msg = state["incoming"]
    bid = msg.button_id or ""
    cmd = state.get("command") or ""
    text = state.get("text", "")
    authorize(NODE, "get_own_profile")   # only the home country, for the currency name
    action = bid.removeprefix("money:") if bid.startswith("money:") else ""
    cur = currency_for(user)

    # ---- calculator input (only plain input, never a recognised command)
    if cmd == "money_input" and msg.kind == "text" and text and not bid:
        if user.step == AWAIT_COMPARE:
            result = compare_offers(text, cur, lang)
            if result is None:
                return _out(state, Outgoing(text=t("money_compare_bad", lang), buttons=_back(lang)))
            user.step = "ready"
            return _out(state, result)
        if user.step == AWAIT_BUDGET:
            result = money_plan(text, lang)
            if result is None:
                return _out(state, Outgoing(text=t("money_budget_bad", lang), buttons=_back(lang)))
            user.step = "ready"
            return _out(state, result)
    user.step = "ready"

    if cmd == "rent_account":
        return _out(state, Outgoing(text=t("money_rent_warning", lang)), scams_message(lang))
    if action == "send" or cmd == "send_money":
        return _out(state, send_message(lang))
    if action == "compare" or cmd == "compare_costs":
        user.step = AWAIT_COMPARE
        return _out(state, Outgoing(text=t("money_compare_ask", lang, cur=cur), buttons=_back(lang)))
    if action == "budget" or cmd == "budget":
        user.step = AWAIT_BUDGET
        return _out(state, Outgoing(text=t("money_budget_ask", lang), buttons=_back(lang)))
    if action == "loans" or cmd == "loans":
        return _out(state, loans_message(lang))
    if action == "scams" or cmd == "money_scams":
        return _out(state, scams_message(lang))
    return _out(state, money_menu(lang))
