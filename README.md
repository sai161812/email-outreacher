# Email Outreacher

A personal, self-hosted application for managing internship outreach. It researches a company, drafts a tailored email around an existing resume, and sends only after an explicit human review.

## What it demonstrates

- A Flask operator dashboard for contacts, drafts, approvals, tracking, and follow-ups.
- AI-assisted company research and draft generation with deterministic quality checks.
- SQLite-backed state management for contacts, resume variants, email status, and suppression records.
- Safe delivery controls: approval gates, rate limits, randomized delays, duplicate-send protection, and reply tracking.

## Why it's built this way

- **One SQLite file is the source of truth.** Every module reads/writes through a central `repository.py` to `outreach.db`.
- **Every draft needs your approval before it can send.** The AI research step can get facts wrong or stale; the Review dashboard is the safety net for that, not an optional step.
- **Sends are capped and randomly delayed** to protect sender reputation. Speed is not worth getting an account flagged as spam.
- **Resume content is never AI-generated.** You register resume variants (PDF files you already wrote); the tool only picks which variant fits a given job posting by keyword match.
- **Contact sourcing is manual, on purpose.** A named person's email outperforms a scraped generic inbox by a wide margin.

## Setup (one-time)

```bash
cd email-outreacher
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and fill in:
#   GEMINI_API_KEY      - get one at https://aistudio.google.com/apikey
#   GMAIL_ADDRESS        - your gmail address
#   GMAIL_APP_PASSWORD   - generate at https://myaccount.google.com/apppasswords
#                          (requires 2-Step Verification turned on)

> **Important — enable IMAP in Gmail**:
> You must manually enable IMAP access in your Gmail account for automatic reply detection to work.
> Go to **Gmail +' Settings (gear icon) +' See all settings +' Forwarding and POP/IMAP +' Enable IMAP** and click **Save Changes**.
```

## Running the App

Start the Flask server:

```bash
$env:FLASK_APP="app.py"
python -m flask run --port 5000
```

Then open `http://localhost:5000` in your browser.

## Using the Dashboard

### 1. Contacts & Companies
Click the **Contacts** tab in the sidebar to view all your imported contacts. You can manually add new contacts and companies using the "Add Contact" button. To draft an email for a contact, click "Draft Email" next to their name. This triggers the AI to write a personalized outreach email.

### 2. Review Queue
Every drafted email lands in the **Review** tab. You MUST review every draft before it can be sent.
- Click **Save Edits** to modify the subject, hook, or body.
- Click **Approve** to move it to the send queue.
- Click **Reject** to discard it.

### 3. Sending
Once emails are approved, click the **Send Batch** button on the Dashboard.
- The system respects the `DAILY_SEND_CAP` configured in `.env` (or defaults to 15).
- It will randomly delay each send to protect your sender reputation.
- It will automatically attach the correct personalized PDF resume to the email.

### 4. Tracking & Follow-ups
Click the **Tracking** tab to see the status of all sent emails.
- Click **Check IMAP Replies** on the dashboard to automatically scan your inbox and mark replies.
- Use the status dropdown on any sent email to manually mark it as `interview_scheduled`, `offer`, `ghosted`, etc.
- If an email has gone unanswered past the follow-up window, it will appear in the "Due for Follow-up" table. Click "Draft Follow-up" to generate a polite nudge.

## Known limitations (by design, for v1)

- No automated contact discovery or scraping. Contacts are sourced manually; scraping platforms such as LinkedIn also violates their terms of service.
- Gmail SMTP with an app password is used for delivery. Moving to Gmail OAuth would only require replacing the transport layer.
- No multi-user/team features. This is a focused personal tool, intended for local or private deployment.
