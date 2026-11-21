"""The personal checklist: which items a user sees, and the screens for it.

Personalised from the profile only (visa type, home country, journey stage).
Everything is fixed text from content.py: no AI writes any of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.db.models import User
from app.i18n import fmt_date, t
from app.modules.departure import content  # noqa: F401  (registers the text)
from app.modules.departure.content import CLEARANCE_LINKS, EDE, GDRFA, ICP_SMART, NEA_AGENCIES, U_AE_PREPARING


@dataclass(frozen=True)
class Item:
    key: str
    action: tuple[str, str] | None = None   # (button id, label key): a shortcut to another module


PASSPORT = Item("passport")
PERMIT = Item("permit")
VISIT = Item("visit", ("work:visit", "btn_can_i_work"))
CONTRACT = Item("contract", ("menu:job", "btn_check_offer"))
CLEARANCE = Item("clearance")
MEDICINES = Item("medicines", ("legal:med", "btn_check_medicine"))
HEALTH = Item("health")
COPIES = Item("copies")
MONEY = Item("money")
PACK = Item("pack")

ALL_ITEMS = {i.key: i for i in (PASSPORT, PERMIT, VISIT, CONTRACT, CLEARANCE, MEDICINES, HEALTH, COPIES, MONEY, PACK)}


def items_for(user: User) -> list[Item]:
    """At most 9 items, so the list plus the travel-date row fits WhatsApp's 10 rows."""
    visit = user.visa_type == "visit"
    out = [PASSPORT, VISIT if visit else PERMIT, CONTRACT]
    if not visit:
        out.append(CLEARANCE)   # exit clearance is for people leaving to work
    out += [MEDICINES, HEALTH, COPIES, MONEY, PACK]
    return out


def item_for(user: User, key: str) -> Item | None:
    """Only items on THIS user's list are accepted (stale or forged ids are ignored)."""
    return next((i for i in items_for(user) if i.key == key), None)


def title(item: Item, lang: str | None) -> str:
    return t(f"plan_i_{item.key}", lang)


def _bar(done: int, total: int) -> str:
    return "🟩" * done + "⬜" * (total - done)


def progress(user: User) -> tuple[int, int, list[Item]]:
    items = items_for(user)
    done = repo.plan_done(user)
    left = [i for i in items if i.key not in done]
    return len(items) - len(left), len(items), left


def countdown_line(user: User, today: date, lang: str | None) -> str | None:
    travel = repo.get_travel_date(user)
    if not travel:
        return None
    days = (travel - today).days
    d = fmt_date(travel, lang)
    if days < 0:
        return t("plan_flying_past", lang, date=d)
    if days == 0:
        return t("plan_flying_today", lang, date=d)
    if days == 1:
        return t("plan_flying_tomorrow", lang, date=d)
    return t("plan_flying", lang, date=d, days=days)


def overview(user: User, today: date, lang: str | None, *, header: str | None = None) -> Outgoing:
    done_n, total, left = progress(user)
    done = repo.plan_done(user)
    parts = [p for p in (header, t("plan_title", lang)) if p]
    if user.journey_stage in ("arrived", "resident"):
        parts.append(t("plan_intro_here", lang))
    if line := countdown_line(user, today, lang):
        parts.append(line)
    parts.append(t("plan_progress", lang, bar=_bar(done_n, total), done=done_n, total=total))
    if not left:
        parts.append(t("plan_all_done", lang))
    elif done_n:
        parts.append(t("plan_next", lang, item=title(left[0], lang)))
    else:
        parts.append(t("plan_intro", lang))

    rows = [ListRow(id=f"plan:item:{i.key}", title=f"{'✅' if i.key in done else '⬜'} {title(i, lang)}",
                    description=t(f"plan_i_{i.key}_d", lang)) for i in items_for(user)]
    has_date = repo.get_travel_date(user) is not None
    rows.append(ListRow(id="plan:date", title=t("plan_row_date_change" if has_date else "plan_row_date", lang),
                        description=t("plan_row_date_d", lang)))
    return Outgoing(text="\n\n".join(parts), menu=ListMenu(button=t("btn_plan_list", lang), rows=rows))


def detail_key(user: User, item: Item) -> str:
    if item.key == "clearance":
        return f"plan_clearance_{user.home_country}" if user.home_country in CLEARANCE_LINKS else "plan_clearance_other"
    return f"plan_{item.key}"


def detail(user: User, item: Item, lang: str | None) -> Outgoing:
    body = t(detail_key(user, item), lang, u_ae=U_AE_PREPARING, icp=ICP_SMART, gdrfa=GDRFA, ede=EDE,
             nea=NEA_AGENCIES, link=CLEARANCE_LINKS.get(user.home_country or "", ""))
    is_done = item.key in repo.plan_done(user)
    toggle = Button(id=f"plan:{'undo' if is_done else 'done'}:{item.key}",
                    title=t("btn_plan_undo" if is_done else "btn_plan_done", lang))
    buttons = [toggle]
    if item.action:
        buttons.append(Button(id=item.action[0], title=t(item.action[1], lang)))
    buttons.append(Button(id="plan:list", title=t("btn_plan_list", lang)))
    return Outgoing(text=body, buttons=buttons)


def date_prompt(user: User, lang: str | None) -> Outgoing:
    buttons = [Button(id="plan:date_skip", title=t("btn_plan_not_sure", lang))]
    if repo.get_travel_date(user):
        buttons.append(Button(id="plan:date_clear", title=t("btn_plan_remove_date", lang)))
    return Outgoing(text=t("plan_ask_date", lang), buttons=buttons)
