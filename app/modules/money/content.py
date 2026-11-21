"""Money Home: all user-facing text and official sources.

Checked on 2026-11-19 (see README):
- Hawala is legal only through providers holding a Central Bank (CBUAE)
  Hawala Provider Certificate; banks and exchange houses are CBUAE-licensed.
- Since a CBUAE notice of 17 April 2026, licensed banks and finance companies
  may not use WhatsApp or other messaging apps to serve customers or collect
  information. A "bank" asking for documents or offering loans on WhatsApp is
  a red flag.
- Renting out / lending a bank account or digital wallet can make you part of
  money laundering (Sharjah Public Prosecution, Dubai Police 2026).
- Missing about 3 loan or card instalments can count as default; banks can go
  to court, and a court can impose a travel ban until the debt is settled.
Nothing here is financial advice, and nothing the user types is stored.
"""

from __future__ import annotations

from app.i18n import S

CHECKED_ON = "2026-11-19"

CBUAE = "https://www.centralbank.ae"

CURRENCY = {
    "India": "INR", "Pakistan": "PKR", "Bangladesh": "BDT", "Philippines": "PHP", "Nepal": "NPR",
    "Kenya": "KES", "Uganda": "UGX", "Nigeria": "NGN", "Egypt": "EGP",
}

STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ menu
    "menu_money": {"en": "Money home"},
    "menu_money_d": {"en": "Send money safely, compare costs, avoid traps"},
    "money_menu": {"en": "💸 *Money home*\nYou work hard for it. Let's make sure it arrives safely."},
    "money_m_send": {"en": "Send money safely"},
    "money_m_send_d": {"en": "Banks, exchange houses and legal hawala"},
    "money_m_compare": {"en": "Compare transfer costs"},
    "money_m_compare_d": {"en": "Which offer gets more to your family?"},
    "money_m_budget": {"en": "Monthly money plan"},
    "money_m_budget_d": {"en": "See what's left after rent, food and home"},
    "money_m_loans": {"en": "Loans & debt"},
    "money_m_loans_d": {"en": "Loan traps, missed payments, travel bans"},
    "money_m_scams": {"en": "Money scams"},
    "money_m_scams_d": {"en": "Renting your account, fake banks, OTPs"},
    "btn_money_menu": {"en": "Money home"},
    "btn_compare": {"en": "Compare costs"},
    "btn_money_scams": {"en": "Money scams"},
    "money_footer": {"en": "General guidance, not financial advice. I never ask for your bank details or codes."},

    # ------------------------------------------------------------------ send safely
    "money_send": {
        "en": (
            "🏦 *Send money safely*\n\n"
            "• Use a *bank* or a licensed *exchange house*, in a branch or their official app. They're licensed by the Central Bank of the UAE.\n"
            "• *Hawala* is legal only through providers registered with the Central Bank, who hold its certificate. Unregistered hawala is illegal, and your money has no protection.\n"
            "• *Always get a receipt* with a reference number, and keep it until your family has the money.\n"
            "• Double-check the receiver's name and number before you pay. Transfers are hard to reverse.\n"
            "• Never send money through a person you don't know, or someone offering a \"special rate\".\n"
            "• Compare the *amount your family receives*, not just the fee. A low fee can hide a poor exchange rate.\n\n"
            "Central Bank of the UAE: {cbuae}"
        ),
    },

    # ------------------------------------------------------------------ compare
    "money_compare_ask": {
        "en": (
            "🧮 *Compare transfer costs*\n\n"
            "Ask each provider: \"If I pay AED ___, how much will arrive?\" Then type each offer on its own line: "
            "*amount in AED, fee in AED, amount received in {cur}*.\n\n"
            "For example:\n*1000 15 23500*\n*1000 0 23300*\n\n"
            "I don't save what you type."
        ),
    },
    "money_compare_line": {"en": "{label}: you pay *AED {paid}* → *{received} {cur}* arrive (= {rate} {cur} per AED)"},
    "money_compare_best": {"en": "✅ *{label}* gets your family the most: *{diff} {cur}* more for every AED 1,000 you pay."},
    "money_compare_same": {"en": "Both offers deliver about the same."},
    "money_compare_single": {"en": "Send me a second offer to compare, or check today's market rate in your bank's app."},
    "money_compare_bad": {
        "en": "Please type each offer as 3 numbers: *amount in AED, fee in AED, amount received*. For example: *1000 15 23500*",
    },
    "money_offer": {"en": "Offer {n}"},

    # ------------------------------------------------------------------ budget
    "money_budget_ask": {
        "en": (
            "📒 *Monthly money plan*\n\n"
            "Type your monthly amounts in AED with a word for each, for example:\n"
            "*salary 2000, rent 450, food 500, transport 150, phone 50, home 700*\n\n"
            "Use any words you like. I don't save what you type."
        ),
    },
    "money_budget_result": {
        "en": "📒 *Your month* (AED)\n\n{lines}\n\n*Spending:* {spent}\n*Left over:* {left}\n\n{advice}",
    },
    "money_budget_ok": {
        "en": "👍 You have *AED {left}* left. Try to put a little aside every month for emergencies, like a fine, a medical bill or a sudden flight home. Even AED 100 a month adds up.",
    },
    "money_budget_tight": {"en": "⚠️ You spend almost all of your salary. Small changes help: shared transport, cooking together, a cheaper phone plan."},
    "money_budget_over": {
        "en": "🔴 You spend *AED {over}* more than you earn. Please don't cover the gap with loans or credit cards: debts here can lead to court cases and travel bans. Look at what you can cut first.",
    },
    "money_budget_home": {"en": "You send home *{pct}%* of your salary. Remember to keep enough for yourself here too."},
    "money_budget_no_salary": {"en": "Please include your salary, for example: *salary 2000, rent 450, food 500*"},
    "money_budget_bad": {"en": "Please type amounts with words, for example: *salary 2000, rent 450, food 500, home 700*"},

    # ------------------------------------------------------------------ loans & debt
    "money_loans": {
        "en": (
            "⚠️ *Loans & debt*\n\n"
            "• *Borrow only from licensed banks or finance companies*, never from people on social media or \"agents\" who lend cash.\n"
            "• *Never pay a fee in advance* to get a loan approved. That's a scam.\n"
            "• *Never give your Emirates ID, passport or a signed cheque* to someone so they can \"arrange\" a loan.\n"
            "• *Missing payments is serious.* After about 3 missed instalments, banks often treat it as default and can go to court. A court can stop you leaving the UAE until the debt is paid.\n"
            "• Missed payments also go on your credit record (Etihad Credit Bureau), which follows you for future loans and some jobs.\n"
            "• Struggling to pay? Talk to your bank *early* and ask about a payment plan. It's much easier before a case is filed.\n"
            "• Leaving the UAE for good? Close or settle your loans and cards first."
        ),
    },

    # ------------------------------------------------------------------ scams
    "money_scams": {
        "en": (
            "🚨 *Money scams to know*\n\n"
            "• *\"Rent your bank account\" or \"receive money and pass it on\"*: this is money laundering, even if you didn't know the money was dirty. Never let anyone use your bank account, card, digital wallet or app, whatever they pay you.\n"
            "• *A job that asks you to receive and transfer money* for a commission is a scam.\n"
            "• *Banks don't use WhatsApp*: since April 2026, licensed banks may not serve customers or collect documents on WhatsApp. A \"bank\" asking for your details there is fake.\n"
            "• *Never share your OTP, PIN or card number*, not even with someone claiming to be from your bank or the police.\n"
            "• *Prizes, lotteries and \"investments\" with big returns* are almost always scams.\n"
            "• Got a suspicious request? Stop, don't pay, and report it to your bank and to Dubai Police on *901*."
        ),
    },
    "money_rent_warning": {
        "en": "🚨 *Stop: never let anyone use your bank account*, even for a friend or for payment. If the money is from crime, *you* can be charged with money laundering. If you already did, call your bank now and report it to the police on *901*.",
    },
}

S.update(STRINGS)
