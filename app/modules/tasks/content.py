""""Do it for me": tasks Rafiq carries out for the user, not just answers.

Rule for every task: Rafiq prepares, the user confirms, and Rafiq only acts on
the user's own things, or towards a person the user chose who agreed to it.
Rafiq never contacts an employer, agency or government office for anyone.
"""

from __future__ import annotations

from app.i18n import S

CHECKED_ON = "2026-11-21"

MOHRE = "https://www.mohre.gov.ae"
MOHRE_PHONE = "80084"
FX_SOURCE_NAME = "open.er-api.com (ExchangeRate-API)"

# ---------------------------------------------------------------- limits
VAULT_MAX_DOCS = 12
VAULT_MAX_BYTES = 5_000_000
VAULT_KINDS = ("passport", "visa", "eid", "contract", "offer", "other")
VAULT_REMIND_DAYS = (90, 30, 7)      # before a saved document expires
SOS_PER_HOUR = 3
SOS_INVITE_HOURS = 48
JOIN_ATTEMPTS_PER_DAY = 5
RATE_MIN_UP_PCT = 0.5
RATE_MAX_UP_PCT = 20.0
PACK_MAX_SALARY = 200_000
FORM_FIELD_MAX = 120

STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ menu
    "menu_tasks": {"en": "Do it for me"},
    "menu_tasks_d": {"en": "Letters, wage records, document safe, SOS, alerts"},
    "tasks_menu": {"en": (
        "🧰 *Do it for me*\n"
        "I can do these jobs for you. I prepare everything and you decide. "
        "I never contact your employer, agency or any office for you."
    )},
    "task_m_pack": {"en": "Unpaid wages pack"},
    "task_m_pack_d": {"en": "A PDF of what you're owed, ready for MOHRE"},
    "task_m_vault": {"en": "My documents"},
    "task_m_vault_d": {"en": "Safe copies of passport, visa, ID + expiry alerts"},
    "task_m_sos": {"en": "Trusted contact (SOS)"},
    "task_m_sos_d": {"en": "One tap alerts someone you trust if you're in danger"},
    "task_m_rate": {"en": "Rate alert"},
    "task_m_rate_d": {"en": "I tell you when it's a good day to send money"},
    "task_m_forms": {"en": "Letters & forms"},
    "task_m_forms_d": {"en": "Leave, passport return, salary certificate..."},
    "task_m_contract": {"en": "Contract switch check"},
    "task_m_contract_d": {"en": "Is your contract the job you were promised?"},
    "task_m_status": {"en": "What I'm doing for you"},
    "task_m_status_d": {"en": "Your reminders, alerts and saved items"},
    "btn_tasks": {"en": "🧰 Do it for me"},
    "btn_skip": {"en": "Skip"},
    "btn_cancel": {"en": "Cancel"},
    "btn_yes_correct": {"en": "Yes, correct"},
    "btn_change_date": {"en": "Change date"},
    "btn_no_date": {"en": "No expiry date"},
    "task_cancelled": {"en": "OK, cancelled. Nothing was saved or sent."},
    "task_needs_consent": {"en": "I can only do tasks for you after you agree to the privacy note. Type *menu* to see it."},

    # ------------------------------------------------------------------ status
    "status_head": {"en": "📋 *What I'm doing for you*"},
    "status_none": {"en": "Nothing yet. Pick a task below and I'll start working for you."},
    "status_visa": {"en": "⏰ Visa reminders before {date}"},
    "status_travel": {"en": "✈️ Departure checklist: {done}/{total} done"},
    "status_arrival": {"en": "🛬 Arrival checklist: {done}/{total} done"},
    "status_pay": {"en": "💰 Monthly salary check-ins (on)"},
    "status_unpaid": {"en": "⚠️ Months recorded as not fully paid: {n}"},
    "status_social": {"en": "💬 Weekly wellbeing check-ins (on)"},
    "status_vault": {"en": "🗂️ {n} saved document(s), expiry alerts on"},
    "status_vault_next": {"en": "   Next to expire: {kind} on {date}"},
    "status_sos": {"en": "🆘 Trusted contact: {name}"},
    "status_sos_pending": {"en": "🆘 Trusted contact: waiting for {name} to accept"},
    "status_rate": {"en": "💱 Rate alert: 1 AED ≥ {target} {cur}"},

    # ------------------------------------------------------------------ evidence pack
    "pack_intro": {"en": (
        "📄 *Unpaid wages pack*\n"
        "I'll make a PDF you can show at MOHRE, to a lawyer or your embassy: the months you weren't paid, "
        "what you're owed, your end-of-service estimate and a complaint letter.\n\n"
        "3 quick questions first. *What is your employer's company name?* (as on your contract)"
    )},
    "pack_ask_salary": {"en": "What is your *monthly salary* in AED, as written in your contract? (just the number, e.g. *1500*)"},
    "pack_bad_salary": {"en": "Please type just the monthly amount in AED, e.g. *1500*."},
    "pack_ask_start": {"en": "When did you *start* this job? (e.g. *03/2024* or *March 2024*)"},
    "pack_bad_start": {"en": "I didn't get that date. Try *03/2024* or *March 2024*."},
    "pack_ask_months": {"en": (
        "Which months were you *not paid*? Type them like *September, October* "
        "(add *half* after a month if you got only part, e.g. *August half*)."
    )},
    "pack_bad_months": {"en": "I couldn't find any months. Type them like *September, October 2026*."},
    "pack_ready": {"en": (
        "✅ *Your unpaid wages pack is ready.*\n"
        "• Months not paid: {unpaid}\n"
        "• Months part-paid: {part}\n"
        "• Owed (unpaid months): about *AED {owed}*\n"
        "• End-of-service estimate: {gratuity}\n\n"
        "Take it to MOHRE (call *80084* or use the MOHRE app), a lawyer or your embassy. "
        "Keep your payslips and bank statements with it. "
        "I updated your salary record too, so the next pack is quicker."
    )},
    "pack_caption": {"en": "📄 Your unpaid wages pack (PDF)"},
    "pack_no_unpaid": {"en": "Your salary record shows every month as paid. 👍 If that's wrong, tell me which months were missed."},
    "pack_title": {"en": "Unpaid wages record"},
    "pack_subtitle": {"en": "Prepared with Rafiq on {date}. Information given by the worker; amounts are estimates."},
    "pack_footer": {"en": "Made with Rafiq. Not a legal document. Check figures with MOHRE (80084) or a lawyer."},
    "pack_h_worker": {"en": "1. Worker and job"},
    "pack_h_months": {"en": "2. Salary record"},
    "pack_h_owed": {"en": "3. Amount owed (estimate)"},
    "pack_h_rights": {"en": "4. The rules that apply"},
    "pack_h_next": {"en": "5. What to do next"},
    "pack_h_letter": {"en": "6. Complaint letter"},
    "pack_rights_private": {"en": (
        "UAE Labour Law (Federal Decree-Law No. 33 of 2021): wages must be paid on time through the Wage Protection "
        "System. Since 1 June 2026, a month's salary is due on the 1st of the next month and any later payment counts "
        "as delayed; MOHRE starts action against the employer from the 2nd day. "
        "End-of-service gratuity is due after one year of continuous work: 21 days' basic pay per year for the first "
        "five years and 30 days per year after that. Source: MOHRE, mohre.gov.ae (checked {checked})."
    )},
    "pack_rights_domestic": {"en": (
        "UAE Domestic Workers Law (Federal Decree-Law No. 9 of 2022, Article 15): the monthly wage must be paid in "
        "dirhams within 10 working days of the due date. End-of-service pay is due after one year of service. "
        "Source: MOHRE, mohre.gov.ae (checked {checked})."
    )},
    "pack_next": {"en": (
        "1. Talk to the employer in writing first if it is safe, and keep a copy.\n"
        "2. File a complaint: MOHRE app or website, or call 80084. Domestic workers can also go to a Tadbeer centre.\n"
        "3. Bring: this record, your contract, Emirates ID or passport copy, payslips, bank statements, messages.\n"
        "4. If the case is not settled, MOHRE refers it to the Labour Court. Filing is free for most workers' claims.\n"
        "5. Filing a complaint is your legal right, and your employer is not allowed to keep your passport."
    )},
    "pack_letter": {"en": (
        "To: Ministry of Human Resources and Emiratisation (MOHRE)\n"
        "Subject: Complaint about unpaid wages\n\n"
        "I, {name}, work for {employer} since {start} with a monthly salary of AED {salary}. "
        "I have not received my full salary for: {months}. "
        "The unpaid amount is about AED {owed}.\n\n"
        "I ask MOHRE to help me receive my unpaid wages and all my rights under UAE law.\n\n"
        "Name: {name}\nEmirates ID / passport number: ____________\nPhone: ____________\n"
        "Signature: ____________   Date: {date}"
    )},
    "pack_status_unpaid": {"en": "Not paid"},
    "pack_status_part": {"en": "Part paid"},
    "pack_status_paid": {"en": "Paid"},
    "pack_col_month": {"en": "Month"},
    "pack_col_status": {"en": "Status"},
    "pack_col_owed": {"en": "Owed (AED)"},
    "pack_to_confirm": {"en": "to confirm"},
    "pack_under_year": {"en": "Not yet due (under 1 year of work)"},
    "pack_gratuity_val": {"en": "about AED {amount} ({years} years)"},
    "pack_employer_unknown": {"en": "[employer name]"},

    # ------------------------------------------------------------------ vault
    "vault_head": {"en": (
        "🗂️ *My documents*\n"
        "Keep safe copies of your passport, visa, Emirates ID and contract here. If someone takes your passport, "
        "you still have proof. I'll remind you before anything expires.\n🔒 Files are encrypted. Only you can get them back."
    )},
    "vault_list_head": {"en": "Saved ({n}/{max}). Tap one to get your copy back:"},
    "vault_empty": {"en": "Nothing saved yet."},
    "btn_vault_add": {"en": "➕ Save a document"},
    "btn_vault_open": {"en": "Choose"},
    "vault_pick_kind": {"en": "Which document is it?"},
    "vault_k_passport": {"en": "Passport"},
    "vault_k_visa": {"en": "Visa / residence"},
    "vault_k_eid": {"en": "Emirates ID"},
    "vault_k_contract": {"en": "Work contract"},
    "vault_k_offer": {"en": "Job offer"},
    "vault_k_other": {"en": "Other document"},
    "vault_send_photo": {"en": "📸 Send a clear photo or PDF of your *{kind}* now (the page with the expiry date)."},
    "vault_need_file": {"en": "Please send it as a *photo* or *PDF*. Or tap Cancel."},
    "vault_full": {"en": "You have {max} documents saved, the most I can keep. Delete one first."},
    "vault_too_big": {"en": "That file is too big (max 5 MB). Try a photo instead of a scan."},
    "vault_bad_file": {"en": "I can only save photos (JPG/PNG) and PDFs."},
    "vault_download_failed": {"en": "I couldn't download that file. Please send it again."},
    "vault_found_expiry": {"en": "I read the expiry date as *{date}*. Is that right?"},
    "vault_ask_expiry": {"en": "What is the *expiry date*? (e.g. *15/03/2028*) Or tap *No expiry date*."},
    "vault_bad_date": {"en": "I didn't get that date. Try *15/03/2028*, or tap *No expiry date*."},
    "vault_saved": {"en": "✅ Saved your *{kind}*. {remind}"},
    "vault_saved_remind": {"en": "I'll remind you 90, 30 and 7 days before {date}."},
    "vault_saved_no_remind": {"en": "No expiry date, so no reminders."},
    "vault_saved_expired": {"en": "⚠️ This expired on {date}. Renew it as soon as you can."},
    "vault_visa_synced": {"en": "I also set this as your visa expiry, so your visa reminders use it."},
    "vault_doc_caption": {"en": "🗂️ Your {kind}{expiry}"},
    "vault_doc_expiry": {"en": " (expires {date})"},
    "btn_vault_delete": {"en": "🗑️ Delete it"},
    "vault_deleted": {"en": "🗑️ Deleted. That copy is gone."},
    "vault_not_found": {"en": "I couldn't find that document. It may have been deleted."},
    "vault_reminder": {"en": "🗂️ Your *{kind}* expires on *{date}* ({days} days). Start the renewal now so you're never without valid papers."},
    "vault_reminder_soon": {"en": "⚠️ Your *{kind}* expires on *{date}*, in {days} days. Please renew it this week."},

    # ------------------------------------------------------------------ SOS
    "sos_intro": {"en": (
        "🆘 *Trusted contact*\n"
        "Choose one person you trust: family, a friend or a community leader. If you're ever in danger, "
        "one tap sends them an alert with your location and your embassy's details.\n\n"
        "They must agree first: I'll give you an invite to forward to them.\n\n*What is their name?*"
    )},
    "sos_invite": {"en": (
        "✅ Now forward the message below to *{name}*. When they send the code to Rafiq, they're your trusted contact. "
        "The invite works for {hours} hours."
    )},
    "sos_invite_card": {"en": (
        "{owner} chose you as their trusted contact on Rafiq, a safety assistant for workers in the UAE.\n"
        "If they ever need help, Rafiq will message you.\n\n"
        "To accept, send this message to Rafiq: JOIN {code}{link}"
    )},
    "sos_invite_link_tg": {"en": "\nOr open: https://t.me/{bot}?start=join_{code}"},
    "sos_invite_link_wa": {"en": "\nOr open: https://wa.me/{number}?text=JOIN%20{code}"},
    "sos_joined_contact": {"en": (
        "✅ You're now *{owner}'s* trusted contact. If they send an SOS, I'll message you here.\n"
        "I only keep your chat address for this, encrypted. To stop at any time, send *stop sos*."
    )},
    "sos_joined_owner": {"en": "✅ *{name}* accepted. They're now your trusted contact. In danger? Type *sos* or tap Help."},
    "sos_bad_code": {"en": "That code didn't work. It may have expired. Ask your friend to send a new invite."},
    "sos_own_code": {"en": "That's your own invite. Forward it to the person you trust."},
    "sos_join_limit": {"en": "Too many tries. Please wait until tomorrow."},
    "sos_left": {"en": "✅ Done. You're no longer anyone's trusted contact. I deleted your chat address."},
    "sos_not_contact": {"en": "You're not anyone's trusted contact on Rafiq."},
    "sos_owner_removed": {"en": "ℹ️ {name} is no longer your trusted contact. Set up a new one in *Do it for me*."},
    "sos_have_contact": {"en": "🆘 Your trusted contact is *{name}*. In danger? Tap *Send SOS* and I'll alert them right away."},
    "sos_pending": {"en": "⏳ Waiting for *{name}* to accept your invite. You can send it again or change the person."},
    "btn_sos_send": {"en": "🆘 Send SOS"},
    "btn_sos_change": {"en": "Change person"},
    "btn_sos_remove": {"en": "Remove contact"},
    "btn_sos_reinvite": {"en": "Send invite again"},
    "btn_sos_setup": {"en": "Set up contact"},
    "btn_sos_now": {"en": "Send now"},
    "btn_sos_location": {"en": "📍 Add location"},
    "sos_no_contact": {"en": (
        "You don't have a trusted contact yet. In danger right now? Call *999* (police).\n"
        "Set up a trusted contact so next time one tap alerts them."
    )},
    "sos_confirm": {"en": "🆘 Send an SOS to *{name}* now? Add your location so they can find you."},
    "sos_ask_location": {"en": (
        "📍 Share your location: tap 📎 (attach), then *Location*, then *Send your current location*.\n"
        "Or tap *Send now* to alert them without it."
    )},
    "sos_alert": {"en": (
        "🚨 *SOS from {owner}* (sent via Rafiq)\n"
        "{owner} says they need help and may be in danger.{where}\n\n"
        "What you can do:\n"
        "• Call or message them now.\n"
        "• If you can't reach them and you're in the UAE, call police on *999*.\n"
        "• From abroad, contact their country's embassy in the UAE{embassy}.\n"
        "• Dubai Police Human Trafficking crimes control centre: *800 7283*."
    )},
    "sos_where": {"en": "\n📍 Location: https://maps.google.com/?q={lat},{lon}"},
    "sos_where_none": {"en": "\n(No location was shared.)"},
    "sos_embassy": {"en": ": {url}"},
    "sos_sent": {"en": (
        "✅ SOS sent to *{name}*. If you're in immediate danger, call *999* now.\n"
        "Need a safe place or help leaving? Call *800 7283* (Dubai Police, human trafficking and abuse)."
    )},
    "sos_limit": {"en": "You've sent {n} SOS alerts in the last hour. If you're in danger, call *999* now."},
    "sos_relay_failed": {"en": "⚠️ I couldn't reach your contact just now. If you're in danger, call *999*."},
    "sos_location_nostep": {"en": "📍 Got your location. I don't keep it. Do you want to send an SOS with it to your trusted contact?"},
    "sos_location_nocontact": {"en": "📍 Got your location. I don't keep it. You haven't set up a trusted contact yet."},
    "sos_bad_name": {"en": "Please type just their name (letters only), e.g. *Amina*."},
    "sos_removed": {"en": "Removed. {name} won't get your alerts any more."},

    # ------------------------------------------------------------------ rates
    "rate_head": {"en": (
        "💱 *Rate alert*\nToday 1 AED = *{rate} {cur}* (mid-market rate, {source}, updated {updated}).\n"
        "Transfer companies give a bit less than this, so compare before you send.\n\n"
        "Want me to tell you when it goes up?"
    )},
    "rate_unavailable": {"en": "I can't get today's exchange rate right now. Please try again later."},
    "rate_no_currency": {"en": "Which currency do you send money in? Type its 3-letter code, e.g. *KES*, *INR*, *PHP*."},
    "rate_bad_currency": {"en": "I don't know that currency. Type a 3-letter code like *KES*, *INR*, *PKR*, *PHP*."},
    "btn_rate_1": {"en": "+1% higher"},
    "btn_rate_2": {"en": "+2% higher"},
    "btn_rate_own": {"en": "My own number"},
    "btn_rate_cancel": {"en": "Stop the alert"},
    "rate_ask_target": {"en": "Type the rate you're waiting for, e.g. *{example}* (1 AED = ? {cur})."},
    "rate_bad_target": {"en": "Please type a number between {low} and {high}."},
    "rate_set": {"en": "✅ Done. I'll message you when 1 AED reaches *{target} {cur}* (today {rate}). I check a few times a day."},
    "rate_current_alert": {"en": "Your alert: 1 AED ≥ *{target} {cur}*."},
    "rate_stopped": {"en": "✅ Rate alert stopped."},
    "rate_hit": {"en": (
        "💱 Good news! 1 AED = *{rate} {cur}* today. That's at or above your target of {target}.\n"
        "Compare a couple of exchange houses or apps before you send. Type *compare* for help."
    )},

    # ------------------------------------------------------------------ forms
    "forms_head": {"en": "✍️ *Letters & forms*\nI ask a few questions, then make a ready-to-print letter (PDF). You decide whether to send it."},
    "form_passport": {"en": "Ask for my passport back"},
    "form_passport_d": {"en": "Employers may not keep your passport"},
    "form_leave": {"en": "Annual leave request"},
    "form_leave_d": {"en": "Ask for your paid holiday in writing"},
    "form_salary_cert": {"en": "Salary certificate"},
    "form_salary_cert_d": {"en": "For a bank, rent or embassy"},
    "form_resign": {"en": "Resignation notice"},
    "form_resign_d": {"en": "Give notice the legal way"},
    "form_payslip": {"en": "Ask for payslips"},
    "form_payslip_d": {"en": "Proof of what you've been paid"},
    "form_q_employer": {"en": "What is your employer's company name?"},
    "form_q_manager": {"en": "Who should it go to? (e.g. *HR Manager* or a name)"},
    "form_q_job": {"en": "What is your job title?"},
    "form_q_start": {"en": "When did you start this job? (e.g. *03/2024*)"},
    "form_q_leave_from": {"en": "First day of leave? (e.g. *01/12/2026*)"},
    "form_q_leave_to": {"en": "Last day of leave? (e.g. *21/12/2026*)"},
    "form_q_purpose": {"en": "What is it for? (e.g. *opening a bank account*)"},
    "form_q_last_day": {"en": "Your planned last working day? (e.g. *31/12/2026*)"},
    "form_q_months": {"en": "Which months do you need payslips for? (e.g. *August to October 2026*)"},
    "form_q_reason": {"en": "Why do you need your passport? (e.g. *to travel home*, *to renew it*)"},
    "form_bad_date": {"en": "I didn't get that date. Try *01/12/2026*."},
    "form_bad_text": {"en": "Please type a short answer (up to 120 characters)."},
    "form_ready": {"en": "✅ Your letter is ready. Print or send it yourself, and keep a copy (a photo of it signed is fine)."},
    "form_caption": {"en": "✍️ {title} (PDF)"},
    "form_tip_passport": {"en": (
        "ℹ️ Keeping a worker's passport is not allowed in the UAE. If your employer refuses, "
        "you can report it to MOHRE (*80084*) or the police."
    )},
    "form_tip_resign": {"en": (
        "ℹ️ Check the notice period in your contract (usually 30 to 90 days). You keep your right to end-of-service pay. "
        "Type *gratuity* to estimate it."
    )},
    "letter_footer": {"en": "Prepared with Rafiq. Check the details before you sign."},

    # ------------------------------------------------------------------ contract switch
    "contract_intro": {"en": (
        "🔍 *Contract switch check*\n"
        "Some workers are promised one job at home, then asked to sign a worse contract in the UAE. "
        "That's called contract substitution and it's against UAE law.\n\n"
        "Step 1: send a photo/PDF of the *offer you were promised*, or paste its text."
    )},
    "contract_use_saved": {"en": "You saved a job offer in My documents. Use that one?"},
    "btn_use_saved": {"en": "Use saved offer"},
    "btn_send_new": {"en": "Send a new one"},
    "contract_ask_contract": {"en": "Got it ✅ Step 2: now send the *contract you are asked to sign* (photo, PDF or text)."},
    "contract_unreadable": {"en": "I couldn't read that. Please send a clearer photo, a PDF, or paste the text."},
    "contract_no_terms": {"en": "I couldn't find the salary or job title in that. Please send the page that shows them."},
    "contract_head": {"en": "🔍 *Offer vs contract*"},
    "contract_row": {"en": "• {label}: offer *{offer}* → contract *{contract}* {mark}"},
    "contract_lbl_salary": {"en": "Salary (AED/month)"},
    "contract_lbl_job": {"en": "Job title"},
    "contract_lbl_hours": {"en": "Hours per day"},
    "contract_lbl_leave": {"en": "Annual leave (days)"},
    "contract_lbl_years": {"en": "Contract length (years)"},
    "contract_unknown": {"en": "not found"},
    "contract_bad": {"en": (
        "⛔ *The contract is worse than the offer.* This may be contract substitution.\n"
        "• Don't sign under pressure. You may ask for time to read it.\n"
        "• Keep both documents (I can save them in *My documents*).\n"
        "• Call MOHRE on *80084*. The terms registered with MOHRE are the ones that count."
    )},
    "contract_ok": {"en": (
        "✅ I didn't find anything worse in the contract on these points. Still read every page, "
        "and never sign a page that is blank or in a language you can't read."
    )},
    "contract_partial": {"en": "⚠️ I couldn't compare everything. Check the points marked 'not found' yourself."},
    "contract_note": {"en": "I read these automatically, so check the numbers yourself. I don't keep the documents unless you save them."},
    "btn_save_docs": {"en": "Save both"},
    "contract_saved": {"en": "✅ Saved both in *My documents*."},

    # ------------------------------------------------------------------ export labels
    "field_employer": {"en": "Employer"},
    "field_monthly_salary": {"en": "Monthly salary"},
    "field_job_start": {"en": "Job start"},
    "field_trusted_contact": {"en": "Trusted contact"},
    "field_rate_alert": {"en": "Rate alert"},
    "field_vault": {"en": "Saved documents: open *My documents* to see or delete them"},
}

S.update(STRINGS)
