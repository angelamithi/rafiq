"""Pay & Rights: all user-facing text and official sources.

Checked against current sources on 2026-11-19 (see README):
- Private sector: since 1 June 2026 (MOHRE Ministerial Resolution 340 of 2026)
  last month's salary is due on the 1st of each month through WPS; anything
  later is "delayed". Reminders to the employer from day 2, a formal warning on
  day 5, fines possible from day 11. Paying at least 85% counts as paid for
  WPS, without losing the right to the rest.
- Domestic workers: wages within 10 days of the due date (Federal Law 10 of
  2017 and its 2022 replacement), one paid rest day a week, 12 hours' daily
  rest (8 in a row), 30 days' annual leave, 30 days' sick leave (15 full, 15
  half pay), keep their own passport.
- Gratuity: 21 days' basic pay per year for the first 5 years, 30 days per
  year after, from 1 year of service, capped at 2 years' pay.
- Complaints: MOHRE app / website, 80084 (free), "My Salary Complaint" keeps
  your name from the employer.
Wording is fixed, never generated.
"""

from __future__ import annotations

from app.i18n import S

CHECKED_ON = "2026-11-19"

MOHRE = "https://www.mohre.gov.ae"

# Day of the month to ask "did you get your salary?" (the due day + a little time),
# and the follow-ups if it hasn't arrived. Domestic workers: 10 days after due date.
CHECKIN_DAYS = {"private": (3, 10, 17), "domestic": (11, 18)}

GRATUITY_MIN_SALARY = 100
GRATUITY_MAX_SALARY = 1_000_000
GRATUITY_MAX_YEARS = 50

STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ menu
    "menu_pay": {"en": "Pay & rights"},
    "menu_pay_d": {"en": "Short salary? Wage check, overtime, complaints"},
    "pay_m_wc": {"en": "Wage check"},
    "pay_m_wc_d": {"en": "Paid less than agreed? Work out what's owed"},
    "pay_menu": {"en": "💵 *Pay & rights*\nWhat do you need?"},
    "pay_m_watch": {"en": "Salary watch"},
    "pay_m_watch_d": {"en": "A monthly check that your salary arrived"},
    "pay_m_late": {"en": "My salary is late"},
    "pay_m_late_d": {"en": "What the law says and what to do now"},
    "pay_m_complaint": {"en": "Write a complaint"},
    "pay_m_complaint_d": {"en": "A ready-to-send draft for MOHRE"},
    "pay_m_rights": {"en": "Hours, leave & days off"},
    "pay_m_rights_d": {"en": "Overtime, rest days, annual and sick leave"},
    "pay_m_ot": {"en": "Overtime calculator"},
    "pay_m_ot_d": {"en": "What extra hours should pay, at least"},
    "pay_m_gratuity": {"en": "End-of-service pay"},
    "pay_m_gratuity_d": {"en": "Gratuity rules and a quick calculator"},
    "pay_m_proof": {"en": "Keep proof"},
    "pay_m_proof_d": {"en": "What to save in case there's a problem"},
    "btn_pay_menu": {"en": "Pay & rights"},
    "pay_footer": {"en": "Guidance, not legal advice. For your exact case, call MOHRE on *80084* (free)."},

    # ------------------------------------------------------------------ salary watch
    "pay_watch_intro": {
        "en": (
            "🔔 *Salary watch*\n\n"
            "Each month I'll ask if your salary arrived. You just reply *PAID*, *PART* or *NOT PAID*. "
            "I keep a simple record (only paid or not, never amounts), and if pay is late I'll tell you what to do and help you write a complaint."
        ),
    },
    "pay_watch_when_private": {"en": "Salaries are due on the *1st* of each month, so I'll ask on the 3rd."},
    "pay_watch_when_domestic": {"en": "Domestic workers must be paid within *10 days* of the due date, so I'll ask on the 11th."},
    "pay_watch_status_on": {"en": "Check-ins are *on* 🔔"},
    "pay_watch_status_off": {"en": "Check-ins are *off*."},
    "pay_watch_record": {"en": "*Your record*\n{lines}"},
    "pay_watch_record_empty": {"en": "*Your record*\nNothing yet."},
    "pay_watch_ask": {"en": "Did you get your salary for *{month}*?"},
    "pay_row_paid": {"en": "✅ Paid in full"},
    "pay_row_paid_d": {"en": "Got all of it"},
    "pay_row_part": {"en": "🟠 Only part"},
    "pay_row_part_d": {"en": "Some of it is missing"},
    "pay_row_unpaid": {"en": "🔴 Not paid yet"},
    "pay_row_unpaid_d": {"en": "Nothing has arrived"},
    "pay_row_on": {"en": "🔔 Turn check-ins on"},
    "pay_row_on_d": {"en": "I'll ask once a month"},
    "pay_row_off": {"en": "🔕 Turn check-ins off"},
    "pay_row_off_d": {"en": "Your record stays until you delete it"},
    "pay_watch_turned_on": {"en": "🔔 Salary check-ins are on. I'll ask once a month."},
    "pay_watch_turned_off": {"en": "🔕 Salary check-ins are off."},
    "pay_status_paid": {"en": "paid ✅"},
    "pay_status_part": {"en": "part 🟠"},
    "pay_status_unpaid": {"en": "not paid 🔴"},
    "pay_saved_paid": {"en": "✅ Saved: your *{month}* salary was paid in full. Great!"},
    "pay_saved_part": {"en": "🟠 Saved: only part of your *{month}* salary was paid."},
    "pay_saved_unpaid": {"en": "🔴 Saved: your *{month}* salary has not been paid."},
    "btn_write_complaint": {"en": "Write a complaint"},
    "btn_how_to_complain": {"en": "How to complain"},
    "btn_salary_watch": {"en": "Salary watch"},

    # ------------------------------------------------------------------ late salary
    "pay_late_private": {
        "en": (
            "⏰ *Late salary: what the law says*\n\n"
            "Since 1 June 2026, last month's salary is due on the *1st* of each month, through the Wage Protection System (WPS). Anything later counts as *delayed*.\n"
            "• From day 2, MOHRE sends your employer reminders.\n"
            "• On day 5, your employer gets a formal warning.\n"
            "• From day 11, your employer can be fined.\n"
            "• If you got at least 85%, WPS counts you as paid, but you still have the right to the rest.\n\n"
            "*What you can do now*\n"
            "1. Ask your employer or HR in writing (a message is fine) when you'll be paid. Keep the reply.\n"
            "2. Keep proof: payslips, bank or salary-card messages, your contract.\n"
            "3. Complain to MOHRE for free: in the MOHRE app, on the website, or call *80084*. The *My Salary Complaint* service keeps your name from your employer.\n\n"
            "Keep working normally while you wait, and don't sign any paper saying you were paid if you weren't."
        ),
    },
    "pay_late_domestic": {
        "en": (
            "⏰ *Late salary: domestic workers*\n\n"
            "Your employer must pay your salary, as written in your contract, within *10 days* of the date it's due.\n\n"
            "*What you can do now*\n"
            "1. Ask your employer politely, by message if you can, when you'll be paid. Keep the reply.\n"
            "2. Keep proof: your contract, and any bank or salary-card messages.\n"
            "3. If it isn't paid, complain to MOHRE for free: call *80084*, or use the MOHRE app or website. MOHRE tries to settle it, and domestic workers pay no court fees if it goes further.\n\n"
            "Your passport is yours: your employer must not keep it."
        ),
    },
    "pay_how_to_complain": {
        "en": (
            "📮 *How to complain to MOHRE* (free)\n\n"
            "• *MOHRE app* (App Store / Google Play): register a labour complaint, or use *My Salary Complaint* to keep your name from your employer.\n"
            "• *Website*: {mohre}\n"
            "• *Phone*: *80084*, the free labour claims and advice line.\n\n"
            "After you register, MOHRE usually contacts you within 14 days to try to settle it. Answer their calls: if you don't reply, the complaint can be closed.\n"
            "You'll need your Emirates ID or passport number, and your work permit (labour card) number if you have it."
        ),
    },

    # ------------------------------------------------------------------ complaint drafts
    "pay_complaint_pick": {"en": "📝 *Write a complaint*\nWhat is the problem? I'll write a draft you can copy into the MOHRE app."},
    "pay_c_unpaid": {"en": "Salary not paid"},
    "pay_c_unpaid_d": {"en": "Some or all of your salary is missing"},
    "pay_c_late": {"en": "Salary always late"},
    "pay_c_late_d": {"en": "Paid, but late again and again"},
    "pay_c_passport": {"en": "Employer kept passport"},
    "pay_c_passport_d": {"en": "Your passport is held against your will"},
    "pay_c_hours": {"en": "Hours or days off"},
    "pay_c_hours_d": {"en": "Too many hours, no rest day, unpaid overtime"},
    "pay_c_contract": {"en": "Different from contract"},
    "pay_c_contract_d": {"en": "Job, salary or conditions changed"},
    "pay_c_final": {"en": "Final pay missing"},
    "pay_c_final_d": {"en": "Gratuity, leave or last salary not paid"},
    "pay_draft_head": {"en": "Here's your draft 👇 Copy it, fill in the parts in [brackets], and send it in the MOHRE app or read it out on *80084*."},
    "pay_draft_tail": {"en": "🔒 I don't send anything for you, and I don't keep this draft. Only you decide whether to send it."},
    "pay_draft_body": {
        "en": (
            "To: Ministry of Human Resources and Emiratisation (MOHRE)\n"
            "Subject: Labour complaint – {subject}\n\n"
            "Name: {name}\n"
            "Emirates ID or passport number: [your number]\n"
            "Work permit (labour card) number: [if you have it]\n"
            "Employer: [company or employer name]\n"
            "Job: [your job title]\n\n"
            "{details}\n\n"
            "I request: {request}\n\n"
            "Proof I can provide: [for example: contract, payslips, bank messages, messages from my employer]\n\n"
            "Thank you."
        ),
    },
    "pay_d_unpaid_subject": {"en": "unpaid salary"},
    "pay_d_unpaid": {"en": "My salary has not been paid in full for: {months}. The amount owed is about AED [amount]. I asked my employer on [date] and have not been paid."},
    "pay_d_unpaid_none": {"en": "My salary has not been paid for [month(s)]. The amount owed is about AED [amount]. I asked my employer on [date] and have not been paid."},
    "pay_d_unpaid_request": {"en": "payment of all my unpaid salary."},
    "pay_d_late_subject": {"en": "salary repeatedly paid late"},
    "pay_d_late": {"en": "My salary is paid late again and again. For example: [month] was paid on [date], and [month] was paid on [date]."},
    "pay_d_late_request": {"en": "that my salary is paid on time every month through WPS."},
    "pay_d_passport_subject": {"en": "passport kept by employer"},
    "pay_d_passport": {"en": "My employer has kept my passport since [date] and does not give it back when I ask. I did not agree to this."},
    "pay_d_passport_request": {"en": "the return of my passport."},
    "pay_d_hours_subject": {"en": "working hours, rest days and overtime"},
    "pay_d_hours": {"en": "I work about [number] hours a day and [number] days a week. I do not get [a weekly rest day / overtime pay]. This has happened since [date]."},
    "pay_d_hours_request": {"en": "working hours and rest days as set by law and my contract, and payment for my overtime."},
    "pay_d_contract_subject": {"en": "conditions different from my contract"},
    "pay_d_contract": {"en": "My contract says [what the contract says], but in practice [what really happens]. This started on [date]."},
    "pay_d_contract_request": {"en": "that my employer follows the contract registered with MOHRE."},
    "pay_d_final_subject": {"en": "end-of-service dues not paid"},
    "pay_d_final": {"en": "My work ended on [date]. I have not received my [end-of-service gratuity / unused leave pay / last salary]. I worked for this employer from [start date]."},
    "pay_d_final_request": {"en": "payment of all my end-of-service dues."},
    "pay_name_placeholder": {"en": "[your full name as in your passport]"},

    # ------------------------------------------------------------------ rights
    "pay_rights_private": {
        "en": (
            "🕗 *Hours, leave & days off* (private sector)\n\n"
            "• *Hours*: normally up to 8 a day or 48 a week, 2 hours shorter in Ramadan.\n"
            "• *Overtime*: at most 2 extra hours a day, paid at least 25% more than your normal hourly pay.\n"
            "• *Breaks*: after 5 hours in a row, you get a rest break.\n"
            "• *Rest day*: at least one paid day off a week.\n"
            "• *Annual leave*: 30 days a year after one year; 2 days a month after your first 6 months. Unused leave is paid when you leave.\n"
            "• *Sick leave*: up to 90 days a year after probation: 15 full pay, 30 half pay, 45 unpaid.\n"
            "• Midday outdoor work is banned from 15 June to 15 September (12:30 to 3pm)."
        ),
    },
    "pay_rights_domestic": {
        "en": (
            "🕗 *Hours, leave & days off* (domestic workers)\n\n"
            "• *Daily rest*: at least 12 hours a day, including 8 hours in a row.\n"
            "• *Rest day*: one paid day off every week. If you work on it, you get another day off or a day's pay.\n"
            "• *Annual leave*: 30 paid days a year.\n"
            "• *Sick leave*: up to 30 days a year: 15 full pay, 15 half pay.\n"
            "• *Ticket home*: a return ticket every 2 years, paid by your employer.\n"
            "• Decent accommodation, meals and health insurance, paid by your employer.\n"
            "• Your passport and ID are yours to keep."
        ),
    },

    # ------------------------------------------------------------------ gratuity
    "pay_gratuity": {
        "en": (
            "🧾 *End-of-service pay (gratuity)*\n\n"
            "If you've worked at least *1 year* for the same employer, you get gratuity when you leave:\n"
            "• *21 days'* basic salary for each of the first 5 years\n"
            "• *30 days'* basic salary for each year after that\n"
            "• Part years count proportionally, and the total can't be more than 2 years' pay.\n\n"
            "It's based on your *basic* salary (without allowances).\n\n"
            "🧮 Want an estimate? Type your basic monthly salary and years worked, for example: *2000 3.5*"
        ),
    },
    "pay_gratuity_domestic": {
        "en": (
            "🧾 *End-of-service pay: domestic workers*\n\n"
            "Domestic workers have their own end-of-service rules, set by the domestic workers law and your contract. "
            "Ask MOHRE on *80084* (free) for your exact amount. Keep your contract and records of your start date."
        ),
    },
    "pay_gratuity_result": {
        "en": "🧮 With a basic salary of AED {salary} and {years} years, your gratuity is about *AED {amount}* ({days} days' basic pay).\n\nThis is an estimate: unpaid leave days and your contract can change it.",
    },
    "pay_gratuity_under_year": {"en": "🧮 Gratuity starts after 1 full year with the same employer. You've worked {years} years, so there's none yet."},
    "pay_gratuity_bad": {"en": "Please type your basic monthly salary and years worked, for example: *2000 3.5*"},

    # ------------------------------------------------------------------ proof
    "pay_proof": {
        "en": (
            "📁 *Keep proof*\n\n"
            "If there's ever a problem, proof makes MOHRE's job much easier.\n"
            "• A photo of your *contract* and your offer letter.\n"
            "• *Payslips*, and bank or salary-card messages each month.\n"
            "• *Messages* from your employer about pay, hours or leave. Don't delete them.\n"
            "• A simple *diary*: the days and hours you work, and your days off.\n"
            "• Save copies somewhere your employer can't reach, like your own email.\n\n"
            "⚠️ Don't secretly record people or take photos of them: that can break UAE privacy law. Your own documents and messages are enough."
        ),
    },

    # ------------------------------------------------------------------ check-in message (sent by the worker)
    "pay_checkin": {
        "en": "💵 Rafiq salary check: did you get your salary for {month}? Reply *PAID*, *PART* or *NOT PAID*. (Type *stop* to pause check-ins.)",
    },
    "pay_checkin_again": {
        "en": "💵 Rafiq: has your salary for {month} arrived now? Reply *PAID*, *PART* or *NOT PAID*. If not, type *salary late* to see what to do.",
    },
}

S.update(STRINGS)
