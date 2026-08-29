# Outreach — internship cold-email tool

A small, modular CLI that researches a company, drafts a personalized
cold email with your resume, and sends it under rate limits — with a
mandatory human review step before anything goes out.

## Why it's built this way

- **One SQLite file is the source of truth.** Every module reads/writes
  through `db.py`. This is what makes the tool mergeable into a bigger
  project later without a rewrite — swap the CLI for a UI, keep the DB
  and modules as-is.
- **Every draft needs your approval before it can send.** The AI
  research step can get facts wrong or stale; `review` is the safety
  net for that, not an optional step.
- **Sends are capped and randomly delayed** to protect your own email
  account's sender reputation. Don't remove this to "go faster" —
  getting your account flagged as spam is worse than a slow campaign.
- **Resume content is never AI-generated.** You register resume
  variants (PDF files you already wrote); the tool only picks which
  variant fits a given job posting by keyword match.
- **Contact sourcing is manual, on purpose.** A named person's email
  outperforms a scraped generic inbox by a wide margin — the tool
  helps you manage and speed up entry, not find contacts for you.

## Setup (one-time)

```bash
cd outreach
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and fill in:
#   GEMINI_API_KEY      - get one at https://aistudio.google.com/apikey
#   GMAIL_ADDRESS        - your gmail address
#   GMAIL_APP_PASSWORD   - generate at https://myaccount.google.com/apppasswords
#                          (requires 2-Step Verification turned on)

python cli.py init
```

Register at least one resume variant (put the PDF in `resumes/` first):

```bash
python cli.py add-resume --name main --keywords "python,ai,ml,data" \
    --file resumes/YourResume.pdf
```

Write a `context.txt` — a plain-text file describing your real background.
This is the **only** source of truth the AI uses about you; it will not
invent achievements beyond what's in here.

## Every time you have a new batch of companies

### Option A — bulk add with a CSV (faster for several companies at once)

1. Open `companies_template.csv` in Excel/Google Sheets. One row per
   contact. Only `company_name` and `contact_email` are required —
   leave the rest blank if you don't have it. Same `company_name` on
   multiple rows just adds another contact under that one company.

2. Import it:
   ```bash
   python cli.py import-csv --file companies_template.csv
   ```

3. See the ID numbers you'll need next:
   ```bash
   python cli.py list-companies
   python cli.py list-contacts
   ```

### Option B — add one at a time

```bash
python cli.py add-company --name "Acme Corp" --domain acme.com \
    --job-url https://acme.com/careers/intern-backend
# → prints "Added company #1"

python cli.py add-contact --company 1 --email jane@acme.com \
    --name "Jane Doe" --title "Engineering Manager" --source "LinkedIn"
# → prints "Added contact #1"
```

## Compose, review, send — the part that repeats for every contact

```bash
# 1. Draft — researches the company via web search, writes a hook + email.
#    Lands in pending_review. Nothing is sent yet.
python cli.py compose --company 1 --contact 1 --context context.txt

# 2. Read every pending draft before approving anything
python cli.py review

# 3. Fix it if needed, then approve (or reject if it's bad)
python cli.py edit --email 1 --subject "Better subject line"
python cli.py approve --email 1
python cli.py reject --email 2

# 4. Send — preview first, then actually send.
#    Respects your daily cap and adds random delays between sends.
python cli.py send --dry-run
python cli.py send
```

Repeat `compose → review → approve → send` for each company/contact —
this step is intentionally per-contact, since every email is a unique
AI draft that needs your eyes before it goes out.

## After sending

```bash
# Check overall pipeline counts any time
python cli.py status

# As you check your own inbox, record what happened
python cli.py mark --email 1 --result replied     # or: ghosted / bounced

# See who's gone quiet and might need a nudge
python cli.py follow-ups

# Draft a short follow-up referencing the original email (not a new pitch)
python cli.py follow-up --email 1
# then review → approve → send it just like any other draft
```

## Full command reference

| Command | What it does |
|---|---|
| `init` | Creates/upgrades the database. Safe to re-run after an update. |
| `add-resume` | Registers a resume PDF + keywords for matching. |
| `add-company` | Adds one company. |
| `add-contact` | Adds one contact under a company. |
| `import-csv` | Bulk-adds companies + contacts from a CSV file. |
| `list-companies` / `list-contacts` | Shows everything you've added, with ID numbers. |
| `compose` | AI researches + drafts an email. Always lands as `pending_review`. |
| `review` | Shows every pending draft. |
| `edit` | Change a draft's subject/body before approving. |
| `approve` / `reject` | Moves a draft to `approved` (sendable) or `rejected`. |
| `send` | Sends everything `approved`, capped per day with random delays. Use `--dry-run` to preview. |
| `status` | Counts of emails by status. |
| `mark` | Manually record `replied` / `ghosted` / `bounced` after checking your inbox. |
| `follow-ups` | Lists sent emails with no reply past the follow-up window, excluding ones already followed up on. |
| `follow-up` | Drafts a short nudge referencing an original sent email. Only works on emails with status `sent`/`replied`/`ghosted`. |

## Known limitations (by design, for v1)

- No automated contact discovery/scraping — you source contacts
  yourself. This is intentional: named-person emails outperform
  scraped generic inboxes by a wide margin, and scraping (e.g.
  LinkedIn) violates most platforms' terms of service.
- Gmail SMTP with an app password is used for sending. If Google
  tightens or removes app-password SMTP access, the fix is to swap
  `sender.py` for the Gmail API with OAuth — the rest of the tool is
  unaffected since sending is isolated to that one module.
- No multi-user/team features — this is a personal tool.

## Extending later

Each module (`contacts`, `resume`, `composer`, `reviewer`, `sender`,
`tracker`) only talks to the DB and to each other through plain
function calls — no framework lock-in. To fold this into a bigger app
later: keep `db.py`'s schema, replace `cli.py` with a different
front end (web UI, desktop app, etc.), and everything else works
unchanged.