# Rafiq – AI agent for newcomers to Dubai

Built module by module.

| Module | Status |
| --- | --- |
| 1. Welcome & profile + privacy | ✅ Complete |
| 2. Job Safety (job offer and agency checks, text/photo/PDF) | ✅ Complete |
| 3. Stay Legal (visa, work, medicines, posting, everyday rules) | ✅ Complete |
| 4. Departure Planner (personal before-you-fly checklist, travel reminders) | ✅ Complete |
| 5. Arrival Guide (Emirates ID, SIM, bank, insurance, ILOE, safe housing) | ✅ Complete |
| 6. Pay & Rights (salary watch, late pay, complaint drafts, hours & leave, gratuity) | ✅ Complete |
| 7. Friends & wellbeing (loneliness, free things to do, meeting safely, support lines, crisis safety net) | ✅ Complete |
| 8. Money home (sending money safely, cost comparison, monthly plan, loans & debt, money scams) | ✅ Complete |
| 9. Help & emergency (not-safe support, embassies, lost passport, reporting crime, police trouble, numbers) | ✅ Complete |
| Core: Official Knowledge Base & Rule Monitor (weekly checks of official sources, human review) | ✅ Complete |
| Core: Language & Voice (voice notes in any language, natural phrasing) | ✅ Complete |

## What Module 1 does

- A one-message welcome and a short, plain-language privacy consent ("Tell me more" for detail). English only for now; all text lives in `app/i18n.py`, ready for more languages later.
- Employment-first setup in about 5 taps: name (optional), kind of work (decides which pay, hours and overtime rules apply), home country, contract monthly salary (optional, used by the wage check), then a summary to confirm or edit. Setup ends on the employment menu with a wage-check tip. Journey stage and visa details are optional and can be added from the profile or *My visa*.
- Forgiving input: users can tap buttons, type the option number, type the answer ("nepal", "yes"), or write dates many ways ("15/03/2027", "15 March 2027").
- Main menu, profile view/edit, pause/resume reminders, help with UAE emergency numbers.
- Privacy controls anytime: *my data* (export), *delete* (with a one-time confirmation), re-consent when the privacy notice changes, automatic deletion after 12 months of inactivity.

## What Module 2 (Job Safety) does

- *Check a job offer* is the first menu item. Users paste or forward the recruiter's message, or send a **photo or PDF** of the offer; Rafiq also spots a pasted offer or a sent photo/PDF automatically.
- **Photos and PDFs:** PDFs with a text layer are read locally (no AI, nothing leaves the server). Photos and scanned PDFs are transcribed word for word by Google Gemini. Clear messages for every problem (wrong file type, too big, password-protected, blurry, AI unavailable), and the user can always paste the text instead.
- **Rules first:** 10 built-in checks for scam signs (fees charged to the worker, work on a visit visa, payment by mobile money/crypto, passport retention, cash salary, free email, chat-only contact, pressure, "no interview / guaranteed visa", no salary). They work with the AI switched off, and each links to the official source (MOHRE).
- **AI second (Google Gemini, optional):** reads the offer's details (employer, job, salary, hours, contract...) and lists what's *not mentioned*. It can't invent anything: every value must appear in the offer, numbers must match exactly, or it's dropped.
- **Clear next steps:** a High risk / Be careful / No common warning signs verdict, what to do now, the official agency register for the user's home country (Kenya, Nepal, Pakistan, Bangladesh, Uganda, India, Philippines), and a ready-to-send list of questions for the employer.
- **Agency check:** how to verify a recruitment agency on the official list for the user's country.
- Offers are checked, never stored. Only an anonymous result (risk level and flag codes) is logged for impact metrics.
- The privacy notice now explains offer checks; existing users are asked to agree again automatically.

## What Module 3 (Stay Legal) does

- **My visa:** days left with a colour-coded status, an overstay estimate if expired (AED 50 per day, unified by ICP), links to check status and fines on the official GDRFA (Dubai) and ICP (other emirates) portals, and a one-tap way to add or update the expiry date.
- **Visa reminders:** a daily job (09:00 UAE time) sends reminders 30, 14, 7, 3 and 1 day before expiry, on the day, and the day after. Each is sent once; failures retry next run; paused users get nothing.
- **Can I work?** Clear answers for: visit visa, "start now, visa later", second/part-time job (MOHRE part-time permit), family visa, and the summer midday break.
- **Medicine check:** type a name or send a photo of the box. Controlled medicines (opioid painkillers, benzodiazepines, sleep medicines, ADHD stimulants, pregabalin, gabapentin, codeine) get the free Emirates Drug Establishment permit steps; cannabis/CBD is flagged as illegal; common medicines are confirmed; anything else goes to the official list. Rafiq never says "allowed" for a medicine it doesn't know. Names are never stored.
- **Can I post this?** Photos of people, accidents, rumours, online complaints, fundraising.
- **Everyday rules:** nine laws newcomers break by mistake.
- Users can also just ask: "can I bring tramadol?" or "I'm on a visit visa, can I work?" are answered directly.
- All wording is fixed and sourced (checked 2026-11-19); the AI is only used to read a photo of a medicine box.

### WhatsApp visa reminder template (submit to Meta for approval)

WhatsApp only allows messages more than 24 hours after a user's last message if they use an approved template. In WhatsApp Manager create a **Utility** template, language English, for example named `visa_expiry_reminder`, with this body:

```
Hi {{1}}, this is a reminder from Rafiq: your UAE visa expires on {{2}} ({{3}} days left). Renew it or leave before then to avoid overstay fines. Reply MENU for help.
```

Then set `WHATSAPP_VISA_TEMPLATE=visa_expiry_reminder` in `.env`. Telegram reminders need no template.

## What Module 4 (Departure Planner) does

- *Before you fly* in the main menu (or type *checklist*, *what should I pack?*).
- A **personal checklist** of up to 9 items, built from the profile: passport (6+ months), entry permit (or a *visit visa* warning instead), contract, **exit clearance for the user's own country**, medicines, medical & certificates, copies & contacts, money, packing.
- **Exit clearance by country** (checked 2026-11-19): Kenya (contract attestation + pre-departure training), India (ECR emigration clearance on eMigrate), Philippines (OEC / OFW Pass), Pakistan (Protector registration), Nepal (final labour approval), Bangladesh (BMET clearance card + 3-day orientation), Uganda (MGLSD clearance + orientation); everyone else gets "ask your labour ministry". Each links to the authority's own site.
- Tap an item to read what to do, then *Mark as done*; progress (🟩⬜) and "Next up" are saved. Items link straight to the right tool: *Check my offer* (Module 2), *Check a medicine* and *Can I work?* (Module 3).
- **Optional travel date**: countdown, a reminder about the entry permit's 2-month window, and reminders 7 days and 1 day before the flight listing what's left. Respects *stop*.
- Stored in its own `departure_plans` table (no change to `users`): travel date encrypted, ticks stored as item keys only. Included in *my data*, removed by *delete* and by the retention cleanup. The privacy notice was updated (v4), so existing users are asked to agree again.

### WhatsApp departure reminder template

Create a second **Utility** template, for example `departure_reminder`:

```
Hi {{1}}, this is Rafiq: you fly on {{2}} ({{3}} days to go). You have {{4}} items left on your checklist. Reply CHECKLIST to see them. Safe travels!
```

Then set `WHATSAPP_DEPARTURE_TEMPLATE=departure_reminder` in `.env`.

## What Module 5 (Arrival Guide) does

- *Your first weeks* in the main menu, or type *arrival* / *I just arrived*.
- Up to 9 steps for settling in, built from the profile: SIM card, **medical test & Emirates ID** (or a visit-visa warning instead), work contract, health insurance, **job-loss insurance (ILOE)** (skipped for domestic workers, who are exempt), bank/salary account (WPS), safe housing, official apps, and rights at work.
- **Typed topics open the right step directly**: *emirates id*, *sim card*, *ejari*, *bed space*, *iloe*, *bank account*, *uae pass*, *my rights*...
- **Optional arrival date** → "Day 7 in the UAE" and the residence-visa deadline (within 1 month of entry), shown until that step is ticked; overdue gets a clear warning. Reminders on day 21 and day 28 if it's still open (not for visit visas; respects *stop*).
- Facts checked 2026-11-19: residence within 1 month of entry (u.ae); employer-paid health insurance in all emirates since January 2025; ILOE AED 400 fine for not subscribing, AED 5–10 a month, domestic workers exempt; Dubai REST / Ejari checks; Dubai's 2026 shared-housing permits (bed spaces, partitions).
- Shortcuts: *My visa* (Module 3), *Check my contract* (Module 2), *Can I work?* (Module 3).
- Shares the checklist storage with Module 4 (`arrival_plans` table, encrypted date, item keys only); included in *my data*, removed by *delete* and retention cleanup. Privacy notice v5 (adds the arrival date).

### WhatsApp arrival reminder template

```
Hi {{1}}, this is Rafiq: your medical test and Emirates ID should be finished by {{2}} ({{3}} days left). If they aren't done, ask your employer now. Reply ARRIVAL for help.
```

Set `WHATSAPP_ARRIVAL_TEMPLATE=<template name>` in `.env`.

## What Module 6 (Pay & Rights) does

- *Pay & rights* in the main menu, or type *salary late*, *complaint*, *gratuity*, *overtime*, *my rights*...
- **Salary watch (opt-in):** once a month Rafiq asks "did you get your salary for October?" and the user replies *PAID*, *PART* or *NOT PAID* (typed or tapped). Private sector: asked on the 3rd, again on the 10th and 17th if not paid. Domestic workers: the 11th and 18th. Respects *stop*. The record keeps only paid/part/unpaid per month (no amounts), encrypted, last 12 months.
- **Late salary:** the current rules (checked 2026-11-19): since 1 June 2026 last month's salary is due on the 1st through WPS and anything later is delayed; MOHRE reminds the employer from day 2, warns on day 5, can fine from day 11; 85% counts as paid without losing the rest. Domestic workers: within 10 days of the due date. Clear next steps, and the free, confidential *My Salary Complaint* route.
- **Complaint drafts** for 6 problems (unpaid, always late, passport kept, hours/rest days, different from contract, final pay). Filled from a template with the user's own name and salary record; everything else is a [placeholder]. **Rafiq never sends anything:** there is no outward tool at all, and drafts aren't stored.
- **Hours, leave & days off** (private sector and a separate domestic-worker version), **gratuity** rules with a calculator (21/30 days' basic pay, 1-year minimum, 2-year cap; not stored), and **keep proof** tips (including not secretly recording people, which breaks UAE privacy law).
- Privacy notice v6 (adds the salary record).

### WhatsApp salary check-in template

```
Hi {{1}}, this is Rafiq's salary check: did you get your salary for {{2}}? Reply PAID, PART or NOT PAID. Reply STOP to pause check-ins.
```

Set `WHATSAPP_PAY_TEMPLATE=<template name>` in `.env`.

## What Module 7 (Friends & wellbeing) does

- *Friends & wellbeing* in the main menu, or type *lonely*, *homesick*, *things to do*, *make friends*, *talk to someone*.
- **Deliberate design choice:** Rafiq does **not** match users with strangers or share anyone's contact details. Lonely newcomers are prime targets for romance, "friend" and job-for-cash scams, so the module points to public, free, official places and teaches how to meet people safely.
- **I feel lonely:** a warm, practical message (fixed call home, go where people are, one small "yes" a week, move, rest).
- **Free things to do:** beaches, parks, libraries (MBRL membership is free for residents), culture, the official events calendar, plus **dated events** (e.g. Dubai Fitness Challenge 31 Oct – 29 Nov 2026, Eid Al Etihad on 2 Dec) that **disappear automatically** after they end. The team adds events in `app/modules/social/content.py`, each with an official link.
- **Meet people safely:** community through embassies, places of worship and public events; the main scams (romance, job/visa for cash, carrying parcels, lending SIM/bank/ID, "investment" groups); report to Dubai Police on 901.
- **Talk to someone:** 800 HOPE (800 4673, call or WhatsApp), 800 SAKINA (800 725462), Dubai's Itma'en (800 506), the IWRC line (800 46342, all nationalities); 999 / 998 in danger.
- **Weekly check-in (opt-in):** Friday evenings, "How was your week? GOOD / OK / HARD". Answers are never stored; HARD always gets support options.
- **Crisis safety net (whole agent):** any message mentioning suicide or self-harm, from any state (even before setup or mid-flow), gets an immediate caring reply with 999/998 and free support lines, before anything else. The user's place in any flow is kept. Only an anonymous "support shown" event is logged, never the message.
- Privacy notice v7 (adds the check-in setting); the notice was also tightened to fit WhatsApp's 1,024-character limit.

### WhatsApp weekly check-in template

```
Hi {{1}}, Rafiq here. How was your week? Reply GOOD, OK or HARD. Reply STOP to pause messages.
```

Set `WHATSAPP_SOCIAL_TEMPLATE=<template name>` in `.env`.

## What Module 8 (Money home) does

- *Money home* in the main menu, or type *send money*, *hawala*, *compare*, *budget*, *loan*, *otp*...
- **Send money safely:** banks and licensed exchange houses; hawala only through providers registered with the Central Bank; receipts; compare the amount that *arrives*, not just the fee.
- **Compare transfer costs:** type each offer as "AED amount, fee, amount received" (one per line). Rafiq shows the real rate per AED including fees, in the user's home currency (KES, INR, PKR, PHP...), and which offer gets the family most per AED 1,000.
- **Monthly money plan:** "salary 2000, rent 450, food 500, home 700" → spending, what's left, the share sent home, and a gentle warning if spending is more than income (debt here can lead to court cases and travel bans).
- **Loans & debt:** licensed lenders only, never pay a fee to get a loan, never hand over ID or signed cheques; what happens after missed instalments (court, travel ban, credit record); talk to the bank early.
- **Money scams:** renting/lending your account or wallet (money laundering), "receive and transfer" jobs, fake banks on WhatsApp (licensed banks have been barred from serving customers on messaging apps since April 2026), OTP/PIN theft, prizes and investments.
- **Danger detection:** free-text messages like "a man will pay me to rent my bank account" or "my cousin wants to use my card" get an immediate warning, while normal messages ("I use my card at the shop", "can I use my card abroad") don't.
- **Nothing typed is stored or logged.** The calculators parse the numbers, reply once, and drop them; the node can only read the home country (for the currency name).
- The main menu is now at WhatsApp's 10-item limit; the Help & Emergency module will expand the existing *Help & emergencies* item.

## What Module 9 (Help & emergency) does

- The existing *Help & emergencies* menu item now opens a full help menu (the main menu stays at WhatsApp's 10-item limit). Typing *help*, *sos*, *embassy*, *lost passport*, *report a crime*, *arrested*, *useful numbers* or *not safe* also works.
- **I'm not safe:** 999 for danger; the human trafficking hotline 800 7283 (800 SAVE); Dubai Foundation for Women and Children 800 111 (call or WhatsApp); Ministry of Interior 116111; MOHRE 80084; Dubai Police 901; the embassy. Advice for workers thinking of leaving an abusive employer: report it too, so there's a record (absconding reports only after 5 days; MOHRE can cancel false ones).
- **"Not safe" safety net (whole agent):** messages describing abuse, being locked in, forced work, sexual violence or trafficking ("my madam beats me", "they locked me in") get the not-safe screen immediately, from any state, without losing the user's place. Suicide/self-harm support (Module 7) still takes priority. Only an anonymous "support shown" event is logged.
- **My embassy:** official websites for India, the Philippines, Pakistan, Bangladesh, Nepal, Kenya and Uganda (each mission's own domain); everyone else gets the UAE Foreign Ministry's official list of foreign missions.
- **Lost passport or ID:** police report and lost certificate → embassy (new passport or emergency travel document) → move the residence visa (GDRFA / ICP); Emirates ID replacement through ICP; a passport *kept* by someone is a police/MOHRE matter.
- **Report a crime** (999, 901, Al Ameen 800 4888 confidential), **police or court trouble** (interpreter, don't sign what you can't read, ask for your embassy, lawyer), and **useful numbers** on one screen.
- Numbers checked against the official u.ae crime and safety page on 2026-11-19.
- **Guard fix found by this module's tests:** the output guard used to strip a valid official link when a comma or full stop came right after it. Trailing punctuation is now ignored when checking links (regression test included).

## Flagship: the wage check (Employment protection agent)

The championship entry is the **AI employment protection agent**, starting with one problem: a salary that arrives short or not at all. One message in ("My employer was supposed to pay me AED 1,800, but I only received AED 1,000"), typed or as a voice note in any language, and Rafiq:

1. **Understands**: rules (not the AI) pick out the agreed and received amounts; if one is missing it asks for both.
2. **Cross-checks**: her saved contract salary and the pay rule for her worker category (private sector: due on the 1st through WPS; domestic workers: within 10 working days).
3. **Calculates**: the *potential* shortfall and any pattern across months. It is always "potential": only MOHRE or a court decides what is owed.
4. **Asks**: was a deduction agreed in writing? If yes, it isn't counted as owed.
5. **Prepares** (on her tap): a case file in Rafiq (her own record, not an official case) and the Arabic + English evidence pack.
6. **Drafts** (on her tap): the complaint, filled with her own figures. "Nothing has been sent": she reviews and files it herself (MOHRE app, website or 80084).
7. **Follows up**: when she taps *I've filed it*, her reference number and reminders after 7 days, then every 14.

Code: `app/modules/pay/wagecheck.py` (detection, parsing, steps 1–4) and `app/modules/pay/node.py` (steps 5–6, using the case manager). Every step is logged for the impact dashboard. Evals: `wage-check-*` (5 cases). Supporting tools in the same agent: Contract Shield (offer vs contract), job offer check, payslip reader, gratuity calculator, free legal help.

**Contract Shield (offer vs contract).** Photo, PDF or text of the offer, then of the contract. The AI only transcribes; rules compare salary, job title, hours, leave and contract length. It reads English and Arabic (including Arabic-only pages and Arabic-Indic digits) and compares basic with basic and total with total, so a bilingual MOHRE contract with basic + allowances isn't a false alarm; a contract listing only a basic salary is treated as all the pay promised in writing. Job titles in different languages are flagged to check, not guessed.

**Overtime calculator** (type *overtime calculator*, or Pay & Rights → Overtime calculator). Private sector, Article 19 of Decree-Law 33 of 2021, with MOHRE's own formula: hourly wage = basic salary ÷ 30 ÷ 8; extra hours +25%, 10pm–4am +50% (not shift workers), rest day without a day off = the day's wage +50%. Warns when overtime averages more than 2 hours a day (the legal limit; 144 hours every 3 weeks in total). Domestic workers get their own rules instead. Rules only, always "at least", with a button to draft an hours complaint.

## Replies in her language

Rafiq answers in the language she writes or speaks: Swahili, Hindi, Urdu, Bengali, Nepali, Tagalog, Arabic, Malayalam, Tamil, Amharic and more (`app/media/translate.py`). The rules, routing and safety checks still run in English:

- **In:** a typed message that isn't English is translated to English first (phone numbers, IDs and emails masked before it goes to the AI); a voice note already comes back in English with its language code. Rafiq shows "I understood (in English): …" so she can check it.
- **Out:** the English replies, after the output guard, are translated in one batch. Every number, amount, phone number, link and [placeholder] must come back unchanged, and the output guard runs again on the translation; any message that fails stays in English. Replies containing an ID or long number aren't sent to the AI at all.
- **Stays in English:** complaint drafts, letters and evidence packs, because MOHRE and employers need that version.
- *Reply in Swahili* or *English* switches the language; a short note says the reply was translated by AI. Daily cap and timeout; without the AI, Rafiq simply answers in English. The privacy notice says these messages may go to Google Gemini (privacy version 2026-11-24.3, so users are asked again).

## Lead task: My renewals (residency and document deadlines)

**Status check** (in *My renewals*; type *status check*). Everything a renewal depends on is checked in one go: residence visa, passport (and who holds it), Emirates ID, health insurance, whether the employer is renewing, last month's pay, housing, family visa fees and open cases. Five tap-only questions fill what Rafiq doesn't know (no free text, so nothing to inject). The result is red / amber / green with one plain reason per line, and every problem is a button into the agent that fixes it: passport held → Protection, unpaid pay → Employment, insurance deducted or missing → Wellbeing, changing jobs → Career, unlicensed bed space → Housing, family visa fees → Financial. Each handoff is logged (`status_handoff`) for the impact dashboard.

**Bilingual case pack.** Every case exports as a PDF with an Arabic version first (MOHRE, the courts and typing centres work in Arabic), then English: summary, amounts owed month by month for wages cases (from the worker's own pay records), timeline and what to bring to MOHRE. The Arabic wording is fixed template text (have a native speaker or typing centre check it before launch); the worker's own entries are copied as written, never machine-translated. Arabic is shaped and laid out right to left with arabic-reshaper and python-bidi, using the bundled DejaVu Sans font (free licence, `app/media/fonts`).

**Free legal help** (type *free legal help* or *I need a lawyer*, or tap it on any case). Rafiq is not a lawyer, so when a case needs one it lists the free official routes: MOHRE 80084 (advice and complaints, including domestic workers), Dubai Courts' *Shoor* programme (one free consultation with a licensed law firm, 04 334 7777), the Dubai CDA Legal Clinic, Abu Dhabi Judicial Department legal aid, Ministry of Justice consultation in other emirates, and the embassy labour office. It is also offered when a case ends *Not resolved* or *Sent to Labour Court*.

About 9 in 10 people living in Dubai are expatriates, and every one of them runs on paperwork deadlines. *My renewals* (first row of the main menu) keeps one calendar for the residence visa, Emirates ID, passport, family visa and Ejari:

- **One calendar:** expiry dates come from the profile, from documents saved in *My documents*, or typed in; sorted by urgency (red within 30 days).
- **Cross-checks:** warns when the passport expires less than 6 months after the visa (renewal can be refused) and when the Emirates ID and visa dates don't match.
- **What each renewal needs:** who files it (employer, you, embassy), where (GDRFA/Amer in Dubai, ICP elsewhere, embassy, DLD), the steps, and what happens if late (Emirates ID: AED 20 a day after 30 days, max AED 1,000; overstay after grace: AED 50 a day).
- **Readiness checklist:** tick documents as you collect them; status moves from *Not started* to *Done*.
- **Reminders:** scheduled automatically (e.g. 60, 30 and 7 days before a residence visa expires) and shown in the Life Manager.
- **Renewal pack:** a printable PDF of steps, checklist and dates.
- **Next cycle:** marking *Done* asks for the new expiry date and resets the reminders (the visa reminders follow it).
- **Official sites:** each renewal links only to the official place to apply and check status (GDRFA, ICP, MOFA embassy list, DLD, u.ae), with a reminder never to pay through a link in a message.
- **Status from official messages:** forward or paste the SMS/email from ICP, GDRFA, Amer or Ejari (or tap *Paste official SMS*). Rules (no AI) read the status (*Submitted*, *Action needed*, *Done*), the application number and any new expiry date, then update the tracker and reminders. The message itself is not stored. A message with a non-official link or asking for card details or a code is flagged as a likely scam and changes nothing. There is no public ICP/GDRFA API for third parties, so this is how Rafiq stays in step with the government systems (e.g. ICP's own AI renewal service) instead of competing with them.

Rafiq never files anything: the employer, an official centre or the person does. Type *my renewals*, *renew my visa*, *renew my emirates id* or *renew my passport*.

## Agents: one orchestrator, six specialists

Rafiq is one LangGraph graph with one AI model. The `route` node is the orchestrator: it checks consent, then crisis and abuse signs, then picks a specialist by rules (the AI picks only from a fixed list when the rules can't). Each specialist is a group of nodes with its **own** tool allow-list. A tool is refused unless both the node and the agent that owns it hold it (`app/security/tool_policy.py`, `app/agent/agents.py`). Every message records which agent handled it.

| Agent | What it does | Never |
| --- | --- | --- |
| Rafiq orchestrator | Checks consent, then crisis and abuse signs first; rules pick the specialist, the AI picks only from a fixed list when the rules can't. | acts on another person's data; lets the AI choose a tool or write advice |
| Employment agent | Job offer and contract checks, salary watch and gaps, evidence packs, letters and dispute cases. | contacts an employer, recruiter or office; submits a complaint for the worker; opens saved ID documents; gives a legal ruling |
| Protection agent | Crisis and abuse detection, exploitation early warning, incident records, emergency help and SOS. | sends an SOS without the worker's confirmation; messages anyone but the opted-in trusted contact; decides for the worker whether to leave or report |
| Life admin agent | Renewals calendar (visa, Emirates ID, passport, tenancy) with document checks and reminders, legal status, journey checklists, document vault, housing, trusted services and the Life Manager brief. | files a visa or renewal application; shares a saved document with anyone |
| Financial agent | Sending money home, budgets, savings goals, loan costs, rate alerts and financial scam checks. | moves or holds money; opens saved documents; recommends a specific lender |
| Wellbeing agent | Friends, free events, opt-in weekly check-ins and healthcare navigation. Crisis words go to the Protection agent. | diagnoses or suggests prescription medicine; opens documents or salary records |
| Career agent (roadmap) | Skills gap to a target job, 90-day plan, CV, application and interview tracker, safe job search. | applies for a job or contacts an employer; opens saved documents or salary records |

## Guardian features (Employment, Protection, Life admin)

- **What I'm owed:** contract salary vs amount received per month; asks whether a shortfall was an agreed deduction; names a pattern after 2 short months. Type *what am i owed*.
- **Payslip reading:** photo or PDF; Gemini transcribes, rules pick net, gross, basic and deductions; the payslip isn't kept. Type *read my payslip*.
- **Dispute case manager:** open a case (wages, passport, contract, safety, other), get evidence, file it yourself, record the reference number, follow-up check-ins after 7 days and then every 14, record the outcome, download the history as a PDF. Type *my cases*.
- **Protection early warning:** two or more exploitation signs together (unpaid wages, debt to repay before leaving, passport held, locked in, threats, violence, no rest, phone taken, no food, forced work, deceptive job) go to the Protection agent: names the signs (no legal ruling), asks "Are you safe right now?", gives confidential help, starts a dated incident record, offers the SOS. Rules only; nothing stored unless the worker asks.
- **Life Manager:** one prioritised list (urgent, coming up, ongoing) across salary, cases, visa, documents, checklists and safety, each with its next action. Weekly Monday push is opt-in. Type *brief*.

## Evaluation

```
python scripts/run_evals.py            # 47 labelled synthetic cases, rules only, free; writes evals/report.md
python scripts/run_evals.py --live     # also uses Gemini; counts tokens for cost per task (set --price-in/--price-out)
```

Case types follow the workshop: complete, missing detail, unexpected input, out of context, plus safety (attacks and emergencies). The test suite fails if the score drops below 100%. The cases were written by the team, so the next step is adding anonymised real messages from user interviews.

## Judges' web demo

Set `DEMO_ENABLED=true` and `DEMO_ACCESS_CODE=<code for judges>` in `.env`, then `docker compose up -d`. Judges open `https://rafiq.afrivance.ai/demo`, enter the code and chat with the same agent (same pipeline, rate limits and guards) as on WhatsApp. They can upload a photo or PDF, share a sample location and open **Impact** for anonymised totals and the evaluation score. Each reply shows which agent handled it.

Update the shared Caddy once so `/demo` is reachable (keeps the file's inode, changes only Rafiq's block):

```
cp ~/proxy/Caddyfile ~/proxy/Caddyfile.backup-$(date +%F)
python3 scripts/update_shared_caddy.py ~/proxy/Caddyfile
docker exec shared_caddy caddy validate --config /etc/caddy/Caddyfile
docker exec shared_caddy caddy reload --config /etc/caddy/Caddyfile
```

### WhatsApp templates for cases and the brief

```
rafiq_case_followup:  Rafiq check-in: any news on your {{1}} complaint (ref {{2}})? Reply MY CASES to add an update or record how it ended.
rafiq_weekly_brief:   Good morning from Rafiq. {{1}} things need your attention this week. Reply BRIEF to see them. Reply STOP to pause messages.
```

Set `WHATSAPP_CASE_TEMPLATE` and `WHATSAPP_BRIEF_TEMPLATE` to the approved names.

## Growth areas: career, housing, health, money, trusted services

Open *Work, home & health* in the main menu.

- **Career (Career agent):** pick your job now, your years and the skills you have; Rafiq shows the target role, the skills to build and a 90-day plan, makes a one-page CV (PDF, contact details left blank), tracks applications and interview dates (reminder the day before), gives interview practice and explains how to change jobs without a one-year permit ban (MOHRE guidance, May 2026). It never applies for a job or contacts an employer.
- **Housing (Life admin agent):** checks a room ad or rental agreement before you pay (pay-before-viewing, no Ejari, cash only, partitions or bed spaces under Dubai Law No. 4 of 2026, overcrowding, large deposits, extra fees, and what's missing), the real monthly cost, a viewing checklist, the 90-day rent-increase rule and the DLD Smart Rental Index, a monthly rent reminder, and a landlord case in *My cases*.
- **Health (Wellbeing agent):** insurance rights (mandatory, employer-paid for private-sector and domestic workers in every emirate since 1 January 2025), where to get care, no-insurance steps with a request letter, bill terms, what to tell and ask a doctor, appointment reminders. It never diagnoses or suggests prescription medicine.
- **Grow my money (Financial agent):** savings goals in the home currency converted at today's rate with progress and an optional monthly check-in, a family budget that names pressure points and proposes a plan, the yearly cost of transfer fees, and a loan cost calculator. It never moves money or recommends a lender.
- **Find trusted help (Life admin agent):** a directory in three labelled tiers: official bodies, licensed business types with how to check the licence, and community help marked "not checked by Rafiq". No private business is listed until it has been verified (`PARTNERS` is empty).

Reminders the user asks for (rent, appointments, interviews, savings) are stored with encrypted wording in `user_reminders` and sent by a daily job at 08:30 UAE time; they also appear in the Life Manager.

```
rafiq_reminder:  Rafiq reminder: {{1}} Reply MENU for help or STOP to pause messages.
```

Set `WHATSAPP_REMINDER_TEMPLATE` to the approved name.

## "Do it for me": tasks Rafiq carries out

Rafiq doesn't just answer questions, it does jobs for the user. The rule for all of them: **Rafiq prepares, the user confirms, and Rafiq only acts on the user's own things or towards a person the user chose who agreed.** It never contacts an employer, agency or government office.

Open *Do it for me* (first row of the main menu) or type the task name.

| Task | What Rafiq does | Type |
| --- | --- | --- |
| Unpaid wages pack | Asks for employer, salary and start date once, uses the salary record (or asks which months were missed) and builds a PDF: salary table, amount owed, end-of-service estimate, the law that applies, next steps and a ready complaint letter. | *evidence pack* |
| My documents | Encrypted copies of passport, visa, Emirates ID, contract or offer. Gemini transcribes the page, rules pick the expiry date, and the user confirms it. Reminders 90/30/7 days before expiry. A visa's date also updates the visa reminders. Tap to get a copy back. Max 12 files, 5 MB each. | *my documents* |
| Trusted contact (SOS) | The user names someone. Rafiq gives an invite (code `JOIN ABCD1234`, plus a one-tap link when `TELEGRAM_BOT_USERNAME` / `WHATSAPP_PUBLIC_NUMBER` are set). Only after that person sends the code are they linked. *sos* asks for confirmation, can add a live location, then alerts the contact with a map link and the embassy. The contact can leave with *stop sos*. | *trusted contact*, *sos* |
| Rate alert | Shows today's mid-market rate for the home currency and messages the user once when it reaches their target (+1%, +2% or their own number). | *rate alert* |
| Letters & forms | A few questions, then a PDF letter: passport return, annual leave, salary certificate, resignation notice, payslips. The employer name is remembered. | *letters* |
| Contract switch check | Compares the offer that was promised with the contract the worker is asked to sign: salary, job title, hours, leave and length. Flags anything worse as possible contract substitution and gives the MOHRE number. Can save both copies. | *contract check* |
| What I'm doing for you | One screen listing every reminder, alert, check-in, saved document and contact Rafiq is looking after. | *my reminders* |

**Security of the tasks**

- **Tool misuse / privilege escalation:** the `tasks` node has its own allow-list. `send_sos` is the only outward tool in Rafiq. It needs a confirmation nonce created by the user's own tap, sends only to the opted-in contact, and is limited to 3 per hour. A stray or forged "send" button does nothing.
- **Invite abuse:** codes are random, single-use and expire after 48 hours. Join attempts are limited to 5 a day, and your own code is refused. Nobody can be added as a contact without sending the code themselves.
- **Data leakage:** documents and their dates are Fernet-encrypted. Every vault lookup is filtered by the owner's id, so a guessed id returns nothing. Locations are never stored: one is held for 10 minutes, encrypted, only if the user hasn't sent the SOS yet. Messages to the contact pass the same output guard. Delete-my-data and retention cleanup remove all of it.
- **Indirect prompt injection:** in offers, contracts and ID pages the AI only transcribes. Dates and terms are picked out and compared by rules, so a document can't "say" it is fine.
- **Safe outputs:** PDFs escape every typed value, so a value can't inject markup or links. `t.me` / `wa.me` links pass the output guard only when they point at Rafiq's own bot or number. Exchange rates come only from the allow-listed host, over HTTPS, with no redirects, and are cached for an hour.

### WhatsApp templates for tasks (submit to Meta, category Utility)

```
rafiq_doc_expiry:  Rafiq reminder: your {{1}} expires on {{2}} ({{3}} days). Start the renewal now so you always have valid papers. Reply MENU for help.
rafiq_rate_alert:  Rafiq rate alert: 1 AED = {{2}} {{1}} today, at or above your target of {{3}}. Compare providers before you send. Reply COMPARE for tips.
rafiq_sos_alert:   SOS from {{1}} via Rafiq. They say they need help and may be in danger. Location: {{2}}. Call or message them now. In the UAE, police: 999. Human trafficking hotline: 800 7283.
```

Set `WHATSAPP_VAULT_TEMPLATE`, `WHATSAPP_RATE_TEMPLATE` and `WHATSAPP_SOS_TEMPLATE` to the approved names.

## Official Knowledge Base & Rule Monitor

- **One registry of every rule Rafiq relies on** (`app/knowledge/registry.py`): 24 facts, each with its module, official source, check mode and the date it was last verified.
- **Weekly check** (worker cron, Mondays 07:00 UAE):
  - *tokens* pages: Rafiq extracts the numbers that matter (AED amounts, day/month counts, toll-free numbers, percentages) and compares them with the last reviewed baseline, so a change shows up as a readable diff like "new on page: 500 aed / gone: 400 aed". Busy home pages are only checked for reachability; must-contain phrases (e.g. "8007283") must still be on the page.
  - Pages failing 2 checks in a row are flagged as unreachable; facts with no stable page (news-reported resolutions) get a "re-check by hand" reminder 180 days after verification.
- **Human in the loop:** alerts go to the team (audit log + optional Telegram chat `ADMIN_TELEGRAM_CHAT_ID`). Advice is **never** changed automatically. While a topic has an unreviewed change, users of that module see: "An official source for this topic changed recently and our team is checking it. Please double-check the official link before you act." (never on crisis or not-safe screens).
- **Review workflow (server only, no chat admin commands):**
  ```
  python scripts/rule_monitor.py status          # every fact, source, state
  python scripts/rule_monitor.py check           # run now
  python scripts/rule_monitor.py ack <fact_id>   # reviewed: accept new numbers, clear the user notice
  ```
- **Security:** fetching is https-only to allow-listed official domains, every redirect hop is checked before it's requested, hosts resolving to private/loopback/link-local addresses are refused (SSRF), 2 MB and 20 s limits. Page text is never stored, shown to users or sent to an AI (no indirect prompt injection); only the extracted numbers are kept.

## How the agent is organised

One LangGraph agent with specialist nodes: **route → onboarding | menu | privacy | job_safety | stay_legal | departure | arrival | pay | social | money | help | fallback**.

1. **Rules first** (fast, predictable): safety nets (crisis, not-safe) → buttons → what the user is in the middle of → commands (tolerant of filler words) → keyword detectors.
2. **AI only if the rules don't recognise a typed message** (`app/agent/intent.py`): Gemini picks **one label from a fixed list of 33 topics**, and the matching specialist answers with its fixed, sourced content. Rafiq tells the user: "🤔 I think you're asking about *late salary*… (Not right? Type *menu*.)"
   - The model can't call tools, write what the user sees, delete/export/change data (those aren't on the list), or bypass the safety nets and attack scan (they run first).
   - Message masked for phone numbers/emails and wrapped as untrusted data; canary; the answer must be exactly one known label, anything else → normal "didn't understand" menu; short timeout; 50 per user per day; only after consent; switch off with `INTENT_AI_ENABLED=false`. Only the chosen topic is logged, never the message.
3. Gemini's other narrow jobs: extracting job-offer fields (grounded), reading photos/scans, transcribing voice notes.

## Language & Voice

- **Voice notes in any language:** a worker can send a WhatsApp/Telegram voice note in Hindi, Urdu, Tagalog, Bengali, Nepali, Swahili, Arabic or English. Gemini writes it down and translates it into simple English; Rafiq replies "🎙️ I heard: “…”" so the user can see it understood, then answers **in English** (English-only replies for now, as decided; every string is in `app/i18n.py`, ready for more languages later).
- **A voice note is treated exactly like typed text:** the same cleaning, attack scan (a spoken "ignore your instructions" is blocked and counts as a strike), crisis and not-safe checks, routing, delete confirmation and output guard. A spoken job offer goes to Job Safety; "my salary is late" to Pay & Rights.
- **Natural phrasing:** commands now match even with filler words ("can you please check my job offer", "hello Rafiq, my salary is late"), which helps typed messages too. Long messages are treated as content, not commands.
- **Privacy & limits:** only after the user agreed to the privacy notice (v8 says voice notes may go to Google Gemini); audio is never stored and the words are never logged (only "voice_transcribed"). File type from the bytes (Ogg/Opus, MP3, M4A, AMR, WAV, WebM), 3 MB / 3 minutes, 30 voice notes per user per day (`VOICE_*` in `.env`), the transcription prompt carries the canary.
- Friendly messages for every problem: too long, no speech heard, unplayable audio, AI unavailable, daily limit, not yet agreed.

## Security: how each attack is countered

| Attack | Defence in Rafiq | Where |
| --- | --- | --- |
| Prompt injection | Every typed message (and every voice-note transcript) is cleaned (invisible characters removed, Unicode normalised) and scanned with rules (English, plus common Swahili attack phrases) that also catch spaced-out, leetspeak and full-width text. Blocked messages get a polite refusal; 3 strikes = 30-minute cool-down. | `app/security/injection.py`, `app/service.py` |
| Jailbreaking | Persona/"DAN"/"no restrictions" patterns are blocked. Module 1 replies are fully scripted (no AI model writes them), so there is nothing to jailbreak. | same |
| Data leakage | Phone numbers stored only as a keyed hash + encrypted copy; names and visa dates encrypted at rest. Every outgoing message passes an output guard that blocks secrets and the system-prompt canary, masks any personal data that isn't the user's own, and strips non-official links. Message text is never stored or logged; logs are PII-masked. | `app/security/crypto.py`, `output_guard.py`, `pii.py`, `logging_setup.py` |
| Tool misuse | Each graph node has an allow-list of tools; tools only act on the current user. Button ids are validated server-side against the current step (and, for the checklist, against the user's own items), so forged or stale buttons do nothing. | `app/security/tool_policy.py`, `app/agent/nodes.py` |
| Privilege escalation | Identity comes only from the verified webhook (Meta HMAC signature / Telegram secret), never from message text. There are no admin commands in chat. Deleting data requires a one-time, 10-minute server nonce. | `app/main.py`, `app/channels/*`, `tool_policy.py` |
| Malicious files | Files are downloaded in memory only (never saved), capped at 10 MB before and during download, typed from their own bytes (only JPEG, PNG, WebP, PDF), PDFs limited to 5 pages, encrypted PDFs refused, parsing time-limited. WhatsApp media is fetched with an ownership check, and every download hop (including redirects) must be on a Meta or Telegram host before any request is sent. | `app/media/` |
| Indirect prompt injection | Crawled official pages (Rule Monitor) are never shown to users or sent to the AI; only extracted numbers are compared. A pasted job offer, photo or PDF is treated as a document, not as the user's instructions: hidden "instructions to the AI" are reported to the user as a warning sign (no strike against them), and such text is never sent to the AI. Other offers are PII-masked and wrapped in a random boundary with rules that it is data. The AI has no tools; it can only fill a fixed form. | `app/security/untrusted.py`, `app/modules/job_safety/` |
| Hallucination | All advice wording is written by us, not generated. The AI only copies details from the offer, and a grounding check drops any value not in the offer (numbers must match exactly). The AI can add a red flag only by quoting a sentence that really is in the offer. Links are limited to official domains. | `app/modules/job_safety/extract.py`, `output_guard.py` |

Also: per-user rate limits, webhook de-duplication, 512 KB body limit, API docs off in production, containers run read-only as a non-root user, and the database and cache have no internet access.

## Run it locally (no WhatsApp needed)

```bash
pip install -r requirements-dev.txt
python3 scripts/chat.py        # chat with Rafiq in your terminal
python3 -m pytest -q           # 251 tests
```

## Deploy on the VPS

Tested target: Ubuntu 22.04/24.04, 2 GB RAM or more.

1. **DNS:** create an A record (e.g. `rafiq.yourdomain.com`) pointing at the VPS IP.
2. **Server:** install Docker (`curl -fsSL https://get.docker.com | sh`), open the firewall (`ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable`).
3. **Code and secrets:**
   ```bash
   unzip rafiq-latest.zip && cd rafiq
   cp .env.example .env && chmod 600 .env
   docker compose build
   docker compose run --rm --no-deps web python scripts/generate_secrets.py   # paste the output into .env
   nano .env      # DOMAIN, PUBLIC_BASE_URL, TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY (+ WhatsApp values later)
   docker compose up -d
   curl https://<DOMAIN>/health                  # {"status":"ok"}
   ```
4. **Telegram (test channel):** create a bot with @BotFather, put the token in `.env`, `docker compose up -d`, then
   `docker compose exec worker python scripts/set_telegram_webhook.py` (the worker, not web: web has no internet access by design).
5. **WhatsApp:** in the Meta developer dashboard, set the webhook URL to `https://<DOMAIN>/webhook/whatsapp` with your `WHATSAPP_VERIFY_TOKEN`, subscribe to `messages`, fill in the `WHATSAPP_*` values, set `WHATSAPP_ENABLED=true`, then `docker compose up -d`.
6. **Rule Monitor baseline:** `docker compose exec worker python scripts/rule_monitor.py check`.
7. **Logs:** `docker compose logs -f web worker`.
8. Back up `.env` (especially `FIELD_ENCRYPTION_KEY` and `ID_HASH_PEPPER`) somewhere safe. Without them, saved data can't be read.

**Server already has a reverse proxy on ports 80/443** (e.g. a shared Caddy for other apps): don't run Rafiq's own Caddy. Add to `.env`:
```
COMPOSE_FILE=docker-compose.yml:docker-compose.shared-proxy.yml
SHARED_PROXY_NETWORK=<the shared proxy's Docker network>
```
then `docker compose up -d --build`, paste `deploy/shared-caddy-rafiq.caddy` into the shared Caddyfile, and reload that Caddy. Rafiq's web container joins the proxy network as `rafiq-web`.

**Moving to a Dubai server later:** copy the folder and `.env`, restore a `pg_dump` of the database, update DNS and the Meta webhook URL.

## Project layout

```
app/
  main.py            webhooks (signature checks, size limits) -> queue
  worker.py          arq worker: processes messages, nightly retention cleanup, visa, travel and arrival reminders, salary and wellbeing check-ins
  service.py         security pipeline around the agent
  agent/graph.py     LangGraph: route -> onboarding | menu | privacy | job_safety | stay_legal | departure | arrival | pay | social | money | help | fallback
  agent/llm.py       AI model (any provider, set in .env)
  modules/job_safety rules, AI extraction + grounding, report, node
  media/             safe download (WhatsApp/Telegram), reading photos/PDFs, voice notes
  modules/stay_legal content (sourced rules), medicines, visa view + reminders, node
  modules/departure  checklist content (sourced), personal checklist, travel-date reminders, node
  modules/arrival    first-weeks steps (sourced), deadline + reminders, typed topics, node
  modules/pay        salary watch + check-ins, late-pay guidance, complaint drafts, gratuity, node
  modules/social     wellbeing, free things + dated events, meeting safely, support lines, crisis net, node
  modules/money      sending safely, transfer comparison, monthly plan, loans & scams, node
  modules/help       not-safe net, embassies, lost passport, reporting, police trouble, numbers, node
  knowledge/         registry of every official fact, safe fetcher, Rule Monitor
  agent/nodes.py     Module 1 conversation logic
  agent/ui.py        every screen (buttons/lists within WhatsApp limits)
  i18n.py            all user-facing text (English)
  security/          injection, output guard, PII, crypto, tool policy, rate limits
  channels/          WhatsApp Cloud API + Telegram adapters
  db/                tables and data access (always scoped to one user)
scripts/             chat simulator, secrets generator, Telegram webhook setup, rule_monitor admin tool
tests/               security, conversation, parsing, channel/limit tests
```

## Notes before launch

- Tables are created on startup. Add Alembic migrations before the first schema change in production.
- **AI model: Google Gemini** (`gemini-3.7-flash`). Get an API key in Google AI Studio, put it in `GOOGLE_API_KEY`, keep `LLM_ENABLED=true`. Text offers and text PDFs still work without the key; photos and scanned PDFs need it.
- Gemini processes data on Google's servers. When moving to Dubai, review data-residency options (see the concept doc).
- Visa expiry, travel and arrival dates are encrypted, so the reminder jobs decrypt them in memory; fine for thousands of users, revisit for very large scale.
- The `departure_plans`, `arrival_plans`, `pay_records`, `social_prefs` and `source_checks` tables are new: `create_all` adds them on startup, existing tables are untouched.
- All nine user-facing modules and both core modules are complete. Next: polish for submission (demo script, pitch deck, demo video), real-device testing on WhatsApp, and Meta template approvals.
- Run `python scripts/rule_monitor.py check` once on the VPS after deploying, to set the baselines (the build sandbox can't reach the official sites).
