"""Help & emergency: all user-facing text, verified numbers and embassy links.

Checked on 2026-11-19 against official pages (see README):
- u.ae "Crime, safety and security": Dubai Police Al Ameen 8004888 (confidential);
  human trafficking hotline 8007283 (EWAA, "800 SAVE"); Dubai Foundation for
  Women and Children 800111 (also on WhatsApp); Ministry of Interior 116111
  for violence against women and children.
- Emergencies: 999 police, 998 ambulance, 997 fire; Dubai Police non-emergency 901.
- Lost passport (u.ae): police report and "lost passport certificate", then
  your embassy for a new passport or emergency travel document, then move your
  residence visa to the new passport (GDRFA in Dubai, ICP elsewhere).
- Domestic workers: employers can only file an "absconding" report after 5
  days; MOHRE can cancel an inaccurate one. Police ask workers to report abuse
  (901) rather than only running away.
- Embassy / consulate websites: each mission's own official domain.
Wording is fixed, never generated.
"""

from __future__ import annotations

from app.i18n import S

CHECKED_ON = "2026-11-19"

MOHRE = "https://www.mohre.gov.ae"
DUBAI_POLICE = "https://www.dubaipolice.gov.ae"
U_AE_LOST_PASSPORT = "https://u.ae/en/information-and-services/visa-and-emirates-id/lost-your-passport-with-uae-residence-visa-on-it/lost-your-passport-in-the-uae"
ICP_SMART = "https://smartservices.icp.gov.ae"
GDRFA = "https://www.gdrfad.gov.ae"
UAE_MISSIONS = "https://www.mofa.gov.ae/en/Missions/Foreign-Missions-in-UAE"

# Official websites of each country's embassy / consulate in the UAE.
EMBASSIES: dict[str, list[tuple[str, str]]] = {
    "India": [("Consulate General, Dubai", "https://www.cgidubai.gov.in"),
              ("Embassy, Abu Dhabi", "https://www.indembassyuae.gov.in")],
    "Philippines": [("Consulate General, Dubai", "https://dubaipcg.dfa.gov.ph"),
                    ("Embassy, Abu Dhabi", "https://abudhabipe.dfa.gov.ph")],
    "Pakistan": [("Consulate General, Dubai", "https://pakistanconsulatedubai.ae")],
    "Bangladesh": [("Consulate General, Dubai", "https://bcgdubai.gov.bd")],
    "Nepal": [("Embassy, Abu Dhabi (covers all emirates)", "https://ae.nepalembassy.gov.np")],
    "Kenya": [("Embassy, Abu Dhabi", "https://www.kenyaembassy.ae")],
    "Uganda": [("Embassy, Abu Dhabi", "https://abudhabi.mofa.go.ug")],
}

# Signs that someone is being abused, confined or trafficked. Checked on every
# message (after the crisis check), so help is shown even mid-flow.
UNSAFE_PHRASES = (
    "beats me", "beat me", "beating me", "hits me", "hitting me", "slapped me", "kicked me",
    "locked me", "locks me", "locked in", "lock me in",
    "won't let me leave", "wont let me leave", "not allowed to leave", "can't leave the house", "cant leave the house",
    "cannot leave the house", "not allowed to go out", "won't let me go home", "wont let me go home",
    "raped", "rape me", "sexually abused", "sexual abuse", "sexually harassed", "harassing me sexually",
    "forced to work", "forcing me to work", "forced me to work", "no food for", "don't give me food", "dont give me food",
    "trafficked", "sold me", "they sold me", "threatened to kill me", "threatens to kill me",
)

STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ menu
    "help_menu_text": {
        "en": "🆘 *Help & emergencies*\n\n🚨 In danger right now? Call *999* (police) or *998* (ambulance).\n\nWhat do you need?",
    },
    "help_m_unsafe": {"en": "I'm not safe"},
    "help_m_unsafe_d": {"en": "Abuse, locked in, passport taken, forced work"},
    "help_m_sos": {"en": "Alert trusted contact"},
    "help_m_sos_d": {"en": "One tap sends them an SOS with your location"},
    "help_unsafe_sos": {"en": "🆘 Tap *Send SOS* to alert your trusted contact (set one up in *Do it for me*)."},
    "help_m_embassy": {"en": "My embassy"},
    "help_m_embassy_d": {"en": "Your country's embassy or consulate"},
    "help_m_passport": {"en": "Lost passport or ID"},
    "help_m_passport_d": {"en": "What to do, step by step"},
    "help_m_report": {"en": "Report a crime"},
    "help_m_report_d": {"en": "Including confidentially"},
    "help_m_police": {"en": "Police or court trouble"},
    "help_m_police_d": {"en": "Your basic rights if you're stopped or charged"},
    "help_m_numbers": {"en": "Useful numbers"},
    "help_m_numbers_d": {"en": "Emergency, labour, support lines"},
    "help_m_about": {"en": "How Rafiq works"},
    "help_m_about_d": {"en": "Commands, privacy and limits"},
    "btn_help_menu": {"en": "Help & emergencies"},
    "btn_my_embassy": {"en": "My embassy"},
    "btn_im_not_safe": {"en": "I'm not safe"},

    # ------------------------------------------------------------------ not safe
    "help_unsafe": {
        "en": (
            "💛 *You deserve to be safe. Help is free and confidential.*\n\n"
            "🚨 *In danger right now:* call *999*.\n\n"
            "*If you're being abused, locked in, forced to work, or your passport is taken:*\n"
            "• *800 7283* (800 SAVE): human trafficking hotline, every day, many languages.\n"
            "• *800 111*: Dubai Foundation for Women and Children, call or WhatsApp. Women and children.\n"
            "• *116111*: Ministry of Interior, violence against women and children.\n"
            "• *80084*: MOHRE, for work problems, including domestic workers.\n"
            "• *901*: Dubai Police, non-emergency.\n"
            "• Your embassy or consulate can help too.\n\n"
            "*If you're thinking of leaving:* report it to the police or MOHRE as well, so there's a record. "
            "Employers can only file an \"absconding\" report after 5 days, and MOHRE can cancel one that isn't true.\n\n"
            "If someone might check your phone, you can delete this chat afterwards."
        ),
    },

    # ------------------------------------------------------------------ embassy
    "help_embassy_head": {"en": "🏛️ *Your embassy / consulate ({country})*"},
    "help_embassy_line": {"en": "• {name}: {url}"},
    "help_embassy_other": {
        "en": "🏛️ *Your embassy / consulate*\n\nFind your country's embassy or consulate on the UAE Foreign Ministry's official list: {list}",
    },
    "help_embassy_tail": {
        "en": "They can help with lost passports, emergencies, arrests, deaths, and serious problems with employers. Use only their official website or numbers, not agents.",
    },
    "help_embassy_change": {"en": "Different country? Update it in *profile*."},

    # ------------------------------------------------------------------ lost passport
    "help_passport": {
        "en": (
            "🛂 *Lost passport or ID*\n\n"
            "*Passport:*\n"
            "1. *Report it to the police* (in Dubai: the Dubai Police app or website, or any police station) and get the *lost passport certificate*.\n"
            "2. Take it to *your embassy or consulate* for a new passport, or an emergency travel document if you must fly urgently.\n"
            "3. *Move your residence visa* to the new passport: GDRFA in Dubai {gdrfa}, ICP elsewhere {icp}\n\n"
            "*Emirates ID:* report it lost and apply for a replacement through ICP: {icp}\n\n"
            "*Passport stolen or kept by someone?* That's different: tell the police and MOHRE (*80084*). No employer may keep your passport.\n\n"
            "Official steps: {u_ae}"
        ),
    },

    # ------------------------------------------------------------------ report a crime
    "help_report": {
        "en": (
            "📣 *Report a crime*\n\n"
            "• *Emergency:* *999*.\n"
            "• *Not an emergency:* Dubai Police *901*, the Dubai Police app, or {police}\n"
            "• *Confidential (Dubai):* Al Ameen *800 4888*. Your identity is kept secret.\n"
            "• *Online fraud or scams:* report through the police app or call *901*, and tell your bank straight away.\n"
            "• *Human trafficking:* *800 7283*.\n\n"
            "Keep screenshots, receipts and messages as evidence."
        ),
    },

    # ------------------------------------------------------------------ police / court trouble
    "help_police": {
        "en": (
            "⚖️ *Police or court trouble*\n\n"
            "• Stay calm and polite. Don't resist, and don't run.\n"
            "• *Ask for an interpreter* if you don't understand Arabic.\n"
            "• *Don't sign anything you can't read or understand.* Ask for a translation first.\n"
            "• *Ask that your embassy or consulate be told.* Your family can also contact the embassy for you.\n"
            "• Ask for a lawyer. Your embassy can often share a list of lawyers.\n"
            "• A travel ban or court case? Find out the case number and which court, then get legal advice.\n\n"
            "I can't give legal advice for your case, but your embassy can guide you."
        ),
    },

    # ------------------------------------------------------------------ numbers
    "help_numbers": {
        "en": (
            "📞 *Useful numbers (UAE)*\n\n"
            "*Emergencies*\n• Police *999*\n• Ambulance *998*\n• Fire *997*\n\n"
            "*Police, not urgent*\n• Dubai Police *901*\n• Al Ameen, confidential *800 4888*\n\n"
            "*Work*\n• MOHRE labour claims *80084*\n\n"
            "*Safety*\n• Human trafficking *800 7283*\n• Dubai Foundation for Women and Children *800 111*\n• Violence against women & children *116111*\n\n"
            "*Someone to talk to*\n• 800 HOPE *800 4673* (call or WhatsApp)\n• 800 SAKINA *800 725462*"
        ),
    },
}

S.update(STRINGS)
