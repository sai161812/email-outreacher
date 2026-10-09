# Product acceptance and startup

The local single-owner application passed the updated acceptance suite on source commit **bed935e** (9 October 2026): **209 tests**, including real Chromium workflows against fake providers, source checks, dependency checks and an isolated installation of the committed source ZIP. The release smoke check exercised Waitress, schema initialization/integrity, worker startup and SQLite backup. No real emails or paid AI requests were used.

The final drafting release passed 209 tests and all Windows/Linux release gates in [run 37945988485](https://github.com/sai161812/email-outreacher/actions/runs/37945988485). The tested local package is `dist/email-outreacher-bed935ebb9ec.zip`. Current drafting guidance is in [DRAFTING_QUALITY.md](DRAFTING_QUALITY.md), with verification in `audit/2026-10-09/drafting_verification.json`; earlier operational evidence remains in `audit/2026-10-07/verification_product.json`.

The existing visual design is retained. A separate UI design pass can follow functional acceptance.

## Required account setup

This checkout had no `.env`, Gemini API key or Gmail credentials at acceptance time. Live Gemini generation and Gmail SMTP/IMAP therefore remain unverified. Configure these before real outreach; automated checks cannot establish your account's permissions, billing or mail delivery.

From a **fresh PowerShell terminal**:

~~~powershell
cd D:\Workspace\DEVEL\email-outreacher
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
~~~

Set `GEMINI_API_KEY`, `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`. Keep the other defaults unless you intend to change them. See the README for model/account requirements. Do not paste credentials into Git, issue reports or screenshots.

Fresh terminals matter if you previously ran the UI-only preview: environment variables such as `OUTREACH_DB_PATH`, `CONTEXT_PATH` and `RESUME_DIR` override `.env`. Stop old server/worker processes before starting the updated product.

## Start the installed product

The existing `.venv` is installed. For a new machine or extracted source package, follow the README's locked installation steps first.

Terminal 1:

~~~powershell
cd D:\Workspace\DEVEL\email-outreacher
.\.venv\Scripts\python.exe manage.py init
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:5000 app:app
~~~

Terminal 2, also fresh:

~~~powershell
cd D:\Workspace\DEVEL\email-outreacher
.\.venv\Scripts\python.exe worker.py
~~~

Open **http://127.0.0.1:5000**. Keep both terminals running. Stop them with Ctrl+C when finished. Initialization backs up supported older databases before migration. The actual legacy database was validated through a protected copy; it was not migrated in place during testing.

## First real workflow

1. In Settings, save your name, target role/level and verified project facts with concrete outcomes. Register a resume suitable for the configured attachment/link mode. See `candidate_context.example.txt` for the evidence the improved generator needs.
2. Review existing duplicate-contact groups in Settings. Three groups were present in the original data; no records were merged or deleted automatically.
3. Add or select a company/contact, draft, and inspect the job result. Confirm that your Gemini account successfully produces a draft.
4. Verify the recipient, facts, content and selected resume in Review. Save changes, then approve the saved revision. New edits typed during a save require another save.
5. Preview the approved batch and inspect its result. Queue a real send only when you intend to send it; the worker enforces the configured window and quotas. Defaults allow weekdays 09:00–18:00 Asia/Kolkata.
6. Verify the first intended message in Sent Mail and check its recipient's receipt. Run Check replies after receiving a real response. Ambiguous delivery requires manual Message-ID reconciliation in Tracking.

## Verification scope

| Area | Acceptance evidence |
| --- | --- |
| Setup/import/contact management | Validated APIs, CSV partial failures, concurrent duplicate guards, browser setup |
| Draft review | Saved revisions, dirty-state protection during slow writes, serialized actions, safe rendering |
| Delivery | Atomic claims/quotas, MIME assets, classified failures, restart recovery, atomic reconciliation |
| Replies and follow-ups | Exact threading, per-recipient permanent bounces, bounded UID scans, due-thread browser lifecycle |
| Operations | Clean locked runtime install, Waitress, worker, integrity check, consistent backup, source packaging |
| Live accounts | **Pending account configuration and actual provider checks** |
| Public deployment | **Not exercised**; the supported acceptance target is local loopback use |

See `IMPLEMENTATION_PROGRESS.md` for the fixes and CI evidence. This verifies the tested workflows and failure cases; it is not a guarantee that all possible defects or provider failures are eliminated.
