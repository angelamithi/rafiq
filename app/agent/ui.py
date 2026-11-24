"""Builds every message the user sees in Module 1.

Each builder returns an Outgoing (text + up to 3 buttons, or a list menu of up
to 10 rows). `options_for_step` exposes the same choices so typed answers
("2", "kenya", "skip") can be matched when users don't tap a button.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.db.models import User
from app.i18n import (
    COUNTRIES,
    SECTORS,
    STAGES,
    VISAS,
    fmt_date,
    t,
)


@dataclass(frozen=True)
class MenuItem:
    id: str
    title_key: str
    desc_key: str


# Module 1 menu. Later modules insert their items ABOVE these (most useful first).
MENU_ITEMS: list[MenuItem] = [
    MenuItem("menu:pay", "menu_pay", "menu_pay_d"),            # Lead: employment protection (wage check)
    MenuItem("menu:job", "menu_job", "menu_job_d"),            # Job offer + Contract Shield
    MenuItem("menu:tasks", "menu_tasks", "menu_tasks_d"),      # "Do it for me"
    MenuItem("menu:legal", "menu_legal", "menu_legal_d"),      # Module 3
    MenuItem("rnw:menu", "btn_renewals", "menu_renewals_d"),  # Renewals + status check
    MenuItem("menu:plan", "menu_plan", "menu_plan_d"),         # Module 4
    MenuItem("menu:arrive", "menu_arrive", "menu_arrive_d"),   # Module 5
    MenuItem("menu:money", "menu_money", "menu_money_d"),      # Module 8
    MenuItem("menu:grow", "menu_grow", "menu_grow_d"),          # Career, housing, health, savings, profile
    MenuItem("menu:help", "menu_help", "menu_help_d"),
]

EDITABLE = ("name", "stage", "country", "visa", "expiry", "sector")
_FIELD_LABEL = {
    "name": "field_name", "stage": "field_stage", "country": "field_country",
    "visa": "field_visa", "expiry": "field_expiry", "sector": "field_sector",
}


def _name_part(user: User) -> str:
    name = repo.get_display_name(user)
    return f", {name}" if name else ""


# ---------------------------------------------------------------- onboarding

def consent_prompt(lang: str | None, *, more: bool = False, updated: bool = False, welcome: bool = False, months: int = 12) -> Outgoing:
    body = t("consent_more", lang, months=months) if more else t("consent", lang)
    if welcome:
        body = t("welcome", lang) + "\n\n" + body
    if updated:
        body = t("consent_updated", lang) + "\n\n" + body
    buttons = [Button(id="consent:yes", title=t("btn_agree", lang))]
    if not more:
        buttons.append(Button(id="consent:more", title=t("btn_more", lang)))
    buttons.append(Button(id="consent:no", title=t("btn_decline", lang)))
    return Outgoing(text=body, buttons=buttons)


def name_prompt(lang: str | None) -> Outgoing:
    return Outgoing(text=t("ask_name", lang), buttons=[Button(id="name:skip", title=t("btn_skip", lang))])


def stage_prompt(lang: str | None, user: User) -> Outgoing:
    rows = [ListRow(id=f"stage:{k}", title=v["en"][0], description=v["en"][1]) for k, v in STAGES.items()]
    return Outgoing(text=t("ask_stage", lang, name_part=_name_part(user)), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def country_prompt(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"country:{k}", title=v["en"]) for k, v in COUNTRIES.items()]
    rows.append(ListRow(id="country:other", title=t("country_other", lang)))
    return Outgoing(text=t("ask_country", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def country_other_prompt(lang: str | None) -> Outgoing:
    return Outgoing(text=t("ask_country_other", lang))


def visa_prompt(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"visa:{k}", title=v["en"]) for k, v in VISAS.items()]
    return Outgoing(text=t("ask_visa", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def expiry_prompt(lang: str | None) -> Outgoing:
    return Outgoing(text=t("ask_expiry", lang), buttons=[Button(id="expiry:skip", title=t("btn_skip_for_now", lang))])


def sector_prompt(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"sector:{k}", title=v["en"]) for k, v in SECTORS.items()]
    return Outgoing(text=t("ask_sector", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def _profile_values(user: User, lang: str | None) -> dict[str, str]:
    ns = t("not_set", lang)
    expiry = repo.get_visa_expiry(user)
    stage = STAGES.get(user.journey_stage or "")
    country = COUNTRIES.get(user.home_country or "")
    return {
        "name": repo.get_display_name(user) or ns,
        "stage": stage["en"][0] if stage else ns,
        "country": (country["en"] if country else user.home_country) or ns,
        "visa": VISAS[user.visa_type]["en"] if user.visa_type in VISAS else ns,
        "expiry": fmt_date(expiry, lang) if expiry else ns,
        "sector": SECTORS[user.sector]["en"] if user.sector in SECTORS else ns,
        "reminders": t("off", lang) if user.notifications_paused else t("on", lang),
    }


def summary_prompt(lang: str | None, user: User) -> Outgoing:
    return Outgoing(
        text=t("summary", lang, **_profile_values(user, lang)),
        buttons=[Button(id="summary:ok", title=t("btn_correct", lang)), Button(id="summary:edit", title=t("btn_edit", lang))],
    )


def edit_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"edit:{f}", title=t(_FIELD_LABEL[f], lang)) for f in EDITABLE]
    return Outgoing(text=t("edit_which", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


# ---------------------------------------------------------------- menu & profile

def main_menu(lang: str | None, *, intro: str | None = None) -> Outgoing:
    rows = [ListRow(id=i.id, title=t(i.title_key, lang), description=t(i.desc_key, lang)) for i in MENU_ITEMS]
    return Outgoing(text=intro or t("main_menu", lang), menu=ListMenu(button=t("btn_menu_open", lang), rows=rows))


def welcome_back(lang: str | None, user: User) -> Outgoing:
    return main_menu(lang, intro=t("welcome_back", lang, name_part=_name_part(user)))


def profile_view(lang: str | None, user: User) -> Outgoing:
    return Outgoing(
        text=t("profile_view", lang, **_profile_values(user, lang)),
        buttons=[Button(id="profile:edit", title=t("btn_edit_details", lang)),
                 Button(id="menu:privacy", title=t("menu_privacy", lang)), Button(id="menu:main", title=t("btn_menu", lang))],
    )


def help_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("help", lang), buttons=[Button(id="menu:main", title=t("btn_menu", lang))])


def privacy_menu(lang: str | None) -> Outgoing:
    return Outgoing(
        text=t("privacy_menu", lang),
        buttons=[
            Button(id="privacy:export", title=t("btn_see_data", lang)),
            Button(id="privacy:delete", title=t("btn_delete_data", lang)),
            Button(id="menu:main", title=t("btn_menu", lang)),
        ],
    )


def export_message(lang: str | None, user: User) -> Outgoing:
    v = _profile_values(user, lang)
    ns = t("not_set", lang)
    data = repo.export_data(user)
    lines = [
        f"• {t('field_name', lang)}: {v['name']}",
        f"• {t('field_stage', lang)}: {v['stage']}",
        f"• {t('field_country', lang)}: {v['country']}",
        f"• {t('field_visa', lang)}: {v['visa']}",
        f"• {t('field_expiry', lang)}: {v['expiry']}",
        f"• {t('field_sector', lang)}: {v['sector']}",
        f"• {t('field_consent', lang)}: {data['consent'] or ns}",
        f"• {t('field_joined', lang)}: {data['joined'] or ns}",
    ]
    if data.get("travel_date") or data.get("checklist_done"):
        travel = repo.get_travel_date(user)
        lines.append(f"• {t('field_travel_date', lang)}: {fmt_date(travel, lang) if travel else ns}")
        lines.append(f"• {t('field_checklist', lang)}: {data['checklist_done'] or ns}")
    if data.get("arrival_date") or data.get("arrival_done"):
        arrived = repo.get_plan_date(user, "arrival")
        lines.append(f"• {t('field_arrival_date', lang)}: {fmt_date(arrived, lang) if arrived else ns}")
        lines.append(f"• {t('field_arrival_checklist', lang)}: {data['arrival_done'] or ns}")
    if data.get("salary_watch") or data.get("salary_record"):
        lines.append(f"• {t('field_salary_watch', lang)}: {t('on' if data['salary_watch'] == 'on' else 'off', lang)}")
        lines.append(f"• {t('field_salary_record', lang)}: {data['salary_record'] or ns}")
    if data.get("wellbeing_checkins"):
        lines.append(f"• {t('field_wellbeing', lang)}: {t('on' if data['wellbeing_checkins'] == 'on' else 'off', lang)}")
    for key in ("employer", "monthly_salary", "job_start", "trusted_contact", "rate_alert"):
        if data.get(key):
            lines.append(f"• {t('field_' + key, lang)}: {data[key]}")
    lines.append(f"• {t('field_vault', lang)}")
    return Outgoing(
        text=t("export", lang, data="\n".join(lines)),
        buttons=[Button(id="privacy:delete", title=t("btn_delete_data", lang)), Button(id="menu:main", title=t("btn_menu", lang))],
    )


def delete_confirm(lang: str | None, nonce: str) -> Outgoing:
    return Outgoing(
        text=t("delete_confirm", lang),
        buttons=[Button(id=f"delete:yes:{nonce}", title=t("btn_yes_delete", lang)), Button(id="delete:no", title=t("btn_no_keep", lang))],
    )


def text(key: str, lang: str | None, **kw: object) -> Outgoing:
    return Outgoing(text=t(key, lang, **kw))


# ---------------------------------------------------------------- typed-answer matching

def options_for_step(step: str, lang: str | None) -> list[tuple[str, str]]:
    """(id, title) pairs, plus common typed words, so typed answers work too."""
    def table(tbl: dict, prefix: str, pick=lambda v: v) -> list[tuple[str, str]]:  # type: ignore[no-untyped-def]
        return [(f"{prefix}:{k}", pick(v["en"])) for k, v in tbl.items()]

    match step:
        case "consent":
            return [("consent:yes", t("btn_agree", lang)), ("consent:more", t("btn_more", lang)), ("consent:no", t("btn_decline", lang)),
                    ("consent:yes", "yes"), ("consent:yes", "agree"), ("consent:yes", "ok"), ("consent:yes", "i agree"),
                    ("consent:no", "no"), ("consent:more", "more")]
        case "stage":
            return table(STAGES, "stage", lambda v: v[0])
        case "country":
            return [(f"country:{k}", k) for k in COUNTRIES] + [("country:other", t("country_other", lang))]
        case "visa":
            return table(VISAS, "visa")
        case "sector":
            return table(SECTORS, "sector")
        case "summary":
            return [("summary:ok", t("btn_correct", lang)), ("summary:edit", t("btn_edit", lang)),
                    ("summary:ok", "yes"), ("summary:ok", "correct"), ("summary:ok", "ok"), ("summary:edit", "edit")]
        case "edit":
            return [(f"edit:{f}", t(_FIELD_LABEL[f], lang)) for f in EDITABLE]
        case "name":
            return [("name:skip", "skip")]
        case "expiry":
            return [("expiry:skip", "skip"), ("expiry:skip", t("btn_skip_for_now", lang))]
    return []


def prompt_for_step(step: str, lang: str | None, user: User, *, months: int = 12) -> Outgoing | None:
    match step:
        case "consent":
            return consent_prompt(lang, months=months)
        case "name":
            return name_prompt(lang)
        case "stage":
            return stage_prompt(lang, user)
        case "country":
            return country_prompt(lang)
        case "country_other":
            return country_other_prompt(lang)
        case "visa":
            return visa_prompt(lang)
        case "expiry":
            return expiry_prompt(lang)
        case "sector":
            return sector_prompt(lang)
        case "summary":
            return summary_prompt(lang, user)
        case "edit":
            return edit_menu(lang)
    return None
