"""Stay Legal: all user-facing text and official sources.

Every rule here was checked against current sources on 2026-11-19 (see
README). Wording is fixed, never generated, and each answer links to the
authority's own site. Registered into app.i18n so t() works everywhere.
"""

from __future__ import annotations

from app.i18n import S

CHECKED_ON = "2026-11-19"

MOHRE = "https://www.mohre.gov.ae"
GDRFA = "https://www.gdrfad.gov.ae"
ICP_SMART = "https://smartservices.icp.gov.ae"
EDE = "https://www.ede.gov.ae"
U_AE_PART_TIME = "https://u.ae/en/information-and-services/jobs/working-for-two-employers-at-one-time"

OVERSTAY_FINE_PER_DAY = 50   # AED, unified for all visa types (ICP)
REMINDER_DAYS = (30, 14, 7, 3, 1, 0, -1)

STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ menu
    "menu_legal": {"en": "Stay legal"},
    "menu_legal_d": {"en": "Visa, work, medicines and everyday rules"},
    "legal_menu": {"en": "⚖️ *Stay legal*\nWhat would you like to check?"},
    "legal_visa": {"en": "My visa"},
    "legal_visa_d": {"en": "Days left, reminders and fines"},
    "legal_work": {"en": "Can I work?"},
    "legal_work_d": {"en": "Visit visas, side jobs and permits"},
    "legal_med": {"en": "Medicine check"},
    "legal_med_d": {"en": "Is my medicine allowed in the UAE?"},
    "legal_post": {"en": "Can I post this?"},
    "legal_post_d": {"en": "Photos, videos and news online"},
    "legal_rules": {"en": "Everyday rules"},
    "legal_rules_d": {"en": "Laws newcomers often break by mistake"},
    "btn_legal_menu": {"en": "Stay legal menu"},
    "legal_footer": {"en": "Guidance, not legal advice. Rules can change, so check the official site."},

    # ------------------------------------------------------------------ my visa
    "visa_none": {
        "en": "🛂 *My visa*\n\nI don't have your visa expiry date yet. Add it and I'll remind you before it runs out, so you never pay overstay fines.",
    },
    "visa_ok": {"en": "🟢 Your {visa} expires on *{date}*: {days} days left."},
    "visa_soon": {"en": "🟠 Your {visa} expires on *{date}*: only {days} days left. Start renewing now (ask your employer for a work visa), or plan to leave before then."},
    "visa_urgent": {"en": "🔴 Your {visa} expires on *{date}*: {days} days left. Renew or leave the UAE before then."},
    "visa_today": {"en": "🔴 Your {visa} expires *today* ({date}). Renew or leave today to avoid fines."},
    "visa_expired": {
        "en": (
            "⛔ Your {visa} expired on *{date}*, {days} days ago.\n"
            "Overstay fines are AED {per_day} per day, so you may already owe about *AED {owed}*. "
            "Check your exact fine and status now, then renew or leave as soon as possible."
        ),
    },
    "visa_reminders_on": {"en": "🔔 I'll remind you 30, 14, 7, 3 and 1 day before it expires."},
    "visa_reminders_off": {"en": "🔕 Reminders are paused. Type *start* to turn them on."},
    "visa_check": {
        "en": (
            "🔎 *Check your visa and fines online* (free):\n"
            "• Visa issued in Dubai: GDRFA {gdrfa}\n"
            "• Visa issued in another emirate: ICP {icp}\n\n"
            "You'll need your passport number, nationality and date of birth. Only use these official sites: never give your passport details to other websites."
        ),
    },
    "btn_visa_set": {"en": "Add expiry date"},
    "btn_visa_update": {"en": "Update date"},
    "btn_visa_check": {"en": "Check visa online"},
    "visa_reminder_msg": {
        "en": "⏰ Reminder from Rafiq: your UAE visa expires on {date} ({days} days left). Renew it or leave before then to avoid fines of AED {per_day} per day. Type *my visa* for help.",
    },
    "visa_reminder_today": {
        "en": "⏰ Reminder from Rafiq: your UAE visa expires TODAY ({date}). Renew it or leave today to avoid fines of AED {per_day} per day. Type *my visa* for help.",
    },
    "visa_reminder_expired": {
        "en": "⚠️ Rafiq: your UAE visa expired yesterday ({date}). Fines of AED {per_day} per day have started. Check your status and act now. Type *my visa* for official links.",
    },

    # ------------------------------------------------------------------ can I work?
    "work_menu": {"en": "💼 *Can I work?*\nWhich one is your situation?"},
    "work_visit": {"en": "I'm on a visit visa"},
    "work_visit_d": {"en": "Visit or tourist visa"},
    "work_later": {"en": "\"Start now, visa later\""},
    "work_later_d": {"en": "Employer wants you to start first"},
    "work_second": {"en": "Second or part-time job"},
    "work_second_d": {"en": "Extra work besides my main job"},
    "work_family": {"en": "I'm on a family visa"},
    "work_family_d": {"en": "Sponsored by a spouse or parent"},
    "work_heat": {"en": "Outdoor work in summer"},
    "work_heat_d": {"en": "The midday break rule"},
    "ans_work_visit": {
        "en": (
            "⛔ *You can't work on a visit or tourist visa.* It's illegal for you and the employer: you can be fined, jailed or deported.\n\n"
            "To work, your employer must first get you a work permit from MOHRE and an employment (residence) visa. "
            "Many people are promised a visa \"later\" and end up working illegally, often unpaid.\n\n"
            "More: {mohre}"
        ),
    },
    "ans_work_later": {
        "en": (
            "⛔ *Don't start work before your work permit and employment visa are issued.* Working without them is illegal, even if the employer says it's fine, and you carry the risk: fines, jail or deportation.\n\n"
            "What to do:\n• Ask for your MOHRE work permit and offer letter first.\n• If you're pressured, call the labour ministry (MOHRE) on 80084.\n\n"
            "More: {mohre}"
        ),
    },
    "ans_work_second": {
        "en": (
            "✅ *Yes, with a MOHRE part-time work permit.* If you're on a work visa you can take a second, part-time job once MOHRE issues the permit. "
            "The part-time job must be less than 8 hours a day. If you're on a family visa you also need a no-objection letter from your sponsor.\n\n"
            "Working a second job without the permit is illegal: the hiring company can be fined AED 50,000.\n\n"
            "Official guide: {u_ae}"
        ),
    },
    "ans_work_family": {
        "en": (
            "✅ *Yes, you can work on a family visa*, but only with a work permit from MOHRE that the employer applies for, "
            "and a no-objection letter from your sponsor (your spouse or parent). Don't start before the permit is issued.\n\n"
            "Official guide: {u_ae}"
        ),
    },
    "ans_work_heat": {
        "en": (
            "☀️ *Midday break: 15 June to 15 September, 12:30pm to 3pm.* Work outdoors under direct sun is banned during these hours. "
            "Employers must give you shade and water. Companies that break the rule are fined AED 5,000 per worker.\n\n"
            "Delivery riders can't be forced to work during these hours.\n\n"
            "To report a violation, call MOHRE on 600590000 or use the MOHRE app: {mohre}"
        ),
    },

    # ------------------------------------------------------------------ medicine check
    "med_prompt": {
        "en": (
            "💊 *Medicine check*\n\nType the medicine name as it's written on the box (for example *Tramadol* or *Panadol*), "
            "or send a photo of the box or prescription.\n\nI don't keep what you send."
        ),
    },
    "med_controlled": {
        "en": (
            "⚠️ *{name}* contains *{ingredient}*, which is a *controlled medicine* in the UAE ({group}).\n\n"
            "Before you travel:\n"
            "1. Get the free e-permit from the Emirates Drug Establishment (usually ready in 1 working day): {ede}\n"
            "2. Carry your prescription (from the last 3 months) and a medical report (from the last year).\n"
            "3. Bring no more than a 1-month supply, in the original box.\n\n"
            "No permit? Declare it to customs when you arrive, with your prescription and medical report. Never carry someone else's medicine."
        ),
    },
    "med_controlled_same": {
        "en": (
            "⚠️ *{name}* is a *controlled medicine* in the UAE ({group}).\n\n"
            "Before you travel:\n"
            "1. Get the free e-permit from the Emirates Drug Establishment (usually ready in 1 working day): {ede}\n"
            "2. Carry your prescription (from the last 3 months) and a medical report (from the last year).\n"
            "3. Bring no more than a 1-month supply, in the original box.\n\n"
            "No permit? Declare it to customs when you arrive, with your prescription and medical report. Never carry someone else's medicine."
        ),
    },
    "med_common_same": {
        "en": (
            "✅ *{name}* is a common medicine that is *not* on the UAE controlled list.\n\n"
            "Bring it in the original box with your prescription, and no more than a 3-month supply."
        ),
    },
    "med_banned": {
        "en": (
            "⛔ *{name}*: cannabis and CBD products are *illegal in the UAE*, even if they're legal in your country or sold as a supplement. "
            "Don't bring them, don't ask anyone to send them, and don't use them abroad before travelling."
        ),
    },
    "med_common": {
        "en": (
            "✅ *{name}* ({ingredient}) is a common medicine that is *not* on the UAE controlled list.\n\n"
            "Bring it in the original box with your prescription, and no more than a 3-month supply."
        ),
    },
    "med_unknown": {
        "en": (
            "🔎 I couldn't find *{name}* on my list. My list only covers common medicines, so please check the official "
            "controlled-medicines list before you travel: {ede}\n\nTip: search by the ingredient name on the box, not the brand."
        ),
    },
    "med_unknown_photo": {
        "en": "🔎 I read the photo but couldn't find a medicine name I know. Please type the medicine name as written on the box, or check the official list: {ede}",
    },
    "med_disclaimer": {"en": "This is guidance, not medical advice. Never stop or change a medicine without talking to your doctor."},
    "btn_med_another": {"en": "Check another"},

    # ------------------------------------------------------------------ can I post this?
    "post_menu": {"en": "📱 *Can I post this?*\nUAE online laws are strict. What do you want to share?"},
    "post_people": {"en": "Photos of people"},
    "post_people_d": {"en": "Photos or videos with other people in them"},
    "post_accident": {"en": "An accident or emergency"},
    "post_accident_d": {"en": "Crashes, fires, injured people"},
    "post_news": {"en": "News or a rumour"},
    "post_news_d": {"en": "Forwarded messages, breaking news"},
    "post_complaint": {"en": "Complaint about someone"},
    "post_complaint_d": {"en": "An employer, company or person"},
    "post_fundraise": {"en": "Asking for donations"},
    "post_fundraise_d": {"en": "Raising money for someone in need"},
    "ans_post_people": {
        "en": (
            "⛔ *Don't post photos or videos of people without their permission*, even in public places. "
            "Taking, saving or sharing them without consent can mean at least 6 months in jail and/or a fine of AED 150,000 to 500,000.\n\n"
            "✅ Ask first, or post photos where no one can be recognised."
        ),
    },
    "ans_post_accident": {
        "en": (
            "⛔ *Don't film or share accidents, fires or injured or dead people.* It's a crime in the UAE, and crowding around an accident to film can also get you fined.\n\n"
            "✅ Call 999 (police) or 998 (ambulance) instead, and keep the road clear."
        ),
    },
    "ans_post_news": {
        "en": (
            "⚠️ *Only share news from official sources.* Posting or forwarding rumours or unverified news, especially about emergencies, can bring heavy fines.\n\n"
            "✅ Check official government accounts before you forward anything. If you're not sure, don't share it."
        ),
    },
    "ans_post_complaint": {
        "en": (
            "⚠️ *Don't name, insult or shame a person or company online*, even if what happened is true. Online insults and defamation are crimes in the UAE.\n\n"
            "✅ Use official channels instead: labour problems go to MOHRE (80084), crimes to the police (999)."
        ),
    },
    "ans_post_fundraise": {
        "en": (
            "⛔ *Don't collect or share donation requests without a licence*, including online. Collecting donations for unlicensed causes is a crime, with fines up to AED 500,000 and possible jail.\n\n"
            "✅ Give through a licensed UAE charity instead."
        ),
    },

    # ------------------------------------------------------------------ everyday rules
    "rules_list": {
        "en": (
            "📋 *Everyday rules newcomers break by mistake*\n\n"
            "1. *Visit visa = no work.* Working without a work permit is illegal: {mohre}\n"
            "2. *Know your visa expiry.* Overstay fines are AED 50 per day. Type *my visa*.\n"
            "3. *No photos of people without permission*, and never film accidents.\n"
            "4. *Don't share rumours* or unverified news online.\n"
            "5. *Check medicines before you travel.* Some common ones are controlled: {ede}\n"
            "6. *Your passport is yours.* Employers can't keep it, only hold it briefly for visa paperwork.\n"
            "7. *No unlicensed fundraising*, even for a good cause.\n"
            "8. *Cross only at pedestrian crossings.* Jaywalking is fined (AED 400 in Dubai).\n"
            "9. *Summer midday break:* no outdoor work 12:30pm to 3pm, 15 June to 15 September."
        ),
    },
}

S.update(STRINGS)
