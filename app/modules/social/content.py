"""Friends & wellbeing (Social Circle): all user-facing text, support lines
and the curated, DATED list of community events.

Design choice: Rafiq does NOT match users with strangers or share anyone's
contact details. Lonely newcomers are prime targets for romance, "friend"
and job scams, so the module points to public, free, official places and
events instead, and teaches how to meet people safely.

Checked on 2026-11-19 (see README):
- 800-HOPE (800 4673): national mental health support line, call or WhatsApp,
  Arabic and English, 9am to midnight (National Programme for Happiness and Wellbeing).
- 800-SAKINA (800 725462): Abu Dhabi DOH / SEHA line, announced as 24/7.
- Itma'en, Dubai Health: 800 506.
- Indian Workers Resource Centre helpline 800 46342, now open to all nationalities.
- Emergencies: 999 police, 998 ambulance.
- Dubai Fitness Challenge 2026: 31 Oct to 29 Nov, free Fitness Villages and hubs.
- Mohammed bin Rashid Library: free membership for residents.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.i18n import S

CHECKED_ON = "2026-11-19"

MBRL = "https://www.mbrl.ae"
DUBAI_CULTURE = "https://dubaiculture.gov.ae"
VISIT_DUBAI_EVENTS = "https://www.visitdubai.com"
DFC = "https://www.dubaifitnesschallenge.com"
DUBAI_POLICE = "https://www.dubaipolice.gov.ae"


@dataclass(frozen=True)
class Event:
    """A curated community event. It is shown only between `show_from` and
    `end`, so stale events disappear on their own. The team adds new ones here
    (later: from the admin app), each with an official link."""

    key: str
    show_from: date
    end: date
    link: str


EVENTS: tuple[Event, ...] = (
    Event("dfc_2026", date(2026, 10, 20), date(2026, 11, 29), DFC),
    Event("national_day_2026", date(2026, 11, 22), date(2026, 12, 3), VISIT_DUBAI_EVENTS),
)


def current_events(today: date) -> list[Event]:
    return [e for e in EVENTS if e.show_from <= today <= e.end]


# Self-harm / suicide language. Checked on EVERY message, before anything else,
# so support is shown even mid-setup. Kept specific to avoid false alarms
# ("kill time", "dead tired" do not match).
CRISIS_PHRASES = (
    "kill myself", "killing myself", "end my life", "ending my life", "take my own life", "take my life",
    "suicide", "suicidal", "want to die", "wanna die", "i want to be dead", "better off dead",
    "don't want to live", "dont want to live", "do not want to live", "no reason to live", "nothing to live for",
    "hurt myself", "harm myself", "self harm", "self-harm", "cut myself", "end it all",
)

STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ menu
    "menu_social": {"en": "Friends & wellbeing"},
    "menu_social_d": {"en": "Feeling lonely? Free things to do, support"},
    "soc_menu": {"en": "🤝 *Friends & wellbeing*\nMoving far from home is hard. What would help right now?"},
    "soc_m_lonely": {"en": "I feel lonely"},
    "soc_m_lonely_d": {"en": "Small steps that really help"},
    "soc_m_free": {"en": "Free things to do"},
    "soc_m_free_d": {"en": "Beaches, parks, libraries and events"},
    "soc_m_meet": {"en": "Meet people safely"},
    "soc_m_meet_d": {"en": "Find your community without getting scammed"},
    "soc_m_talk": {"en": "Talk to someone"},
    "soc_m_talk_d": {"en": "Free, confidential support lines"},
    "soc_m_checkin": {"en": "Weekly check-in"},
    "soc_m_checkin_d": {"en": "I'll ask how your week went"},
    "btn_soc_menu": {"en": "Friends & wellbeing"},
    "btn_free_things": {"en": "Free things to do"},
    "btn_talk": {"en": "Talk to someone"},
    "btn_meet_safely": {"en": "Meet people safely"},
    "btn_keep_talking": {"en": "Keep talking"},

    # ------------------------------------------------------------------ lonely
    "soc_lonely": {
        "en": (
            "💛 *Feeling lonely is very common here*\n\n"
            "Most people in the UAE came from somewhere else, and almost everyone feels this in their first months. It doesn't mean something is wrong with you.\n\n"
            "*Small steps that help:*\n"
            "• *Keep one fixed call home* each week, at the same time. Something to look forward to.\n"
            "• *Go where people already are*: a free class, a park, a library, your place of worship. Being around people helps, even before you make friends.\n"
            "• *Say yes to one small thing* a week: tea with a coworker, a walk after work.\n"
            "• *Move your body* for 30 minutes. It really helps your mood.\n"
            "• *Be kind to yourself* about sleep, food and rest. Tiredness makes everything feel heavier.\n\n"
            "If the sadness doesn't lift for a few weeks, please talk to someone. It's free and confidential."
        ),
    },

    # ------------------------------------------------------------------ free things
    "soc_free": {
        "en": (
            "🌴 *Free (or nearly free) things to do*\n\n"
            "• *Public beaches*: Dubai's public beaches, like Kite Beach and Jumeirah public beach, are free. Swim only where it's allowed and lifeguards are on duty.\n"
            "• *Parks*: great for an evening walk, a picnic or cricket and football with friends.\n"
            "• *Libraries*: free to enter, with Wi-Fi, quiet space and events. Mohammed bin Rashid Library membership is free for residents: {mbrl}\n"
            "• *Culture*: many exhibitions and community events are free: {culture}\n"
            "• *What's on*: Dubai's official events calendar: {events}\n\n"
            "Modest clothes in public places, and no photos of strangers without asking."
        ),
    },
    "soc_events_head": {"en": "📅 *Happening now*"},
    "soc_event_dfc_2026": {
        "en": (
            "🏃 *Dubai Fitness Challenge* (until 29 November): free classes and workouts at Fitness Villages (including Kite Beach) and community hubs across the city. "
            "A great way to meet people. Free registration: {link}"
        ),
    },
    "soc_event_national_day_2026": {
        "en": "🇦🇪 *Eid Al Etihad (UAE National Day), 2 December*: celebrations in many public places. Join in respectfully and enjoy it: {link}",
    },

    # ------------------------------------------------------------------ meet people safely
    "soc_meet": {
        "en": (
            "🛡️ *Meet people safely*\n\n"
            "*Good places to find your community:*\n"
            "• Your embassy or consulate's community events and associations.\n"
            "• Your place of worship.\n"
            "• Free sports, fitness and library events.\n"
            "• Coworkers you trust.\n\n"
            "*Stay safe:*\n"
            "• First meetings in *public places*, in daylight. Tell a friend where you're going.\n"
            "• *Never send money* to someone you met online, however close you feel. Romance scammers build trust for weeks, avoid video calls, then have an \"emergency\".\n"
            "• A new \"friend\" offering a *job or visa for money* is a scam. Real visas come through employers and government channels.\n"
            "• *Never carry a bag or parcel* for someone, and never let anyone use your SIM, bank account or Emirates ID.\n"
            "• Don't share your passport, OTP codes or bank details.\n"
            "• Groups that charge \"membership\" or promise big investment returns are a warning sign.\n\n"
            "Scammed or worried? Report it to Dubai Police on *901* (non-emergency) or the police app: {police}"
        ),
    },

    # ------------------------------------------------------------------ talk to someone
    "soc_talk": {
        "en": (
            "📞 *Talk to someone* (free and confidential)\n\n"
            "• *800 HOPE* (800 4673): national support line. Call *or WhatsApp*, Arabic and English, 9am to midnight.\n"
            "• *800 SAKINA* (800 725462): mental health support, announced as open 24/7.\n"
            "• *Dubai*: Itma'en, Dubai Health, *800 506*.\n"
            "• *800 46342*: the Indian Workers Resource Centre helpline, now open to workers of all nationalities.\n\n"
            "🚨 If you or someone else is in danger right now, call *999* (police) or *998* (ambulance).\n\n"
            "I'm not a counsellor, but I'm always here to help with anything else."
        ),
    },

    # ------------------------------------------------------------------ weekly check-in
    "soc_checkin_intro": {
        "en": (
            "🗓️ *Weekly check-in*\n\n"
            "Every Friday evening I'll ask how your week was. Just reply *GOOD*, *OK* or *HARD*. "
            "I won't save your answers, only that check-ins are on. You can turn them off anytime."
        ),
    },
    "soc_checkin_on": {"en": "Check-ins are *on* 🔔"},
    "soc_checkin_off": {"en": "Check-ins are *off*."},
    "btn_checkin_on": {"en": "🔔 Turn on"},
    "btn_checkin_off": {"en": "🔕 Turn off"},
    "soc_checkin_turned_on": {"en": "🔔 Done! I'll check in every Friday evening."},
    "soc_checkin_turned_off": {"en": "🔕 Weekly check-ins are off."},
    "soc_checkin_msg": {"en": "👋 Rafiq here. How was your week? Reply *GOOD*, *OK* or *HARD*. (Type *stop* to pause messages.)"},
    "soc_mood_good": {"en": "😊 That's great to hear! Keep doing what's working. Want something fun for this weekend?"},
    "soc_mood_ok": {"en": "😐 Thanks for telling me. Some weeks are just OK. One small thing to look forward to can help: a call home, a walk, a free class."},
    "soc_mood_hard": {
        "en": "💛 I'm sorry this week was hard. Thank you for telling me. You don't have to carry it alone: talking to someone really helps, and it's free and confidential.",
    },

    # ------------------------------------------------------------------ crisis
    "soc_crisis": {
        "en": (
            "💛 I'm really glad you told me. You matter, and you don't have to go through this alone.\n\n"
            "🚨 *If you might act on these thoughts, or you're in danger now*, call *999* or *998*, or go to the nearest hospital emergency department.\n\n"
            "*Talk to someone now, free and confidential:*\n"
            "• *800 HOPE* (800 4673): call or WhatsApp, 9am to midnight.\n"
            "• *800 SAKINA* (800 725462): announced as open 24/7.\n\n"
            "If you can, reach out to someone you trust today: a friend, a coworker, or family back home.\n\n"
            "I'm still here. You can keep writing to me."
        ),
    },
}

S.update(STRINGS)
