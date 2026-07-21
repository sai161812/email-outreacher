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

## Setup

```bash
cd outreach
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env:
#   ANTHROPIC_API_KEY  - from console.anthropic.com
#   GMAIL_ADDRESS       - your gmail address
#   GMAIL_APP_PASSWORD  - generate at myaccount.google.com/apppasswords
#                         (requires 2-Step Verification turned on)

python cli.py init
```

## Workflow

```bash
# 1. Register a resume variant (do this once per variant you have)
python cli.py add-resume --name backend --keywords "backend,api,sql,django" \
    --file resumes/backend_resume.pdf

# 2. Add a company you're targeting
python cli.py add-company --name "Acme Corp" --domain acme.com \
    --job-url https://acme.com/careers/intern-backend

# 3. Add a specific contact at that company (not a generic info@ inbox)
python cli.py add-contact --company 1 --email jane@acme.com \
    --name "Jane Doe" --title "Engineering Manager" --source "LinkedIn"

# 4. Write a short plain-text file describing your relevant background
#    for this application (this is the ONLY source of truth the AI
#    uses about you — it will not invent achievements)
echo "2nd year CS student. Built a full-stack memory-first productivity
app (Tauri/React/FastAPI/SQLite). Strong in Python and TypeScript.
Looking for a backend or infra internship." > context.txt

# 5. Compose — this researches the company via web search and drafts
#    a hook + email. Lands in pending_review, NOT sent.
python cli.py compose --company 1 --contact 1 --context context.txt

# 6. Review every pending draft before approving
python cli.py review

# 7. Approve the ones that are good (edit first if needed)
python cli.py edit --email 1 --subject "Better subject line"
python cli.py approve --email 1

# 8. Send — respects your daily cap and adds random delays
python cli.py send --dry-run     # preview first
python cli.py send

# 9. Check pipeline status any time
python cli.py status

# 10. As replies come in, mark them yourself (you read your inbox)
python cli.py mark --email 1 --result replied

# 11. See what's overdue for a follow-up
python cli.py follow-ups
```

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
