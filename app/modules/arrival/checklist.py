"""The Arrival Guide checklist: which steps a user sees, and the screens.

Personalised from the profile only (visa type, sector, journey stage) and the
optional arrival date. Fixed text from content.py: no AI writes any of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.db.models import User
from app.i18n import fmt_date, t
from app.modules.arrival import content  # noqa: F401  (registers the text)
from app.modules.departure import content as _shared  # noqa: F401  (shared button labels)
from app.modules.arrival.content import DLD, GDRFA, ICP_SMART, ILOE, MOHRE, RESIDENCY_DAYS

KIND = "arrival"


@dataclass(frozen=True)
class Item:
    key: str
    action: tuple[str, str] | None = None   # (button id, label key): a shortcut to another module


SIM = Item("sim")
RESIDENCY = Item("residency", ("legal:visa", "btn_my_visa"))
VISIT = Item("visit", ("work:visit", "btn_can_i_work"))
CONTRACT = Item("contract", ("menu:job", "btn_check_contract"))
INSURANCE = Item("insurance")
ILOE_ITEM = Item("iloe")
BANK = Item("bank")
HOUSING = Item("housing")
APPS = Item("apps")
RIGHTS = Item("rights")

ALL_ITEMS = {i.key: i for i in (SIM, RESIDENCY, VISIT, CONTRACT, INSURANCE, ILOE_ITEM, BANK, HOUSING, APPS, RIGHTS)}


def items_for(user: User) -> list[Item]:
    """At most 9 steps, so the list plus the arrival-date row fits WhatsApp's 10 rows."""
    out = [SIM, VISIT if user.visa_type == "visit" else RESIDENCY, CONTRACT, INSURANCE]
    if user.sector != "domestic":
        out.append(ILOE_ITEM)          # domestic workers are exempt from ILOE
    out += [BANK, HOUSING, APPS, RIGHTS]
    return out


def item_for(user: User, key: str) -> Item | None:
    return next((i for i in items_for(user) if i.key == key), None)


def title(item: Item, lang: str | None) -> str:
    return t(f"arr_i_{item.key}", lang)


def progress(user: User) -> tuple[int, int, list[Item]]:
    items = items_for(user)
    done = repo.plan_done(user, KIND)
    left = [i for i in items if i.key not in done]
    return len(items) - len(left), len(items), left


def deadline_line(user: User, today: date, lang: str | None) -> str | None:
    """Residence-visa deadline, only while that step is still open."""
    arrived = repo.get_plan_date(user, KIND)
    if not arrived or user.visa_type == "visit" or "residency" in repo.plan_done(user, KIND):
        return None
    due = arrived + timedelta(days=RESIDENCY_DAYS)
    days = (due - today).days
    if days > 0:
        return t("arr_deadline", lang, due=fmt_date(due, lang), days=days)
    if days == 0:
        return t("arr_deadline_today", lang)
    return t("arr_deadline_over", lang, date=fmt_date(arrived, lang))


def overview(user: User, today: date, lang: str | None, *, header: str | None = None) -> Outgoing:
    done_n, total, left = progress(user)
    done = repo.plan_done(user, KIND)
    parts = [p for p in (header, t("arr_title", lang)) if p]
    if user.journey_stage in ("planning", "offer"):
        parts.append(t("arr_not_yet", lang))
    arrived = repo.get_plan_date(user, KIND)
    if arrived:
        parts.append(t("arr_day", lang, n=(today - arrived).days + 1, date=fmt_date(arrived, lang)))
    if line := deadline_line(user, today, lang):
        parts.append(line)
    parts.append(t("arr_progress", lang, bar="🟩" * done_n + "⬜" * (total - done_n), done=done_n, total=total))
    if not left:
        parts.append(t("arr_all_done", lang))
    elif done_n:
        parts.append(t("arr_next", lang, item=title(left[0], lang)))
    else:
        parts.append(t("arr_intro", lang))

    rows = [ListRow(id=f"arrive:item:{i.key}", title=f"{'✅' if i.key in done else '⬜'} {title(i, lang)}",
                    description=t(f"arr_i_{i.key}_d", lang)) for i in items_for(user)]
    rows.append(ListRow(id="arrive:date", title=t("arr_row_date_change" if arrived else "arr_row_date", lang),
                        description=t("arr_row_date_d", lang)))
    return Outgoing(text="\n\n".join(parts), menu=ListMenu(button=t("btn_arr_list", lang), rows=rows))


def detail(user: User, item: Item, today: date, lang: str | None) -> Outgoing:
    body = t(f"arr_{item.key}", lang, icp=ICP_SMART, gdrfa=GDRFA, mohre=MOHRE, iloe=ILOE, dld=DLD)
    if item.key == "residency" and (line := deadline_line(user, today, lang)):
        body += "\n\n" + line
    is_done = item.key in repo.plan_done(user, KIND)
    buttons = [Button(id=f"arrive:{'undo' if is_done else 'done'}:{item.key}",
                      title=t("btn_plan_undo" if is_done else "btn_plan_done", lang))]
    if item.action:
        buttons.append(Button(id=item.action[0], title=t(item.action[1], lang)))
    buttons.append(Button(id="arrive:list", title=t("btn_arr_list", lang)))
    return Outgoing(text=body, buttons=buttons)


def example_date(today: date) -> str:
    return (today - timedelta(days=5)).strftime("%d/%m/%Y")


def date_prompt(user: User, today: date, lang: str | None) -> Outgoing:
    buttons = [Button(id="arrive:date_skip", title=t("btn_plan_not_sure", lang))]
    if repo.get_plan_date(user, KIND):
        buttons.append(Button(id="arrive:date_clear", title=t("btn_plan_remove_date", lang)))
    return Outgoing(text=t("arr_ask_date", lang, example=example_date(today)), buttons=buttons)
