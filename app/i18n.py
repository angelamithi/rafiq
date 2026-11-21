"""All user-facing text.

Rafiq currently runs in English only. Every string is keyed by language code
("en"), so another language can be added later by adding a translation per key
and listing it in SUPPORTED_LANGUAGES.

UX rules for this file:
- Short messages: one idea per message, max ~6 lines before a question.
- Always end with a clear next step (a question, buttons or a command).
- Button titles <= 20 characters, list row titles <= 24, descriptions <= 72
  (WhatsApp limits; tests enforce them).
- Plain, simple English for readers who may use it as a second language.
  Bold (*text*) only for things the user can type.
"""

from __future__ import annotations

SUPPORTED_LANGUAGES = ("en",)
DEFAULT_LANGUAGE = "en"

S: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ welcome & consent
    "welcome": {
        "en": "Hi! I'm Rafiq 👋 I help people working in Dubai stay safe, legal and settled.",
    },
    "consent": {
        "en": (
            "Before we start, a quick note on privacy 🔒\n\n"
            "• I only save what you tell me here, to help you (like your visa expiry date for reminders).\n"
            "• Your details are encrypted. I will never sell or share them.\n"
            "• I give guidance, not legal advice.\n"
            "• You can see or delete your data anytime: type *my data* or *delete*.\n\n"
            "Do you agree?"
        ),
    },
    "consent_more": {
        "en": (
            "More detail 🔒\n\n"
            "• *What I save:* name (optional), home country, journey stage, visa type and expiry, work sector. If you use them: "
            "travel or arrival date, checklist ticks, salary record, check-ins on/off (never your answers), and for *Do it for me*: "
            "employer, salary, job start, rate alert, documents you save, a trusted contact's name and chat (they agree first).\n"
            "• *Not saved:* your messages, voice notes, or photos you don't save.\n"
            "• *Job offers, voice notes and messages I don't understand:* used to help you, then not kept. They may go to "
            "Google Gemini. Phone numbers and emails are removed from typed text; photos, PDFs and voice notes go as they are, "
            "so cover your passport or ID number.\n"
            "• *Who sees it:* only you and the Rafiq system. Never sold or shared.\n"
            "• *How long:* until you delete it, or {months} months without using Rafiq.\n"
            "• *Laws:* UAE Personal Data Protection Law, and Kenya's Data Protection Act.\n\n"
            "Do you agree?"
        ),
    },
    "consent_updated": {"en": "Our privacy notice has been updated. Please take a quick look:"},
    "consent_declined": {
        "en": "No problem. I haven't saved anything about you. If you change your mind, just send *hi*. 👋",
    },
    # ------------------------------------------------------------------ profile questions
    "ask_name": {"en": "Great! What should I call you? You can type a first name or a nickname."},
    "name_invalid": {"en": "Please send just a first name or nickname (letters only, up to 30)."},
    "ask_stage": {"en": "Nice to meet you{name_part}! Where are you in your journey?"},
    "ask_country": {"en": "Which country are you from?"},
    "ask_country_other": {"en": "Please type the name of your home country."},
    "country_invalid": {"en": "I couldn't recognise that. Please type the country name, for example *Rwanda*."},
    "ask_visa": {"en": "What UAE visa do you have right now?"},
    "ask_expiry": {
        "en": (
            "When does your visa expire? Send the date like *15/03/2027*.\n\n"
            "I'll remind you before it runs out, so you don't get overstay fines."
        ),
    },
    "expiry_invalid": {"en": "I couldn't read that date. Please use day/month/year, for example *15/03/2027*."},
    "expiry_past": {
        "en": (
            "That date has already passed. ⚠️ If your visa has expired, you may be charged fines for every extra day. "
            "Please check your status on the official ICP website and act soon: https://icp.gov.ae\n\n"
            "If you typed the wrong date, just send it again."
        ),
    },
    "expiry_too_far": {"en": "That date looks too far in the future. Please check it and send it again, for example *15/03/2027*."},
    "ask_sector": {"en": "What kind of work do you do (or want to do)?"},
    "summary": {
        "en": (
            "Here's what I have:\n\n"
            "👤 Name: {name}\n🧭 Stage: {stage}\n🌍 Home country: {country}\n"
            "🛂 Visa: {visa}\n📅 Visa expiry: {expiry}\n💼 Work: {sector}\n\n"
            "Is this correct?"
        ),
    },
    "profile_view": {
        "en": (
            "Your profile 👤\n\n"
            "Name: {name}\nStage: {stage}\nHome country: {country}\n"
            "Visa: {visa}\nVisa expiry: {expiry}\nWork: {sector}\n"
            "Reminders: {reminders}"
        ),
    },
    "edit_which": {"en": "What would you like to change?"},
    "saved": {"en": "Saved ✅"},
    "done": {"en": "You're all set, {name}! 🎉\nType *menu* anytime to see what I can do."},
    "done_no_name": {"en": "You're all set! 🎉\nType *menu* anytime to see what I can do."},
    # ------------------------------------------------------------------ menu & help
    "main_menu": {"en": "What would you like to do?"},
    "welcome_back": {"en": "Welcome back{name_part}! 👋 What would you like to do?"},
    "help": {
        "en": (
            "I'm Rafiq, your guide for working in Dubai.\n\n"
            "*You can type these anytime:*\n"
            "• *menu* – see what I can do\n"
            "• *profile* – your details\n"
            "• *my data* – see what I've saved\n"
            "• *delete* – delete everything\n"
            "• *checklist* – your before-you-fly checklist\n"
            "• *arrival* – your first weeks in the UAE\n"
            "• *salary late* / *complaint* – pay problems and your rights\n"
            "• *lonely* / *talk to someone* – friends & wellbeing\n"
            "• *send money* / *budget* / *loans* – money home\n"
            "• *stop* / *start* – pause or resume reminders\n"
            "🎙️ You can also send *voice notes* in your own language.\n\n"
            "*Emergencies in the UAE:*\n"
            "• Police: 999\n• Ambulance: 998\n• Fire: 997\n"
            "• Labour ministry (MOHRE): 80084\n\n"
            "I give guidance, not legal advice. For serious problems, contact the authorities or a lawyer."
        ),
    },
    "paused": {"en": "Reminders paused 🔕 I won't message you unless you write first. Type *start* to turn them back on."},
    "resumed": {"en": "Reminders are back on 🔔"},
    # ------------------------------------------------------------------ privacy
    "privacy_menu": {"en": "Privacy & your data 🔒\nYour details are encrypted and belong to you. What would you like to do?"},
    "export": {"en": "Here is everything I have saved about you:\n\n{data}\n\nI don't keep your messages, photos or voice notes."},
    "delete_confirm": {"en": "⚠️ This will permanently delete everything I've saved about you. It can't be undone.\n\nAre you sure?"},
    "deleted": {"en": "Done. I've deleted all your data. 👋\nIf you ever need me again, just send *hi*."},
    "delete_cancelled": {"en": "Okay, nothing was deleted 👍"},
    "delete_expired": {"en": "That confirmation has expired. Type *delete* if you still want to delete your data."},
    # ------------------------------------------------------------------ fallbacks & safety
    "media_not_yet": {"en": "Thanks! I can't use photos or videos here. Please type your answer, or send a voice note 🙏"},
    "didnt_understand": {"en": "Sorry, I didn't understand that. I'm still learning! 🙂 Here's what I can help with right now:"},
    "use_buttons": {"en": "Please tap one of the options below 👇"},
    "blocked": {"en": "I can't help with that request. I'm here to help you work and live safely in the UAE. Type *menu* to see what I can do."},
    "cooldown": {"en": "I've paused our chat for a while because of repeated unsafe requests. Please try again in {minutes} minutes."},
    "rate_limited": {"en": "You're sending messages very quickly. Please wait a minute and try again 🙏"},
    "too_long": {"en": "That message is a bit long for me. Please send it in shorter parts (up to {max} characters)."},
    "error": {"en": "Sorry, something went wrong on my side. Please try again in a moment."},
    "not_set": {"en": "Not set"},
    "on": {"en": "On"},
    "off": {"en": "Paused"},
    # ------------------------------------------------------------------ buttons & list labels
    "btn_agree": {"en": "Yes, I agree"},
    "btn_more": {"en": "Tell me more"},
    "btn_decline": {"en": "No, thanks"},
    "btn_skip": {"en": "Skip"},
    "btn_skip_for_now": {"en": "Skip for now"},
    "btn_correct": {"en": "All correct ✅"},
    "btn_edit": {"en": "Edit something"},
    "btn_edit_details": {"en": "Edit details"},
    "btn_menu": {"en": "Back to menu"},
    "btn_choose": {"en": "Choose"},
    "btn_menu_open": {"en": "Menu"},
    "btn_see_data": {"en": "See my data"},
    "btn_delete_data": {"en": "Delete my data"},
    "btn_yes_delete": {"en": "Yes, delete"},
    "btn_no_keep": {"en": "No, keep it"},
    "menu_profile": {"en": "My profile"},
    "menu_profile_d": {"en": "Your details, privacy and your data"},
    "menu_privacy": {"en": "Privacy & my data"},
    "menu_privacy_d": {"en": "See, download or delete your data"},
    "menu_help": {"en": "Help & emergencies"},
    "menu_help_d": {"en": "Important numbers and how I work"},
    "field_name": {"en": "Name"},
    "field_stage": {"en": "Journey stage"},
    "field_country": {"en": "Home country"},
    "field_visa": {"en": "Visa type"},
    "field_expiry": {"en": "Visa expiry date"},
    "field_sector": {"en": "Work"},
    "field_consent": {"en": "Privacy consent"},
    "field_joined": {"en": "Joined"},
    "rule_review_notice": {
        "en": "ℹ️ An official source for this topic changed recently and our team is checking it. Please double-check the official link before you act.",
    },
    "field_travel_date": {"en": "Travel date"},
    "field_checklist": {"en": "Checklist items ticked"},
    "field_arrival_date": {"en": "Arrival date"},
    "field_arrival_checklist": {"en": "Arrival steps ticked"},
    "field_salary_watch": {"en": "Salary check-ins"},
    "field_salary_record": {"en": "Salary record"},
    "field_wellbeing": {"en": "Weekly check-ins"},
    "country_other": {"en": "Other"},
    # ------------------------------------------------------------------ Module 2: Job Safety
    "menu_job": {"en": "Check a job offer"},
    "menu_job_d": {"en": "Spot scams before you pay or travel"},
    "job_intro": {
        "en": (
            "🛡️ *Job offer check*\n\n"
            "Paste the job offer or the recruiter's message here, or send a photo or PDF of it, and I'll check it for scam warning signs.\n\n"
            "Tip: include everything they sent you: salary, visa, fees and contact details."
        ),
    },
    "job_auto": {"en": "This looks like a job offer, so I checked it for you 👇"},
    "job_media": {"en": "I can't watch videos or stickers. Please send a photo or PDF of the offer, paste its text, or send a voice note 🙏"},
    # ------------------------------------------------------------------ Language & Voice
    "voice_heard": {"en": "🎙️ I heard: “{text}”"},
    "intent_guess": {"en": "🤔 I think you're asking about *{topic}*. Here's what I have 👇 (Not right? Type *menu*.)"},
    "voice_needs_consent": {
        "en": "🎙️ I can listen to voice notes once you've agreed to the privacy notice (they're written down by our AI provider). Please type *hi* to start.",
    },
    "voice_off": {"en": "🎙️ I can't listen to voice notes right now. Please type your message 🙏"},
    "voice_limit": {"en": "🎙️ You've sent a lot of voice notes today. Please type for now; voice notes work again tomorrow 🙂"},
    "voice_err_too_large": {"en": "🎙️ That voice note is too long. Please keep it under 3 minutes, or type your message."},
    "voice_err_too_long": {"en": "🎙️ That voice note is too long. Please keep it under 3 minutes, or type your message."},
    "voice_err_unsupported_type": {"en": "🎙️ I couldn't play that audio. Please send a normal voice note, or type your message."},
    "voice_err_no_speech": {"en": "🎙️ I couldn't hear any words. Please try again somewhere quieter, or type your message."},
    "voice_err_ai_unavailable": {"en": "🎙️ Sorry, I can't listen to voice notes right now. Please type your message 🙏"},
    "voice_err_read_failed": {"en": "🎙️ Sorry, I couldn't understand that voice note. Please try again, or type your message."},
    "voice_err_download_failed": {"en": "🎙️ I couldn't download that voice note. Please send it again, or type your message."},
    "doc_read_note": {"en": "📄 I read your {kind}. If I misread anything, paste the text and I'll check it again."},
    "doc_pages_skipped": {"en": "(I read the first {n} pages.)"},
    "doc_kind_photo": {"en": "photo"},
    "doc_kind_pdf": {"en": "PDF"},
    "doc_not_offer": {"en": "I read your {kind}, but it doesn't look like a job offer. To check an offer, send its text, a photo or a PDF of it. Type *menu* to see what else I can do."},
    "doc_err_unsupported_type": {"en": "I can only read photos (JPG or PNG) and PDF files. Please send one of those, or paste the text."},
    "doc_err_too_large": {"en": "That file is too big for me (max {mb} MB). Please send a smaller photo or PDF, or paste the text."},
    "doc_err_encrypted": {"en": "That PDF is password-protected, so I can't open it. Please send a photo of it or paste the text."},
    "doc_err_no_text": {"en": "I couldn't find any readable text. Please send a clearer photo (good light, whole page in view) or paste the text."},
    "doc_err_ai_unavailable": {"en": "I can't read photos right now. Please paste the text of the offer and I'll check it straight away."},
    "doc_err_read_failed": {"en": "Sorry, I couldn't open that file. Please send it again, or paste the text."},
    "doc_err_download_failed": {"en": "Sorry, I couldn't open that file. Please send it again, or paste the text."},
    "job_too_short": {"en": "That's a bit short for me to check. Please paste the full offer or the recruiter's message."},
    "job_risk_high": {"en": "🔴 *High risk*\nThis offer shows signs of a scam."},
    "job_risk_medium": {"en": "🟠 *Be careful*\nSome things in this offer need checking."},
    "job_risk_low": {"en": "🟢 *No common warning signs found*\nThat's a good sign, but always check before you pay or travel."},
    "job_found": {"en": "*What I found:*"},
    "job_details_title": {"en": "*From the offer:*"},
    "job_not_mentioned": {"en": "*Not mentioned:* {items}. Ask about these before you accept."},
    "job_todo": {"en": "*What to do now:*"},
    "job_todo_dont_pay": {"en": "• Don't pay any money and don't send your original passport."},
    "job_todo_offer_letter": {"en": "• Ask for an official MOHRE offer letter to sign before you travel: {link}"},
    "job_todo_agency": {"en": "• Check the agency is licensed on the {name}: {link}"},
    "job_todo_agency_generic": {"en": "• Check the agency is licensed with your country's labour or emigration ministry."},
    "job_todo_ask": {"en": "• Ask the employer the questions I suggest (tap *Questions to ask*)."},
    "job_disclaimer": {"en": "This check looks for common warning signs. It can't prove an offer is real, and it isn't legal advice."},
    "job_next": {"en": "What would you like to do next?"},
    "job_questions": {
        "en": "Send these questions to the employer or agency. A real employer will answer them clearly:\n\n{questions}",
    },
    "job_agency": {
        "en": (
            "🏢 *How to check a recruitment agency*\n\n"
            "{country_line}\n"
            "• Ask for the agency's licence number and look it up on the official list.\n"
            "• Make sure the UAE employer is real: ask for its trade licence and a MOHRE offer letter ({mohre}).\n"
            "• Never pay an agency that isn't on the official list.\n\n"
            "I can't check licences myself yet, so always use the official site."
        ),
    },
    "agency_country_line": {"en": "• You're from {country}: check the {name}: {link}"},
    "agency_country_generic": {"en": "• Check your country's official list of licensed recruitment agencies (your labour or emigration ministry)."},
    "btn_questions": {"en": "Questions to ask"},
    "btn_check_another": {"en": "Check another"},
    "btn_check_offer": {"en": "Check an offer"},
    "btn_check_agency": {"en": "Check an agency"},
    "flag_hidden_title": {"en": "Hidden instructions in the text"},
    "flag_hidden_detail": {"en": "This message contains text written to trick AI tools. That's unusual for a real job offer."},
    "detail_employer": {"en": "Employer"},
    "detail_job_title": {"en": "Job"},
    "detail_salary": {"en": "Salary"},
    "detail_working_hours": {"en": "Hours"},
    "detail_days_off": {"en": "Days off"},
    "detail_contract_length": {"en": "Contract"},
    "detail_accommodation": {"en": "Accommodation"},
    "detail_visa_type": {"en": "Visa"},
    "missing_salary": {"en": "salary"},
    "missing_hours": {"en": "working hours"},
    "missing_days_off": {"en": "days off"},
    "missing_contract": {"en": "contract length"},
    "missing_accommodation": {"en": "accommodation"},
    "missing_leave": {"en": "annual leave"},
    "q_salary": {"en": "What is the monthly salary in AED? Is that the basic salary or the total?"},
    "q_hours": {"en": "How many hours a day and how many days a week will I work?"},
    "q_days_off": {"en": "How many days off will I get each week?"},
    "q_contract": {"en": "How long is the contract?"},
    "q_accommodation": {"en": "Is accommodation, food and transport provided?"},
    "q_leave": {"en": "How many days of paid annual leave will I get?"},
    "q_offer_letter": {"en": "Will I sign a MOHRE offer letter before I travel?"},
    "q_visa": {"en": "Will I travel on an employment visa (not a visit visa)?"},
    "q_costs": {"en": "Who pays for the visa, medical tests and flight?"},
    "q_passport": {"en": "Will I keep my passport with me?"},
    "q_company": {"en": "What is the company's full name and trade licence number?"},
}

STAGES: dict[str, dict[str, tuple[str, str]]] = {
    "planning": {"en": ("Planning to go", "Looking for work in the UAE")},
    "offer": {"en": ("I have a job offer", "Preparing to travel")},
    "arrived": {"en": ("Just arrived", "In the UAE less than 3 months")},
    "resident": {"en": ("Living in the UAE", "More than 3 months")},
}

VISAS: dict[str, dict[str, str]] = {
    "none": {"en": "No UAE visa yet"},
    "visit": {"en": "Visit / tourist visa"},
    "employment": {"en": "Work / residence visa"},
    "other": {"en": "Other / not sure"},
}
VISAS_WITH_EXPIRY = {"visit", "employment"}

SECTORS: dict[str, dict[str, str]] = {
    "hospitality": {"en": "Hotels & restaurants"},
    "construction": {"en": "Construction"},
    "domestic": {"en": "Domestic work"},
    "retail": {"en": "Shops & retail"},
    "security": {"en": "Security"},
    "transport": {"en": "Driving & delivery"},
    "health": {"en": "Healthcare & care"},
    "office": {"en": "Office & IT"},
    "other": {"en": "Other"},
}

# Common home countries of UAE workers. Anything else can be typed via "Other".
COUNTRIES: dict[str, dict[str, str]] = {
    "India": {"en": "India"},
    "Pakistan": {"en": "Pakistan"},
    "Bangladesh": {"en": "Bangladesh"},
    "Philippines": {"en": "Philippines"},
    "Nepal": {"en": "Nepal"},
    "Kenya": {"en": "Kenya"},
    "Uganda": {"en": "Uganda"},
    "Nigeria": {"en": "Nigeria"},
    "Egypt": {"en": "Egypt"},
}

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}


def lang_or_default(lang: str | None) -> str:
    return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def t(key: str, lang: str | None = None, **kwargs: object) -> str:
    entry = S[key]
    text = entry.get(lang_or_default(lang)) or entry["en"]
    return text.format(**kwargs) if kwargs else text


def fmt_date(d, lang: str | None = None) -> str:  # type: ignore[no-untyped-def]
    return f"{d.day} {MONTHS[lang_or_default(lang)][d.month - 1]} {d.year}"
