# Email Outreacher

A single-owner Flask dashboard for manual contact management, Gemini-assisted drafting, explicit review, Gmail SMTP delivery, and reply tracking. Python **3.12** is supported. The app defaults to loopback access and never schedules sending automatically.

## Install and start

Windows PowerShell, from the repository:

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip==26.2.1
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
Copy-Item .env.example .env
# Edit .env with your own settings.
.\.venv\Scripts\python.exe manage.py init
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:5000 app:app
~~~

In a second terminal, from the same directory:

~~~powershell
.\.venv\Scripts\python.exe worker.py
~~~

Open **http://127.0.0.1:5000**. Keep the server and worker running. Jobs remain pending while the worker is stopped. One worker owns each database through a process lock.

Linux/macOS equivalents:

~~~sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip==26.2.1
.venv/bin/python -m pip install --require-hashes -r requirements.lock
cp .env.example .env
.venv/bin/python manage.py init
.venv/bin/python -m waitress --listen=127.0.0.1:5000 app:app
# Second terminal:
.venv/bin/python worker.py
~~~

The factory also initializes/migrates the database when imported by Flask or Waitress. Stop the server and worker before upgrading application code. An existing supported database receives a pre-migration backup in its sibling backups directory. Existing duplicate identities or invalid legacy relationships are reported and preserved, not silently deleted.

## First use

1. In **Settings**, enter your name and truthful candidate facts. Add a PDF resume you wrote, an HTTPS resume link, or deliberately select **No resume** while reviewing a draft.
2. In **Companies**, add the company and optional job text/URL. In **Contacts**, select the company and enter a contact, or import companies_template.csv.
3. Click **Draft**, then inspect its result in **Jobs** and open **Review**. Keyword matching selects the resume with the most whole-keyword matches; ties/no matches use the earliest registered variant. Review provides a manual override.
4. Verify company claims, sources, recipient, text and resume. AI-written notes and URLs are not independent verification. Save edits first, then approve the saved revision. Saving never approves.
5. Inspect **Queue**. Preview checks current eligibility and projects quotas without SMTP calls or database claims. **Send approved batch** queues a real send operation; it respects the configured window and limits. Preview/live jobs with different inputs cannot replace one another.
6. Inspect each job's actual results. **Tracking** supports reply scans, outcomes, due follow-ups, safe review of failed/canceled work, and reconciliation of uncertain attempts.

Imports use UTF-8 CSV, optionally with a BOM. Required headers: company_name, contact_email. Optional headers: domain, job_url, job_text, notes, contact_name, contact_title, contact_source. Valid rows persist independently; duplicates are skipped, row errors are reported, and a malformed tail stops further parsing while reporting already imported counts. Defaults: 1 MiB and 10,000 rows. The sample uses reserved example domains; replace the synthetic data before outreach.

Email syntax supports ASCII dot-atom local parts and domain labels, at most 254 characters overall and 64 in the local part. Quoted addresses and Unicode mailboxes are unsupported; use an ASCII/punycode address. Identity is trimmed and case-insensitive, without Gmail-specific plus/dot alias rewriting. **Check DNS** is optional, cached for five minutes, and bounded to three seconds; absence of MX is a warning, and DNS errors may be inconclusive. DNS does not prove deliverability.

## Credentials and configuration

Edit .env before starting both processes. Changes require restarting both.

- GEMINI_API_KEY and GEMINI_MODEL select generation. Missing/invalid/blocked output never becomes an approved draft. Model access and search-grounding support depend on the account and selected model.
- GMAIL_ADDRESS and GMAIL_APP_PASSWORD configure SMTP/IMAP. Use an app password where your account permits it, never the normal account password.
- Personal Gmail's IMAP access is always enabled; the old Enable IMAP toggle was removed in January 2025. Workspace administrators may restrict client access or app passwords. See [Google's email-client guidance](https://support.google.com/mail/answer/7126229?hl=en) and [app-password requirements](https://support.google.com/accounts/answer/185833?hl=en).
- OUTREACH_TIMEZONE defaults to Asia/Kolkata. Storage timestamps are UTC; windows, weekday metrics and daily quotas use the configured local timezone. Company limits cover the preceding rolling seven days.
- RESUME_ATTACH_MODE is attach or link. Attach mode requires a PDF inside RESUME_DIR, checked for size/header and approval-time content hash. Link mode requires HTTPS. A selected missing/changed file blocks delivery. No selected resume means no attachment/link.
- OUTREACH_DB_PATH, CONTEXT_PATH and RESUME_DIR resolve relative paths from the application directory, regardless of launch directory. Defaults and validated bounds are in config.py and .env.example.

Database files, backups, resume PDFs, credentials and candidate context are private local artifacts excluded from Git and source releases. Back them up separately. Removing a file from the current Git tree does not remove previous versions from repository history.

## Delivery and recovery

Approval covers a specific revision, recipient, company name and resume asset. Edits revoke approval; stale-tab review receives a conflict. Atomic claims and quota reservations prevent competing workers from submitting the same approved row. Network calls and randomized delays do not hold SQLite write locks.

SMTP cannot guarantee exactly-once delivery through a disconnect or process crash. A message gets a stable Message-ID and durable attempt before submission. Ambiguous/post-acceptance failures become **uncertain** and never retry automatically. Find that exact Message-ID in Sent Mail or provider records, then confirm delivered/not sent in Tracking. Confirmation is an operator assertion, not independent provider verification. A definitely failed/not-sent message returns to review and needs fresh approval.

Accepted sends continue counting after replies/bounces/outcomes. Outstanding and uncertain reservations conservatively consume quota even across dates until resolved. Suppressions block future preflight checks and cancel unsubmitted drafts; they cannot recall mail already submitted. Deferred approved messages need another explicitly queued batch. Batches are not rescheduled automatically.

Reply scans are read-only, fetch up to 500 new UIDs per operation, retain UIDVALIDITY-scoped progress, and require exact Message-ID/thread, sender and date evidence. Address-only historical messages and auto-replies are not counted as human replies. Messages without usable threading evidence require manual tracking; only confidently matched delivery reports can become bounces. Follow-ups require an actually sent, unanswered, due thread and share eligibility checks at drafting, approval and delivery. The default is one follow-up after seven days.

Funnel rates count **sent messages, including follow-ups**, not unique people. Sent totals remain stable through outcomes. Research claims still need human verification. Caps and delays do not guarantee inbox placement or compliance with provider account limits.

## Backup, check and restore

~~~powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py backup
# Optional explicit NEW destination:
.\.venv\Scripts\python.exe manage.py backup --output backups\manual-20261007.sqlite
~~~

Backup uses SQLite's backup API, including committed WAL data. It never overwrites an existing file. Protect backups like the live database.

To restore: stop **both** processes; preserve the current database with the backup command; restore the desired snapshot to a **new filename**, set OUTREACH_DB_PATH to that file, then run manage.py init and manage.py check before restarting. This avoids reusing stale WAL/SHM files. Do not copy a live SQLite main file alone or overwrite an open database. Test recovery using a separate directory before relying on a backup.

## Access controls

Local operation uses Host checks, same-origin writes, session CSRF tokens and debug disabled. Optional OWNER_PASSWORD plus a stable random SECRET_KEY of at least 32 characters enables owner login even locally.

Remote operation additionally requires COOKIE_SECURE=1, ALLOWED_HOSTS set to the exact public hostname, and HTTPS. Use a TLS reverse proxy with Waitress bound to loopback and configured with --url-scheme=https; the proxy must be the only network path to that listener. HTTP requests to remote hosts are rejected. Do not expose Flask's development server. This remains a single-owner tool; it has no team/tenant system. Public reverse-proxy/TLS deployment has not been exercised in the local regression suite.

## Development and verification

~~~powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe scripts/check_source.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip_audit
.\.venv\Scripts\python.exe scripts/release.py
~~~

Node.js is needed for the JavaScript syntax check; Chromium is needed for browser tests. Tests use temporary databases and fake SMTP/IMAP/Gemini providers. Real networking is blocked except the local browser server. They must not use production databases or credentials.

Runtime/development locks include exact versions and hashes. To update dependencies, edit requirements.txt/requirements-dev.txt and regenerate both locks with uv pip compile --python-version 3.12 --generate-hashes, then install in a clean environment and rerun the full gates. GitHub CI runs on Windows and Linux for pushes/PRs and weekly advisory refreshes.

scripts/release.py builds only committed source with git archive, prints its commit, and rejects private/generated tracked paths. Uncommitted edits and unrelated local scripts are excluded. It creates a new ZIP under dist and never overwrites a previous release. See [the implementation plan](docs/AUDIT_IMPLEMENTATION_PLAN.md) and [verification progress](docs/IMPLEMENTATION_PROGRESS.md) for issue-level evidence and remaining integration checks.
