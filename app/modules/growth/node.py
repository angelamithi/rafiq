"""Financial agent: growth tools. Savings goals with progress, a family budget
that finds the pressure points, the yearly cost of sending money home, and a
loan cost calculator. Rafiq never moves money and never recommends a lender.
All numbers the user gives are stored encrypted in their toolkit."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import MONTHS, S, t
from app.modules.reminders import store as reminders
from app.security.tool_policy import authorize

NODE = "growth"
MAX_GOALS = 5

STRINGS: dict[str, dict[str, str]] = {
    "grow_menu": {"en": "📈 *Grow your money*\nPlans that fit your real income, so you can support family *and* build something for yourself."},
    "grow_m_goal": {"en": "New savings goal"},
    "grow_m_goal_d": {"en": "School fees, land, going home: how much a month"},
    "grow_m_goals": {"en": "My goals"},
    "grow_m_goals_d": {"en": "Progress and whether you're on track"},
    "grow_m_budget": {"en": "Family budget check"},
    "grow_m_budget_d": {"en": "Where your money goes and what to change"},
    "grow_m_yearly": {"en": "Yearly cost of sending"},
    "grow_m_yearly_d": {"en": "What transfer fees cost you in a year"},
    "grow_m_loan": {"en": "Loan cost calculator"},
    "grow_m_loan_d": {"en": "What a loan really costs before you sign"},
    "btn_grow": {"en": "Grow my money"},
    "grow_ask_name": {"en": "What are you saving for? (e.g. *school fees*, *land in Kisumu*, *going home*)"},
    "grow_ask_target": {"en": "How much do you need? Type the amount and currency, e.g. *300000 KES* or *5000 AED*."},
    "grow_ask_by": {"en": "By when? (e.g. *12/2027* or *December 2027*)"},
    "grow_bad_target": {"en": "Please type an amount and a 3-letter currency, e.g. *300000 KES*."},
    "grow_bad_by": {"en": "Please type a future month, e.g. *12/2027*."},
    "grow_no_rate": {"en": "I can't get today's {cur} rate, so I'll plan this goal in AED for now."},
    "grow_goal_set": {"en": (
        "🎯 *{name}*: {target} by {by}\n"
        "That's about *AED {monthly} a month* for {months} months{rate}.\n\n"
        "Tell me each month what you saved and I'll show if you're on track."
    )},
    "grow_rate_note": {"en": " (at today's rate, 1 AED = {rate} {cur}; rates change)"},
    "grow_full": {"en": "You have {n} goals, the most I keep. Finish or delete one first."},
    "grow_goals_none": {"en": "No goals yet. Start one and I'll work out the monthly amount."},
    "grow_goal_line": {"en": "• *{name}*: AED {saved} of {target_aed} ({pct}%) · {state}"},
    "grow_on_track": {"en": "on track ✅"},
    "grow_behind": {"en": "behind: save about AED {need}/month from now"},
    "grow_done": {"en": "reached 🎉"},
    "grow_ask_saved": {"en": "How much did you put aside for *{name}* this month, in AED?"},
    "grow_saved": {"en": "✅ Added AED {amount}. *{name}*: AED {saved} of {target} ({pct}%)."},
    "grow_bad_amount": {"en": "Please type just the amount in AED, e.g. *300*."},
    "grow_deleted": {"en": "Goal deleted."},
    "grow_remind_on": {"en": "✅ I'll remind you on the 1st of each month to add what you saved."},
    "btn_add_saving": {"en": "Add savings"},
    "btn_monthly_reminder": {"en": "Remind me monthly"},
    "grow_ask_income": {"en": "What is your monthly income in AED, after deductions? (just the number)"},
    "grow_ask_spend": {"en": (
        "Now your monthly costs in AED, in one message, like:\n"
        "*rent 600, food 400, transport 150, phone 50, family 800, debts 200, other 100*\n"
        "Leave out what you don't pay."
    )},
    "grow_bad_spend": {"en": "I couldn't read that. Try: *rent 600, food 400, family 800*."},
    "grow_budget": {"en": "🧾 *Your month* (income AED {income})\n{lines}\n\n*Left over: AED {left}* ({left_pct}% of income)"},
    "grow_budget_line": {"en": "• {label}: AED {amount} ({pct}%)"},
    "grow_pressure_head": {"en": "*Pressure points*"},
    "grow_p_family": {"en": "Family support is {pct}% of your income. It's generous; agreeing a fixed monthly amount with family helps you both plan."},
    "grow_p_debt": {"en": "Debt payments are {pct}% of income. Pay off the most expensive debt first, and don't take new loans to pay old ones."},
    "grow_p_rent": {"en": "Housing is {pct}% of income. A legal shared room nearer work can cut rent and transport."},
    "grow_p_left": {"en": "Very little is left each month, so one surprise bill can become debt."},
    "grow_p_over": {"en": "⚠️ You spend AED {over} more than you earn each month. Let's fix that first: which cost can change?"},
    "grow_plan": {"en": (
        "*A plan that fits*\n"
        "1. Emergency fund first: AED {fund} (1 month of your essential costs), saving AED {step}/month.\n"
        "2. Then your goals: you can put about AED {goals}/month towards them.{goal_check}"
    )},
    "grow_goal_check_ok": {"en": " That covers your goals. ✅"},
    "grow_goal_check_short": {"en": " Your goals need AED {need}/month, so stretch a deadline or start with the most important one."},
    "grow_ask_yearly": {"en": "Type what you usually send, the fee per transfer, and how many times a month, e.g. *1000 25 2* (all in AED)."},
    "grow_bad_yearly": {"en": "Please type three numbers: amount, fee, times a month, e.g. *1000 25 2*."},
    "grow_yearly": {"en": (
        "💸 You send about *AED {sent}* a year and pay *AED {fees}* in fees ({pct}%).\n"
        "Sending once a month instead of {times} times would save about AED {save_once} a year in fees.\n"
        "Exchange rates matter too: a rate 1% better on AED {sent} is AED {one_pct} more for your family each year. "
        "Type *compare* to compare two offers."
    )},
    "grow_ask_loan": {"en": "Type the loan amount (AED), the interest per *month* in %, and the number of months, e.g. *5000 2.5 12*."},
    "grow_bad_loan": {"en": "Please type three numbers, e.g. *5000 2.5 12*."},
    "grow_loan": {"en": (
        "🏦 Borrowing AED {amount} at {rate}% a month for {months} months:\n"
        "• Monthly payment: *AED {pay}*\n• Total you pay back: *AED {total}*\n• Interest: *AED {interest}*\n\n"
        "{warn}Only borrow from a bank or lender licensed by the UAE Central Bank, and never give anyone your card or OTP."
    )},
    "grow_loan_warn": {"en": "⚠️ That's very expensive: you'd pay back more than 1.5 times what you borrow. "},
}
S.update(STRINGS)

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_CATS = {"rent": ("rent", "housing", "room", "bed"), "food": ("food", "groceries", "meals"),
         "transport": ("transport", "bus", "metro", "taxi", "travel"), "phone": ("phone", "internet", "mobile", "data"),
         "family": ("family", "home", "send", "remit"), "debts": ("debt", "debts", "loan", "loans"),
         "other": ("other", "misc", "extra")}
_LABELS = {"rent": "Rent", "food": "Food", "transport": "Transport", "phone": "Phone & internet",
           "family": "Family support", "debts": "Debt payments", "other": "Other"}


def _nums(text: str) -> list[float]:
    return [float(n.replace(",", "")) for n in _NUM.findall(text or "")]


def parse_spend(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in re.split(r"[,;\n]", (text or "").lower()):
        m = re.search(r"([a-z& ]+?)\s*[:=-]?\s*(\d[\d,]*)", part.strip())
        if not m:
            continue
        word, amount = m.group(1).strip(), int(m.group(2).replace(",", ""))
        for cat, keys in _CATS.items():
            if any(k in word for k in keys) and 0 <= amount <= 200_000:
                out[cat] = out.get(cat, 0) + amount
                break
    return out


def months_between(today: date, by: date) -> int:
    return max(1, (by.year - today.year) * 12 + by.month - today.month)


def budget_report(income: int, spend: dict[str, int], goals_need: int, lang: str | None) -> str:
    total = sum(spend.values())
    left = income - total
    pct = lambda v: round(100 * v / income) if income else 0  # noqa: E731
    lines = [t("grow_budget_line", lang, label=_LABELS[k], amount=f"{v:,}", pct=pct(v)) for k, v in spend.items()]
    parts = [t("grow_budget", lang, income=f"{income:,}", lines="\n".join(lines), left=f"{left:,}", left_pct=pct(left))]
    pressure = []
    if left < 0:
        pressure.append(t("grow_p_over", lang, over=f"{-left:,}"))
    if pct(spend.get("family", 0)) >= 40:
        pressure.append(t("grow_p_family", lang, pct=pct(spend["family"])))
    if pct(spend.get("debts", 0)) >= 30:
        pressure.append(t("grow_p_debt", lang, pct=pct(spend["debts"])))
    if pct(spend.get("rent", 0)) >= 35:
        pressure.append(t("grow_p_rent", lang, pct=pct(spend["rent"])))
    if 0 <= left < income * 0.1:
        pressure.append(t("grow_p_left", lang))
    if pressure:
        parts.append(t("grow_pressure_head", lang) + "\n" + "\n".join(f"• {p}" for p in pressure))
    if left > 0:
        essentials = sum(spend.get(k, 0) for k in ("rent", "food", "transport", "phone", "debts"))
        step = max(1, round(left * 0.4))
        check = ""
        if goals_need:
            check = (t("grow_goal_check_ok", lang) if left - step >= goals_need
                     else t("grow_goal_check_short", lang, need=f"{goals_need:,}"))
        parts.append(t("grow_plan", lang, fund=f"{essentials:,}", step=f"{step:,}", goals=f"{max(0, left - step):,}",
                       goal_check=check))
    return "\n\n".join(parts)


def loan_cost(amount: float, monthly_pct: float, months: int) -> tuple[float, float]:
    r = monthly_pct / 100
    pay = amount / months if r == 0 else amount * r / (1 - (1 + r) ** -months)
    return pay, pay * months


def _goals(user) -> list[dict]:  # type: ignore[no-untyped-def]
    g = repo.toolkit(user).get("goals") or []
    return [x for x in g if isinstance(x, dict)][:MAX_GOALS]


def _goal_state(g: dict, today: date, lang: str | None) -> str:
    saved, target = g.get("saved", 0), g["target_aed"]
    if saved >= target:
        return t("grow_done", lang)
    by = date.fromisoformat(g["by"])
    started = date.fromisoformat(g.get("start", today.isoformat()))
    total_months = months_between(started, by)
    elapsed = max(0, months_between(started, today) - 1) if today > started else 0
    expected = target * min(1, elapsed / total_months)
    if saved + 1 >= expected:
        return t("grow_on_track", lang)
    need = round((target - saved) / months_between(today, by))
    return t("grow_behind", lang, need=f"{need:,}")


def goals_message(user, today: date, lang: str | None) -> Outgoing:  # type: ignore[no-untyped-def]
    goals = _goals(user)
    if not goals:
        return Outgoing(text=t("grow_goals_none", lang), buttons=[Button(id="grow:goal", title=t("grow_m_goal", lang))])
    lines = [t("grow_goal_line", lang, name=g["name"], saved=f"{g.get('saved', 0):,}", target_aed=f"{g['target_aed']:,}",
               pct=min(100, round(100 * g.get("saved", 0) / g["target_aed"])), state=_goal_state(g, today, lang)) for g in goals]
    rows = [ListRow(id=f"grow:add:{i}", title=f"{t('btn_add_saving', lang)}: {g['name']}"[:24]) for i, g in enumerate(goals)]
    rows += [ListRow(id="grow:remind", title=t("btn_monthly_reminder", lang)), ListRow(id="grow:goal", title=t("grow_m_goal", lang))]
    rows += [ListRow(id=f"grow:del:{i}", title=f"Delete: {g['name']}"[:24]) for i, g in enumerate(goals)]
    return Outgoing(text="🎯 *My goals*\n" + "\n".join(lines), menu=ListMenu(button=t("btn_choose", lang), rows=rows[:10]))


def grow_menu(lang: str | None) -> Outgoing:
    keys = ("goal", "goals", "budget", "yearly", "loan")
    rows = [ListRow(id=f"grow:{k}", title=t(f"grow_m_{k}", lang), description=t(f"grow_m_{k}_d", lang)) for k in keys]
    return Outgoing(text=t("grow_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _ev(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


async def growth(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    from app.modules.tasks import pack as pk
    from app.modules.tasks import rates as fx

    user, msg = state["user"], state["incoming"]
    lang = user.language
    bid = msg.button_id or ""
    text = (state.get("text") or "").strip()
    today: date = ctx(config).get("today") or date.today()
    authorize(NODE, "get_own_profile")
    action = bid.removeprefix("grow:") if bid.startswith("grow:") else ""
    kit = repo.toolkit(user)
    draft = kit.get("grow_draft") if isinstance(kit.get("grow_draft"), dict) else {}

    def set_step(step: str | None, d: dict | None) -> None:
        repo.update_toolkit(user, grow_draft=d or None)
        user.step = step or "ready"

    # ---- answers
    if not bid and user.step.startswith("grow:"):
        authorize(NODE, "update_own_toolkit")
        step = user.step
        if step == "grow:name":
            if not (2 <= len(text) <= 40):
                return _out(state, Outgoing(text=t("grow_ask_name", lang)))
            set_step("grow:target", {"name": text})
            return _out(state, Outgoing(text=t("grow_ask_target", lang)))
        if step == "grow:target":
            m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*([A-Za-z]{3})?", text)
            cur = (m.group(2) or "AED").upper() if m else ""
            if not m or not (1 <= float(m.group(1).replace(",", "")) <= 100_000_000):
                return _out(state, Outgoing(text=t("grow_bad_target", lang)))
            set_step("grow:by", {**draft, "target": float(m.group(1).replace(",", "")), "cur": cur})
            return _out(state, Outgoing(text=t("grow_ask_by", lang)))
        if step == "grow:by":
            m = re.fullmatch(r"\s*(\d{1,2})\s*[/\-. ]\s*(\d{4})\s*", text)
            by = None
            if m and 1 <= int(m.group(1)) <= 12:
                by = date(int(m.group(2)), int(m.group(1)), 1)
            else:
                words = text.lower().split()
                if len(words) == 2 and words[1].isdigit():
                    mo = next((i + 1 for i, n in enumerate(MONTHS["en"]) if n.lower().startswith(words[0][:3])), 0)
                    by = date(int(words[1]), mo, 1) if mo else None
            if by is None or by <= today:
                return _out(state, Outgoing(text=t("grow_bad_by", lang)))
            cur, target = draft["cur"], draft["target"]
            extra, rate_note = [], ""
            if cur == "AED":
                target_aed = target
            else:
                rates = await fx.get_rates(ctx(config).get("kv"), ctx(config).get("settings").fx_url if ctx(config).get("settings")
                                           else "https://open.er-api.com/v6/latest/AED", ctx(config).get("fx_fetcher"))
                if rates and cur in rates.rates:
                    target_aed = target / rates.rates[cur]
                    rate_note = t("grow_rate_note", lang, rate=fx.fmt_rate(rates.rates[cur]), cur=cur)
                else:
                    extra.append(Outgoing(text=t("grow_no_rate", lang, cur=cur)))
                    target_aed, cur = target, "AED"
            goals = _goals(user)
            months = months_between(today, by)
            goals.append({"name": draft["name"], "target": target, "cur": cur, "target_aed": round(target_aed),
                          "by": by.isoformat(), "start": today.isoformat(), "saved": 0})
            repo.update_toolkit(user, goals=goals)
            set_step(None, None)
            return _out(state, *extra, Outgoing(
                text=t("grow_goal_set", lang, name=draft["name"], target=f"{target:,.0f} {cur}",
                       by=f"{MONTHS['en'][by.month - 1]} {by.year}", monthly=f"{round(target_aed / months):,}",
                       months=months, rate=rate_note),
                buttons=[Button(id="grow:remind", title=t("btn_monthly_reminder", lang)),
                         Button(id="grow:goals", title=t("grow_m_goals", lang)), Button(id="grow:budget", title=t("grow_m_budget", lang)[:20])]),
                events=_ev(state, ("savings_goal_set", cur)))
        if step == "grow:add":
            nums = _nums(text)
            goals = _goals(user)
            i = int(draft.get("i", -1))
            if len(nums) != 1 or not (0 < nums[0] <= 1_000_000) or not (0 <= i < len(goals)):
                return _out(state, Outgoing(text=t("grow_bad_amount", lang)))
            g = goals[i]
            g["saved"] = int(g.get("saved", 0) + nums[0])
            repo.update_toolkit(user, goals=goals)
            set_step(None, None)
            pct = min(100, round(100 * g["saved"] / g["target_aed"]))
            return _out(state, Outgoing(text=t("grow_saved", lang, amount=f"{nums[0]:,.0f}", name=g["name"], saved=f"{g['saved']:,}",
                                               target=f"{g['target_aed']:,}", pct=pct)), goals_message(user, today, lang),
                        events=_ev(state, ("savings_added", "")))
        if step == "grow:income":
            v = pk.parse_salary(text)
            if v is None:
                return _out(state, Outgoing(text=t("grow_bad_amount", lang)))
            set_step("grow:spend", {"income": v})
            return _out(state, Outgoing(text=t("grow_ask_spend", lang)))
        if step == "grow:spend":
            spend = parse_spend(text)
            if not spend:
                return _out(state, Outgoing(text=t("grow_bad_spend", lang)))
            income = int(draft.get("income", 0))
            repo.update_toolkit(user, budget={"income": income, "spend": spend})
            set_step(None, None)
            need = sum(round(g["target_aed"] - g.get("saved", 0)) // months_between(today, date.fromisoformat(g["by"]))
                       for g in _goals(user) if g.get("saved", 0) < g["target_aed"])
            return _out(state, Outgoing(text=budget_report(income, spend, need, lang),
                                        buttons=[Button(id="grow:goal", title=t("grow_m_goal", lang)),
                                                 Button(id="money:compare", title="Compare transfers"),
                                                 Button(id="menu:main", title=t("btn_menu", lang))]),
                        events=_ev(state, ("budget_checked", "")))
        if step == "grow:yearly":
            nums = _nums(text)
            if len(nums) != 3 or not (0 < nums[0] <= 500_000 and 0 <= nums[1] <= 10_000 and 0 < nums[2] <= 31):
                return _out(state, Outgoing(text=t("grow_bad_yearly", lang)))
            amount, fee, times = nums
            sent, fees = amount * times * 12, fee * times * 12
            set_step(None, None)
            return _out(state, Outgoing(text=t("grow_yearly", lang, sent=f"{sent:,.0f}", fees=f"{fees:,.0f}",
                                               pct=f"{100 * fees / sent:.1f}", times=f"{times:g}",
                                               save_once=f"{max(0.0, fees - fee * 12):,.0f}", one_pct=f"{sent / 100:,.0f}")),
                        events=_ev(state, ("remit_cost_checked", "")))
        if step == "grow:loan":
            nums = _nums(text)
            if len(nums) != 3 or not (100 <= nums[0] <= 10_000_000 and 0 <= nums[1] <= 50 and 1 <= nums[2] <= 360):
                return _out(state, Outgoing(text=t("grow_bad_loan", lang)))
            pay, total = loan_cost(nums[0], nums[1], int(nums[2]))
            set_step(None, None)
            return _out(state, Outgoing(text=t("grow_loan", lang, amount=f"{nums[0]:,.0f}", rate=f"{nums[1]:g}", months=int(nums[2]),
                                               pay=f"{pay:,.0f}", total=f"{total:,.0f}", interest=f"{total - nums[0]:,.0f}",
                                               warn=t("grow_loan_warn", lang) if total > 1.5 * nums[0] else "")),
                        events=_ev(state, ("loan_cost_checked", "")))
    user.step = "ready"

    if action == "goal":
        if len(_goals(user)) >= MAX_GOALS:
            return _out(state, Outgoing(text=t("grow_full", lang, n=MAX_GOALS)), goals_message(user, today, lang))
        set_step("grow:name", {})
        return _out(state, Outgoing(text=t("grow_ask_name", lang)))
    if action == "goals":
        return _out(state, goals_message(user, today, lang))
    if action.startswith("add:") and action[4:].isdigit() and int(action[4:]) < len(_goals(user)):
        i = int(action[4:])
        set_step("grow:add", {"i": i})
        return _out(state, Outgoing(text=t("grow_ask_saved", lang, name=_goals(user)[i]["name"])))
    if action.startswith("del:") and action[4:].isdigit() and int(action[4:]) < len(_goals(user)):
        goals = _goals(user)
        goals.pop(int(action[4:]))
        repo.update_toolkit(user, goals=goals or None)
        return _out(state, Outgoing(text=t("grow_deleted", lang)), goals_message(user, today, lang))
    if action == "remind":
        session = ctx(config).get("db")
        authorize(NODE, "update_own_reminders")
        from app.modules.reminders.store import add_month

        await reminders.replace_kind(session, user.id, "savings")
        first = add_month(today.replace(day=1))
        await reminders.add(session, user.id, "savings", first, "Savings check-in: type *my goals* to add what you saved this month.",
                            monthly=True)
        return _out(state, Outgoing(text=t("grow_remind_on", lang)), events=_ev(state, ("savings_reminder_on", "")))
    if action == "budget":
        set_step("grow:income", {})
        return _out(state, Outgoing(text=t("grow_ask_income", lang)))
    if action == "yearly":
        set_step("grow:yearly", {})
        return _out(state, Outgoing(text=t("grow_ask_yearly", lang)))
    if action == "loan":
        set_step("grow:loan", {})
        return _out(state, Outgoing(text=t("grow_ask_loan", lang)))
    cmd = state.get("command") or ""
    if cmd == "goals":
        return _out(state, goals_message(user, today, lang))
    if cmd == "family_budget":
        set_step("grow:income", {})
        return _out(state, Outgoing(text=t("grow_ask_income", lang)))
    if cmd == "loan_cost":
        set_step("grow:loan", {})
        return _out(state, Outgoing(text=t("grow_ask_loan", lang)))
    return _out(state, grow_menu(lang))
