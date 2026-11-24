"""Life Manager (Life admin agent): one prioritised brief of everything that
needs the worker's attention, built from the records the other agents keep.

It runs on scheduled checks and simple rules, not a continuously running AI
model: cheap, predictable and the same answer every time for the same facts.
Each item comes with the one action that moves it forward.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import S, fmt_date, t
from app.security.tool_policy import authorize

NODE = "life"
URGENT, UPCOMING, ONGOING = 0, 1, 2
MAX_ITEMS = 6

STRINGS: dict[str, dict[str, str]] = {
    "life_head": {"en": "☀️ *Your Life Manager*{name}\n{n} thing{s} need{v} your attention:"},
    "life_clear": {"en": "☀️ *Your Life Manager*{name}\nAll clear right now. 👍 I keep watching your visa, salary, documents and cases."},
    "life_tag_0": {"en": "🔴 Urgent"},
    "life_tag_1": {"en": "🟠 Coming up"},
    "life_tag_2": {"en": "🔵 Ongoing"},
    "life_item": {"en": "{tag}: *{title}*\n   {detail}"},
    "life_pick": {"en": "What would you like me to do?"},
    "life_weekly_on": {"en": "✅ I'll send you this brief every Monday morning when something needs attention. Type *brief off* to stop."},
    "life_weekly_off": {"en": "OK, no weekly brief. You can still type *brief* any time."},
    "btn_life_weekly": {"en": "Every Monday"},
    "btn_life_weekly_off": {"en": "Stop weekly brief"},
    "life_weekly_push": {"en": "☀️ Good morning! {n} thing{s} need{v} your attention this week. Type *brief* to see them and act."},
    "li_salary_missing_t": {"en": "Salary for {month} not fully paid"},
    "li_salary_missing_d": {"en": "About AED {owed} owed so far. Build your evidence or open a case."},
    "li_salary_unknown_t": {"en": "Did your {month} salary arrive?"},
    "li_salary_unknown_d": {"en": "Tell me so I can keep your record complete."},
    "li_streak_t": {"en": "Pay short {n} months in a row"},
    "li_streak_d": {"en": "That's a pattern. A case keeps your evidence and dates together."},
    "li_case_follow_t": {"en": "Follow up your {kind} case"},
    "li_case_follow_d": {"en": "Check-in due {date}. Any news from MOHRE?"},
    "li_case_file_t": {"en": "File your {kind} complaint"},
    "li_case_file_d": {"en": "Your case is open but not filed yet."},
    "li_visa_t": {"en": "Visa expires in {days} days"},
    "li_visa_d": {"en": "Ask your employer about renewal now. Expires {date}."},
    "li_visa_gone_t": {"en": "Visa expired {days} days ago"},
    "li_visa_gone_d": {"en": "Fines grow daily. Check your options today."},
    "li_doc_t": {"en": "{kind} expires in {days} days"},
    "li_doc_d": {"en": "Start the renewal so you're never without valid papers."},
    "li_travel_t": {"en": "Travel in {days} days: {left} checklist items left"},
    "li_travel_d": {"en": "Finish them before you fly."},
    "li_arrive_t": {"en": "Residence steps due by {date}"},
    "li_arrive_d": {"en": "{left} arrival items left (Emirates ID, medical, visa stamping)."},
    "li_contact_t": {"en": "No trusted contact yet"},
    "li_contact_d": {"en": "One tap could alert someone you trust if you're ever in danger."},
    "li_rate_t": {"en": "Watching the {cur} rate for you"},
    "li_rate_d": {"en": "I'll message you when 1 AED reaches {target}."},
    "li_watch_t": {"en": "Turn on salary watch"},
    "li_watch_d": {"en": "A monthly check-in builds proof in case you're ever not paid."},
}
S.update(STRINGS)


@dataclass
class Item:
    priority: int
    title: str
    detail: str
    action: str      # button id
    label: str       # row title (max 24)


async def build_brief(user, session: Any, today: date, lang: str | None) -> list[Item]:  # type: ignore[no-untyped-def]
    from app.modules.cases import store as case_store
    from app.modules.cases.node import kind_label as case_kind
    from app.modules.pay import amounts as am
    from app.modules.pay.node import month_label, pay_month
    from app.modules.tasks import vault as vt

    items: list[Item] = []
    log = repo.pay_log(user)
    last = pay_month(today)

    # Salary
    rows, owed = am.gaps(user)
    if log.get(last) in ("unpaid", "part") and last not in am.agreed_months(user):
        items.append(Item(URGENT, t("li_salary_missing_t", lang, month=month_label(last, lang)),
                          t("li_salary_missing_d", lang, owed=f"{owed:,}"), "pay:gaps", "What I'm owed"))
    elif repo.pay_watch_on(user) and last not in log and today.day >= 11:
        items.append(Item(UPCOMING, t("li_salary_unknown_t", lang, month=month_label(last, lang)),
                          t("li_salary_unknown_d", lang), "pay:watch", "Update salary"))
    if (n := am.shortfall_streak(user)) >= 2:
        items.append(Item(URGENT, t("li_streak_t", lang, n=n), t("li_streak_d", lang), "case:new:wages", "Open a wages case"))

    # Cases
    if session is not None:
        for case in await case_store.list_for(session, user.id):
            k = case_kind(case.kind, lang)
            if case.status == "filed" and case.next_check and case.next_check <= today + timedelta(days=3):
                items.append(Item(URGENT, t("li_case_follow_t", lang, kind=k.lower()),
                                  t("li_case_follow_d", lang, date=fmt_date(case.next_check, lang)),
                                  f"case:view:{case.id}", "Update my case"))
            elif case.status == "open":
                items.append(Item(UPCOMING, t("li_case_file_t", lang, kind=k.lower()), t("li_case_file_d", lang),
                                  f"case:view:{case.id}", "Open my case"))

    # Visa
    if exp := repo.get_visa_expiry(user):
        days = (exp - today).days
        if days < 0:
            items.append(Item(URGENT, t("li_visa_gone_t", lang, days=-days), t("li_visa_gone_d", lang), "rnw:view:residence", "Visa renewal"))
        elif days <= 60:
            items.append(Item(URGENT if days <= 14 else UPCOMING, t("li_visa_t", lang, days=days),
                              t("li_visa_d", lang, date=fmt_date(exp, lang)), "rnw:view:residence", "Visa renewal"))

    # Documents
    if session is not None:
        for _doc_id, kind, exp in await vt.list_docs(session, user.id):
            if exp and kind != "visa" and 0 <= (exp - today).days <= 60:
                items.append(Item(URGENT if (exp - today).days <= 14 else UPCOMING,
                                  t("li_doc_t", lang, kind=vt.kind_label(kind, lang), days=(exp - today).days),
                                  t("li_doc_d", lang), "rnw:menu", "My renewals"))

    # Journey checklists
    if user.plan is not None and (travel := repo.get_travel_date(user)) and 0 <= (travel - today).days <= 30:
        from app.modules.departure.checklist import items_for

        left = len(items_for(user)) - len(repo.plan_done(user))
        if left > 0:
            items.append(Item(UPCOMING, t("li_travel_t", lang, days=(travel - today).days, left=left), t("li_travel_d", lang),
                              "menu:plan", "Departure checklist"))
    if user.arrival is not None and (arrived := repo.get_plan_date(user, "arrival")):
        from app.modules.arrival.checklist import items_for as arrival_items
        from app.modules.arrival.content import RESIDENCY_DAYS

        due = arrived + timedelta(days=RESIDENCY_DAYS)
        left = len(arrival_items(user)) - len(repo.plan_done(user, "arrival"))
        if left > 0 and today <= due + timedelta(days=14):
            items.append(Item(URGENT if (due - today).days <= 7 else UPCOMING, t("li_arrive_t", lang, date=fmt_date(due, lang)),
                              t("li_arrive_d", lang, left=left), "menu:arrive", "Arrival checklist"))

    # Reminders the user asked for (rent, appointments, interviews, savings), due in the next 3 days
    if session is not None:
        from app.modules.reminders.store import upcoming

        go = {"rent": ("home:menu", "Housing"), "appointment": ("health:menu", "Health"),
              "interview": ("career:interview", "Interview practice"), "savings": ("grow:goals", "My goals")}
        for kind, due, text in await upcoming(session, user.id, today):
            if (due - today).days <= 3 and kind in go:
                items.append(Item(UPCOMING, text.split(".")[0][:60], f"Reminder on {fmt_date(due, lang)}.", *go[kind]))

    # Ongoing protection and money
    kit = repo.toolkit(user)
    if not kit.get("contact_address") and not kit.get("contact_pending"):
        items.append(Item(ONGOING, t("li_contact_t", lang), t("li_contact_d", lang), "task:sos", "Trusted contact"))
    if (rate := kit.get("rate")) and rate.get("target"):
        items.append(Item(ONGOING, t("li_rate_t", lang, cur=rate.get("cur", "")), t("li_rate_d", lang, target=rate["target"]),
                          "task:rate", "Rate alert"))
    if user.journey_stage in ("arrived", "resident") and not repo.pay_watch_on(user) and not log:
        items.append(Item(ONGOING, t("li_watch_t", lang), t("li_watch_d", lang), "pay:on", "Salary watch"))

    items.sort(key=lambda i: i.priority)
    return items[:MAX_ITEMS]


def brief_message(items: list[Item], user, lang: str | None) -> list[Outgoing]:  # type: ignore[no-untyped-def]
    name = repo.get_display_name(user)
    nm = f", {name}" if name else ""
    weekly = bool(repo.toolkit(user).get("brief_on"))
    toggle = Button(id="life:off" if weekly else "life:on", title=t("btn_life_weekly_off" if weekly else "btn_life_weekly", lang))
    if not items:
        return [Outgoing(text=t("life_clear", lang, name=nm), buttons=[toggle, Button(id="menu:tasks", title=t("btn_tasks", lang))])]
    n = sum(1 for i in items if i.priority < ONGOING) or len(items)
    lines = [t("life_head", lang, name=nm, n=n, s="" if n == 1 else "s", v="s" if n == 1 else "")]
    lines += [t("life_item", lang, tag=t(f"life_tag_{i.priority}", lang), title=i.title, detail=i.detail) for i in items]
    seen: set[str] = set()
    rows = []
    for i in items:
        if i.action not in seen:
            seen.add(i.action)
            rows.append(ListRow(id=i.action, title=i.label[:24], description=i.title[:72]))
    rows.append(ListRow(id=toggle.id, title=toggle.title))
    return [Outgoing(text="\n\n".join(lines)),
            Outgoing(text=t("life_pick", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows[:10]))]


async def life(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user, msg = state["user"], state["incoming"]
    lang = user.language
    bid = msg.button_id or ""
    cmd = state.get("command") or ""
    authorize(NODE, "get_own_profile")
    if bid in ("life:on", "life:off") or cmd in ("brief_on", "brief_off"):
        on = bid == "life:on" or cmd == "brief_on"
        repo.update_toolkit(user, brief_on=on or None)
        return {"replies": [*state.get("replies", []), Outgoing(text=t("life_weekly_on" if on else "life_weekly_off", lang))],
                "events": [*state.get("events", []), ("life_brief_weekly", "on" if on else "off")]}
    authorize(NODE, "get_own_pay")
    authorize(NODE, "get_own_vault")
    authorize(NODE, "get_own_cases")
    authorize(NODE, "get_own_reminders")
    today: date = ctx(config).get("today") or date.today()
    items = await build_brief(user, ctx(config).get("db"), today, lang)
    return {"replies": [*state.get("replies", []), *brief_message(items, user, lang)],
            "events": [*state.get("events", []), ("life_brief", str(len(items)))]}


# ---------------------------------------------------------------- weekly push (worker)

async def send_weekly_briefs(session: Any, send: Any, today: date) -> int:
    from sqlalchemy import select

    from app.db.models import Toolkit, User
    from app.modules.stay_legal.visa import Reminder
    from app.security.crypto import decrypt

    sent = 0
    users = (await session.execute(select(User).join(Toolkit, Toolkit.user_id == User.id)
                                   .where(User.consent_status == "granted", User.notifications_paused == 0))).scalars().all()
    for user in users:
        if not repo.toolkit(user).get("brief_on"):
            continue
        items = [i for i in await build_brief(user, session, today, user.language) if i.priority < ONGOING]
        to = decrypt(user.address_enc)
        if not items or not to:
            continue
        n = len(items)
        r = Reminder(user_id=user.id, channel=user.channel, to=to, days=0, kind="brief",
                     text=t("life_weekly_push", user.language, n=n, s="" if n == 1 else "s", v="s" if n == 1 else ""),
                     template_params=[str(n)])
        try:
            if await send(r):
                sent += 1
        except Exception:
            continue
    return sent
