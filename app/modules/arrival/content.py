"""Arrival Guide: all user-facing text and official sources.

Checked against current sources on 2026-11-19 (see README). Wording is fixed,
never generated. Every link is on the output guard's allow-list.
"""

from __future__ import annotations

from app.i18n import S

CHECKED_ON = "2026-11-19"

MOHRE = "https://www.mohre.gov.ae"
ICP_SMART = "https://smartservices.icp.gov.ae"
GDRFA = "https://www.gdrfad.gov.ae"
ILOE = "https://www.iloe.ae"
DLD = "https://dubailand.gov.ae"

RESIDENCY_DAYS = 30          # residence procedures within one month of entry (u.ae)
REMINDER_DAYS_SINCE = (21, 28)
MAX_DAYS_AGO = 365

# Typed topics that open one step directly ("emirates id", "ejari"...).
TOPICS: dict[str, set[str]] = {
    "sim": {"sim", "sim card", "get a sim", "phone number", "mobile line", "esim"},
    "residency": {"emirates id", "eid", "medical test", "medical fitness", "residence visa", "residency", "biometrics"},
    "contract": {"work contract", "my contract", "mohre contract", "labour contract", "employment contract"},
    "insurance": {"health insurance", "medical insurance", "insurance card"},
    "iloe": {"iloe", "job loss insurance", "unemployment insurance", "ilo e"},
    "bank": {"bank", "bank account", "salary account", "open bank account", "open a bank account", "wps", "salary card"},
    "housing": {"housing", "rent", "renting", "ejari", "bed space", "bedspace", "partition", "room", "find a room",
                "accommodation", "apartment"},
    "apps": {"uae pass", "uaepass", "apps", "official apps", "mohre app"},
}

STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ menu & overview
    "menu_arrive": {"en": "Your first weeks"},
    "menu_arrive_d": {"en": "Emirates ID, SIM, bank, insurance and housing"},
    "arr_title": {"en": "🛬 *Your first weeks in the UAE*"},
    "arr_intro": {"en": "Your steps for settling in. Tap one to see what to do, then mark it done."},
    "arr_not_yet": {"en": "Not in the UAE yet? Start with *Before you fly*. This list is for after you land."},
    "arr_day": {"en": "📍 Day {n} in the UAE (you arrived on {date})."},
    "arr_progress": {"en": "{bar} *{done} of {total}* done"},
    "arr_next": {"en": "Next up: *{item}*. Tap it in the list when you're ready."},
    "arr_all_done": {"en": "🎉 You've done every step. Welcome to the UAE! Type *menu* anytime if something comes up."},
    "arr_marked": {"en": "✅ Done: *{item}*."},
    "arr_unmarked": {"en": "↩️ *{item}* is back on your list."},
    "arr_row_date": {"en": "🗓️ Set arrival date"},
    "arr_row_date_change": {"en": "🗓️ Change arrival date"},
    "arr_row_date_d": {"en": "I'll show your residence visa deadline"},
    "btn_arr_list": {"en": "📋 My first weeks"},
    "btn_my_visa": {"en": "My visa"},
    "btn_check_contract": {"en": "Check my contract"},
    "arr_tip": {"en": "🛬 Just arrived? Tap *Your first weeks* in the menu for your settling-in steps."},

    # ------------------------------------------------------------------ arrival date
    "arr_ask_date": {"en": "🗓️ When did you arrive in the UAE? Type the date, for example *{example}*."},
    "arr_date_saved": {"en": "Saved 👍"},
    "arr_date_removed": {"en": "Arrival date removed."},
    "arr_date_skipped": {"en": "No problem. Tap *Set arrival date* whenever you like."},
    "arr_date_bad": {"en": "Sorry, I couldn't read that date. Please type it like *{example}*."},
    "arr_date_future": {"en": "That date is in the future. Please type the day you landed in the UAE."},
    "arr_date_old": {
        "en": "That's more than a year ago, so your residence visa should already be done. You can check it in *My visa*.",
    },
    "arr_deadline": {"en": "🗓️ Finish your medical test and Emirates ID by about *{due}* ({days} days left)."},
    "arr_deadline_today": {"en": "🗓️ About 30 days have passed since you arrived: your residence visa should be finished *now*."},
    "arr_deadline_over": {
        "en": "⚠️ It's been more than 30 days since you arrived ({date}). Ask your employer today about your residence visa, and check your status on the official site.",
    },

    # ------------------------------------------------------------------ item titles (≤22 chars: a ✅ is added)
    "arr_i_sim": {"en": "SIM card"},
    "arr_i_sim_d": {"en": "A visitor line now, a resident line later"},
    "arr_i_residency": {"en": "Medical & Emirates ID"},
    "arr_i_residency_d": {"en": "Finish your residence visa within 30 days"},
    "arr_i_visit": {"en": "Your visa status"},
    "arr_i_visit_d": {"en": "A visit visa doesn't let you work"},
    "arr_i_contract": {"en": "Work contract"},
    "arr_i_contract_d": {"en": "Read it before you sign, and keep a copy"},
    "arr_i_insurance": {"en": "Health insurance"},
    "arr_i_insurance_d": {"en": "Your employer must provide it and pay for it"},
    "arr_i_iloe": {"en": "Job-loss insurance"},
    "arr_i_iloe_d": {"en": "ILOE: your own subscription, AED 400 fine if missed"},
    "arr_i_bank": {"en": "Bank / salary account"},
    "arr_i_bank_d": {"en": "Where your salary is paid (WPS)"},
    "arr_i_housing": {"en": "Safe housing"},
    "arr_i_housing_d": {"en": "Check before you pay rent or a deposit"},
    "arr_i_apps": {"en": "Official apps"},
    "arr_i_apps_d": {"en": "UAE Pass, MOHRE and your visa status"},
    "arr_i_rights": {"en": "Your rights at work"},
    "arr_i_rights_d": {"en": "Passport, salary, rest days and complaints"},

    # ------------------------------------------------------------------ item details
    "arr_sim": {
        "en": (
            "📱 *SIM card*\n\n"
            "• Right after you land you can get a *visitor line* with your passport and visa, at the airport or any e& or du shop. It lasts as long as your visa.\n"
            "• Once you have your Emirates ID, switch to a *resident* line (prepaid or postpaid) at an e& or du shop.\n"
            "• A SIM is registered to *your* identity. Never buy one for someone else, and never lend your passport or Emirates ID for one: anything done with that number is traced to you.\n"
            "• Use the same number for your bank, MOHRE and UAE Pass."
        ),
    },
    "arr_residency": {
        "en": (
            "🩺 *Medical test & Emirates ID*\n\n"
            "Your entry permit only lets you in. Within *1 month* of arriving, your residence visa must be finished:\n"
            "1. *Medical fitness test* at an approved centre (it checks for infectious diseases such as TB).\n"
            "2. *Emirates ID*: fingerprints and a photo at a service centre.\n"
            "3. Your residence visa is issued, then your Emirates ID card arrives.\n\n"
            "• Your employer arranges this and pays for it.\n"
            "• Your employer may need your passport for a short time for this. Ask for it back afterwards: keeping it is illegal.\n"
            "• Check your status anytime: {icp} (Dubai visas: {gdrfa})"
        ),
    },
    "arr_visit": {
        "en": (
            "⚠️ *Your visa status*\n\n"
            "Your profile says you're on a *visit visa*. You can't work on a visit visa, not even for a trial. "
            "If you have a job, your employer must get your work permit and change your status, and pay for it.\n\n"
            "• Don't start work until your permit is issued.\n"
            "• Check your visa and its expiry: {icp} (Dubai visas: {gdrfa})\n"
            "• If your visa has changed, update it in *profile*."
        ),
    },
    "arr_contract": {
        "en": (
            "📝 *Your work contract*\n\n"
            "• Your contract is registered with the Ministry of Human Resources (MOHRE), and you sign it. *Read it first.*\n"
            "• Job, salary, hours, days off and leave must match what you were promised. If they don't, don't sign yet: ask questions first.\n"
            "• Keep your own copy (a photo is fine). You can usually also see it in the MOHRE app or website.\n"
            "• Never sign a blank page, or anything you can't read.\n\n"
            "Send me the contract (text, photo or PDF) and I'll check it for warning signs.\n"
            "MOHRE: {mohre}"
        ),
    },
    "arr_insurance": {
        "en": (
            "🏥 *Health insurance*\n\n"
            "• Since January 2025, every private-sector employer in the UAE must give you health insurance *and pay for it*. This includes domestic workers.\n"
            "• It's needed before your residence visa is issued or renewed.\n"
            "• The cost must not be taken from your salary.\n"
            "• Ask for your insurance card or policy number, and save a photo of it in your phone.\n"
            "• In an emergency, go to hospital or call *998* for an ambulance."
        ),
    },
    "arr_iloe": {
        "en": (
            "🛡️ *Job-loss insurance (ILOE)*\n\n"
            "This one is *your* job, not your employer's.\n"
            "• Most private-sector workers must subscribe within *4 months* of getting their work permit. If you don't, the fine is *AED 400*.\n"
            "• It costs about *AED 5 or 10 a month*, depending on your salary.\n"
            "• If you lose your job through no fault of your own, after at least 12 months of subscription, it pays part of your salary for up to 3 months.\n"
            "• Domestic workers are not part of this scheme.\n"
            "• Subscribe only on the official site or app: {iloe}"
        ),
    },
    "arr_iloe_exempt": {
        "en": "🛡️ *Job-loss insurance (ILOE)*\n\nDomestic workers are not part of the ILOE scheme, so there's nothing to do here. Your employer must still give you health insurance.",
    },
    "arr_bank": {
        "en": (
            "🏦 *Bank or salary account*\n\n"
            "• Most UAE salaries are paid through the *Wage Protection System (WPS)*, into a bank account or salary card in *your* name.\n"
            "• Most banks need your Emirates ID. Some accept the Emirates ID application receipt, so you can start sooner.\n"
            "• Your card, PIN and banking app are yours alone. Never give them to anyone, including your employer or agent.\n"
            "• Check every payment: your salary should arrive in full and on time.\n"
            "• Banks never ask for your PIN or one-time code by phone or message."
        ),
    },
    "arr_housing": {
        "en": (
            "🏠 *Safe housing*\n\n"
            "If your employer gives you accommodation, most of this doesn't apply. If you rent:\n"
            "• See the place in person before paying anything, and get a receipt for every payment.\n"
            "• In Dubai, check the agent's licence and the property's title deed in the *Dubai REST* app, and make sure your contract is registered with *Ejari*. A landlord who delays Ejari is a warning sign.\n"
            "• Since 2026, shared rooms and bed spaces in Dubai need a Dubai Municipality permit. Ask: \"Does this place have a permit?\" Illegal partitions can be closed, and tenants can be fined too.\n"
            "• Never pay a deposit for a place you've only seen on WhatsApp or social media.\n\n"
            "Dubai Land Department: {dld}"
        ),
    },
    "arr_apps": {
        "en": (
            "📲 *Official apps*\n\n"
            "• *UAE Pass*: your official digital ID for government services. Set it up once you have your Emirates ID.\n"
            "• *MOHRE*: your work permit, your contract, and complaints about salary or your employer.\n"
            "• *ICP* (or *GDRFA* for Dubai visas): your visa and residency status.\n"
            "• Download apps only from the official app stores. Never share your UAE Pass PIN or one-time codes.\n\n"
            "{mohre}\n{icp}\n{gdrfa}"
        ),
    },
    "arr_rights": {
        "en": (
            "⚖️ *Your rights at work*\n\n"
            "• Your *passport* is yours. Your employer can't keep it.\n"
            "• Your *salary* must be paid on time and in full.\n"
            "• You must not pay for your visa, work permit or recruitment.\n"
            "• You have weekly rest days and paid annual leave, as set by law and your contract.\n"
            "• Problems? Call MOHRE on *80084* or use the MOHRE app. You don't need your employer's permission to complain.\n\n"
            "MOHRE: {mohre}"
        ),
    },

    # ------------------------------------------------------------------ reminders
    "arr_reminder": {
        "en": "🩺 Rafiq: you arrived {n} days ago. Your medical test and Emirates ID should be done by about {due}. If they aren't, ask your employer now. Type *arrival* for help.",
    },
}

S.update(STRINGS)
