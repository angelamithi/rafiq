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
- Profile setup in ~8 taps: name (optional), journey stage, home country, visa type, visa expiry date (only when the visa has one), work sector, then a summary to confirm or edit.
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

- *Before you fly* in the main menu (or type *checklist*, *what should I pack?*). New users with a job offer are pointed to it when setup finishes.
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

- *Your first weeks* in the main menu, or type *arrival* / *I just arrived*. People who pick "Just arrived" during setup are pointed to it.
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

1. Install Docker and the Compose plugin. Point your domain's DNS A record at the VPS.
2. Copy this folder to the server, then:
   ```bash
   cp .env.example .env && chmod 600 .env
   python3 scripts/generate_secrets.py     # paste the output into .env
   nano .env                               # set DOMAIN, PUBLIC_BASE_URL, bot tokens
   docker compose up -d --build
   ```
3. **Telegram (test channel):** create a bot with @BotFather, put the token in `.env`, set `TELEGRAM_ENABLED=true`, then
   `docker compose exec web python scripts/set_telegram_webhook.py`.
4. **WhatsApp:** in the Meta developer dashboard, set the webhook URL to `https://<DOMAIN>/webhook/whatsapp` with your `WHATSAPP_VERIFY_TOKEN`, subscribe to `messages`, and fill in the four `WHATSAPP_*` values. Set `WHATSAPP_ENABLED=true` and restart: `docker compose up -d`.
5. Back up `FIELD_ENCRYPTION_KEY` and `ID_HASH_PEPPER` somewhere safe. Without them, saved data can't be read.

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
