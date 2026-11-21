"""Departure Planner: all user-facing text and official sources.

Checked against current sources on 2026-11-19 (see README). Wording is fixed,
never generated. Every link is on the output guard's allow-list.
"""

from __future__ import annotations

from app.i18n import S

CHECKED_ON = "2026-11-19"

U_AE_PREPARING = "https://u.ae/en/information-and-services/jobs/employment-in-the-private-sector/preparing-to-work"
ICP_SMART = "https://smartservices.icp.gov.ae"
GDRFA = "https://www.gdrfad.gov.ae"
EDE = "https://www.ede.gov.ae"

# Exit clearance a worker needs from their OWN country before flying out for a job.
CLEARANCE_LINKS: dict[str, str] = {
    "Kenya": "https://labour.go.ke/foreign-contracts-serviceattestation",
    "India": "https://www.emigrate.gov.in",
    "Philippines": "https://www.dmw.gov.ph",
    "Pakistan": "https://beoe.gov.pk",
    "Nepal": "https://dofe.gov.np",
    "Bangladesh": "https://www.bmet.gov.bd",
    "Uganda": "https://mglsd.go.ug",
}
NEA_AGENCIES = "https://neaims.go.ke/EmploymentAgencyList.aspx"

REMINDER_DAYS = (7, 1)
MAX_DAYS_AHEAD = 366

STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ menu
    "menu_plan": {"en": "Before you fly"},
    "menu_plan_d": {"en": "Your personal checklist for moving to the UAE"},
    "plan_title": {"en": "✈️ *Before you fly*"},
    "plan_intro": {"en": "Your checklist for moving to the UAE. Tap an item to see what to do, then mark it done."},
    "plan_next": {"en": "Next up: *{item}*. Tap it in the list when you're ready."},
    "plan_intro_here": {"en": "You're already in the UAE, so most of this is behind you. It's still handy for a friend or relative who's coming."},
    "plan_progress": {"en": "{bar} *{done} of {total}* done"},
    "plan_flying": {"en": "🗓️ You fly on *{date}*: {days} days to go."},
    "plan_flying_tomorrow": {"en": "🗓️ You fly *tomorrow* ({date})."},
    "plan_flying_today": {"en": "🗓️ You fly *today* ({date}). Safe travels! 🧳"},
    "plan_flying_past": {"en": "🗓️ Your travel date ({date}) has passed. Arrived? Welcome! You can change the date if your plans moved."},
    "plan_marked": {"en": "✅ Done: *{item}*."},
    "plan_unmarked": {"en": "↩️ *{item}* is back on your list."},
    "plan_all_done": {
        "en": "🎉 Everything is ticked off. Keep your passport, documents and medicines in your hand luggage, and safe travels! When you land, type *menu* and I'll help with your first weeks.",
    },
    "plan_row_date": {"en": "🗓️ Set travel date"},
    "plan_row_date_change": {"en": "🗓️ Change travel date"},
    "plan_row_date_d": {"en": "I'll remind you 7 days and 1 day before you fly"},
    "btn_plan_done": {"en": "✅ Mark as done"},
    "btn_plan_undo": {"en": "↩️ Not done yet"},
    "btn_plan_list": {"en": "📋 My checklist"},
    "btn_check_offer": {"en": "Check my offer"},
    "btn_check_medicine": {"en": "Check a medicine"},
    "btn_can_i_work": {"en": "Can I work?"},
    "btn_plan_not_sure": {"en": "Not sure yet"},
    "btn_plan_remove_date": {"en": "Remove date"},

    # ------------------------------------------------------------------ travel date
    "plan_ask_date": {
        "en": "🗓️ When do you fly? Type the date, for example *15/01/2027*.\n\nI'll remind you 7 days and 1 day before, with anything still left on your list.",
    },
    "plan_date_saved": {"en": "Saved 👍"},
    "plan_date_removed": {"en": "Travel date removed. No travel reminders will be sent."},
    "plan_date_skipped": {"en": "No problem. Tap *Set travel date* whenever you know it."},
    "plan_date_bad": {"en": "Sorry, I couldn't read that date. Please type it like *15/01/2027*."},
    "plan_date_past": {"en": "That date has already passed. Please type the day you fly, for example *15/01/2027*."},
    "plan_date_far": {"en": "That's more than a year away. Please check the date, or tap *Not sure yet*."},
    "plan_date_after_permit": {
        "en": "⚠️ Remember: a work entry permit is valid for *2 months* from the day it's issued. Make sure you land before it runs out.",
    },

    # ------------------------------------------------------------------ item titles (≤22 chars: a ✅ is added)
    "plan_i_passport": {"en": "Passport (6+ months)"},
    "plan_i_passport_d": {"en": "Valid 6+ months when you land, with blank pages"},
    "plan_i_permit": {"en": "Entry permit"},
    "plan_i_permit_d": {"en": "Your work visa: real, valid, and paid by the employer"},
    "plan_i_visit": {"en": "The right visa"},
    "plan_i_visit_d": {"en": "A visit visa doesn't let you work"},
    "plan_i_contract": {"en": "Contract checked"},
    "plan_i_contract_d": {"en": "Signed, matches the offer, no fees"},
    "plan_i_clearance": {"en": "Exit clearance"},
    "plan_i_clearance_d": {"en": "What your own country needs before you leave"},
    "plan_i_medicines": {"en": "Medicines checked"},
    "plan_i_medicines_d": {"en": "Some common medicines are controlled in the UAE"},
    "plan_i_health": {"en": "Medical & certificates"},
    "plan_i_health_d": {"en": "Medical tests and attested certificates"},
    "plan_i_copies": {"en": "Copies & contacts"},
    "plan_i_copies_d": {"en": "Backups of documents, and who to call"},
    "plan_i_money": {"en": "Money plan"},
    "plan_i_money_d": {"en": "No fees, cash for the first weeks, payday"},
    "plan_i_pack": {"en": "Packing"},
    "plan_i_pack_d": {"en": "Clothes, hand luggage and what not to carry"},

    # ------------------------------------------------------------------ item details
    "plan_passport": {
        "en": (
            "🛂 *Passport*\n\n"
            "• It must be valid for at least *6 months* when you enter the UAE, with blank pages for stamps.\n"
            "• If it runs out sooner, renew it *before* you apply for the visa. Renewing from abroad is slower.\n"
            "• Keep your passport yourself. In the UAE it's illegal for an employer or agent to keep it.\n\n"
            "Source: {u_ae}"
        ),
    },
    "plan_permit": {
        "en": (
            "📄 *Entry permit (work visa)*\n\n"
            "Your employer applies for it, not you. It usually comes by email.\n"
            "• It's valid for *2 months* from the day it was issued, so you must land before then.\n"
            "• After you arrive, your residence visa (medical test and Emirates ID) is done within *1 month*.\n"
            "• Check it's real on the official site before you book a flight: {icp} (Dubai visas: {gdrfa}).\n"
            "• Don't pay for it. By UAE law, recruitment and visa costs are paid by the employer.\n\n"
            "Source: {u_ae}"
        ),
    },
    "plan_visit": {
        "en": (
            "⚠️ *The right visa*\n\n"
            "Your profile says you have a *visit visa*. A visit visa does *not* allow you to work in the UAE: "
            "not for a trial, and not \"while your papers are processed\". Working on it can mean fines, a ban and deportation.\n\n"
            "• If you have a job offer, the employer must get you a *work entry permit*, and pay for it.\n"
            "• Be careful if an agent says \"come on a visit visa and we'll change it later\". It's a common trap.\n"
            "• If your visa type has changed, update it in *profile*."
        ),
    },
    "plan_contract": {
        "en": (
            "📝 *Your contract*\n\n"
            "• Get a *signed copy* before you travel, in a language you understand.\n"
            "• Check it matches what you were promised: job, salary, hours, days off and housing.\n"
            "• You should pay *no recruitment fees*.\n"
            "• Never sign a blank page, or a new contract at the airport.\n\n"
            "Send me the offer (text, photo or PDF) and I'll check it for warning signs."
        ),
    },
    "plan_clearance_Kenya": {
        "en": (
            "🇰🇪 *Exit clearance: Kenya*\n\n"
            "• Get your employment contract *attested* by the State Department for Labour before you travel. A labour officer checks it's fair and that you agreed to it freely.\n"
            "• Complete the government *pre-departure training*.\n"
            "• Use only an agency licensed by the National Employment Authority: {nea}\n\n"
            "Official info: {link}"
        ),
    },
    "plan_clearance_India": {
        "en": (
            "🇮🇳 *Exit clearance: India*\n\n"
            "• If your passport is *ECR* (Emigration Check Required) and you're going to work in the UAE, you need *emigration clearance* on eMigrate before you fly.\n"
            "• With an *ECNR* passport you don't need it.\n"
            "• Use only a recruiting agent registered on eMigrate.\n\n"
            "Official site: {link}"
        ),
    },
    "plan_clearance_Philippines": {
        "en": (
            "🇵🇭 *Exit clearance: Philippines*\n\n"
            "• You need the *OEC*, now the digital *OFW Pass*, from the Department of Migrant Workers. Immigration checks it when you leave.\n"
            "• Your contract must be verified, and first-time workers attend the pre-departure orientation (PDOS).\n"
            "• Leaving for work on a tourist visa counts as undocumented: don't do it.\n\n"
            "Official site: {link}"
        ),
    },
    "plan_clearance_Pakistan": {
        "en": (
            "🇵🇰 *Exit clearance: Pakistan*\n\n"
            "• Every worker going abroad on a work visa needs *Protector* registration (the protector stamp) from the Bureau of Emigration & Overseas Employment.\n"
            "• Apply online (e-Protector) or at a Protector of Emigrants office. You may also need a *PakSkills* certificate first.\n"
            "• Without it, you can be stopped at the airport.\n\n"
            "Official site: {link}"
        ),
    },
    "plan_clearance_Nepal": {
        "en": (
            "🇳🇵 *Exit clearance: Nepal*\n\n"
            "• Get your *final labour approval* (Shram Swikriti) from the Department of Foreign Employment *before* you go to the airport.\n"
            "• Without it, immigration won't let you leave for work.\n"
            "• Keep the receipts for the welfare fund and insurance.\n\n"
            "Official site: {link}"
        ),
    },
    "plan_clearance_Bangladesh": {
        "en": (
            "🇧🇩 *Exit clearance: Bangladesh*\n\n"
            "• Register with BMET and complete the *3-day pre-departure orientation*.\n"
            "• Get your *BMET emigration clearance card* (the QR \"smart card\"). Immigration checks it at the airport.\n"
            "• Use only a BMET-licensed agency.\n\n"
            "Official site: {link}"
        ),
    },
    "plan_clearance_Uganda": {
        "en": (
            "🇺🇬 *Exit clearance: Uganda*\n\n"
            "• Go only through an agency licensed by the Ministry of Gender, Labour and Social Development. Tour and travel companies are not allowed to send workers.\n"
            "• Complete the *pre-departure orientation* (14 days for domestic workers) and get your clearance before you travel.\n"
            "• Domestic workers should not pay recruitment fees.\n\n"
            "Official site: {link}"
        ),
    },
    "plan_clearance_other": {
        "en": (
            "🌍 *Exit clearance*\n\n"
            "Many countries ask workers to register, or get clearance, before leaving for a job abroad.\n"
            "• Ask your country's *labour ministry* what you need. Don't rely only on your agent.\n"
            "• Keep every official receipt and certificate with your travel documents.\n"
            "• Save your embassy's contact details for the UAE."
        ),
    },
    "plan_medicines": {
        "en": (
            "💊 *Medicines*\n\n"
            "Some common medicines (strong painkillers, sleeping pills, some anxiety medicines) are *controlled* in the UAE. "
            "Bringing them without a permit can lead to arrest.\n"
            "• Check each medicine with me before you pack.\n"
            "• Carry a doctor's prescription from the last 3 months for everything you bring.\n"
            "• For controlled medicines, apply for the free e-permit from the Emirates Drug Establishment before you fly: {ede}"
        ),
    },
    "plan_health": {
        "en": (
            "🩺 *Medical & certificates*\n\n"
            "• In the UAE you'll have a *medical test* for your residence visa. It checks for infectious diseases such as TB and HIV.\n"
            "• Your country or agency may also ask for a medical before you leave. Use only the clinic named in the official process, and keep the receipt.\n"
            "• If your job needs a degree or diploma, get it *attested* at home before you fly. It's much harder to do from the UAE.\n"
            "• Bring your vaccination record and any medical reports.\n\n"
            "Source: {u_ae}"
        ),
    },
    "plan_copies": {
        "en": (
            "📂 *Copies & contacts*\n\n"
            "• Take photos of your passport, entry permit, contract and ticket. Save them somewhere safe online, and leave copies with your family.\n"
            "• Give your family your employer's name, address and phone number, and your agent's details.\n"
            "• Agree a time to check in with family every week, so they know quickly if something's wrong.\n"
            "• Save these UAE numbers: Police *999*, Ambulance *998*, Labour ministry (MOHRE) *80084*.\n"
            "• Save the number of your country's embassy or consulate in the UAE."
        ),
    },
    "plan_money": {
        "en": (
            "💵 *Money*\n\n"
            "• Don't pay recruitment or visa fees. If you already paid, keep every receipt.\n"
            "• Bring some cash for your first weeks (food, SIM card, transport) until your first salary.\n"
            "• Ask when payday is. Most UAE salaries are paid through the official Wage Protection System, into a bank account or salary card.\n"
            "• Send money home only through banks or licensed exchange companies, never through people you don't know.\n"
            "• If you borrowed money to travel, write down what you owe and when."
        ),
    },
    "plan_pack": {
        "en": (
            "🧳 *Packing*\n\n"
            "• Light, breathable clothes: it's very hot from May to September. Bring a light jacket for air-conditioning and winter evenings.\n"
            "• Modest clothes for malls, public places and government offices.\n"
            "• Passport, documents and medicines go in your *hand luggage*, never in checked bags.\n"
            "• UAE plugs are the 3-pin UK type (230V). Bring an adapter if you need one.\n"
            "• Never carry a bag or parcel for someone else. You're responsible for everything in your luggage."
        ),
    },

    # ------------------------------------------------------------------ reminders
    "plan_reminder": {
        "en": "✈️ Rafiq: you fly in {days} days ({date}). Still on your list: {left}. Type *checklist* to see it. Safe travels!",
    },
    "plan_reminder_1": {
        "en": "✈️ Rafiq: you fly tomorrow ({date}). Still on your list: {left}. Type *checklist* to see it. Safe travels!",
    },
    "plan_reminder_done": {
        "en": "✈️ Rafiq: you fly in {days} days ({date}) and your checklist is complete 🎉 Keep your passport, documents and medicines in your hand luggage.",
    },
    "plan_reminder_done_1": {
        "en": "✈️ Rafiq: you fly tomorrow ({date}) and your checklist is complete 🎉 Keep your passport, documents and medicines in your hand luggage.",
    },
    "plan_tip": {"en": "✈️ Getting ready to travel? Tap *Before you fly* in the menu for your personal checklist."},
}

S.update(STRINGS)
