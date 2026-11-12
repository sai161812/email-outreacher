# Product acceptance and startup

The current verification record is [Milestone 5](MILESTONE_5.md), with structured
results in [milestone5_verification.json](audit/2026-11-12/milestone5_verification.json).
Application source **3b034536047c** passed **303 tests**, including 20 Chromium
cases, on 12 November 2026. The exact committed archive installed cleanly; source,
dependency, worker recovery, schema 7 and backup/asset restore checks pass.

Milestone 5 software is implemented. **R16 live acceptance is pending**, so neither
Milestone 5 nor the overall plan is fully accepted. Gmail/Gemini are unconfigured,
verified facts are not saved and the two active resume files are unusable
placeholders. Supply an actual resume or deliberately select No resume, review
and save facts, then follow [live acceptance](LIVE_ACCEPTANCE.md) for the separately
authorized recipient/message and real receipt/authentication/thread/reply checks.
R11 live-provider/human quality acceptance remains pending in Milestone 3.
No live messages or paid model requests were made during this milestone.

For current installation, use the [README](../README.md); for start/status/stop,
private logs, upgrades, backup/restore and maintenance, use [OPERATIONS.md](OPERATIONS.md).
After installation, `run.py start` starts the server and worker; `run.py stop`
or Ctrl+C stops them with conservative uncertain-delivery recovery on restart.
Connection diagnostics verify access only; they do not establish delivery or
reply-scan freshness. Historical private context remains reachable in Git history;
review that exposure before presenting the repository publicly.

## Historical verification and startup notes

The records below preserve earlier results and setup observations. Use the current
verification and operation links above for the present checkout; earlier data,
duplicate, migration and asset descriptions are not new acceptance claims.

Current Milestone 4 application source **ea80456** passed **293 automated tests**,
including 19 Chromium cases, clean committed-release installation and schema 7
migration/restore checks on 12 November 2026. See [Milestone 4 evidence](MILESTONE_4.md).
R11 live-provider/human quality acceptance is still pending in Milestone 3;
personal resume/account setup and Milestone 5 remain outstanding.

Milestone 3 application source **beaf2bf** passed **273 automated tests**, including
12 browser cases, clean committed-release installation and schema 6 migration/
restore checks. See [Milestone 3 evidence](MILESTONE_3.md). R09/R10 are complete;
R11 live draft quality and human ratings remain pending in Milestone 3. This is
not a claim that the entire hiring plan or live account acceptance is complete.

Current Milestone 2 application source **1d7b927** passed **258 tests**, including
11 Chromium cases, source/dependency checks and a clean committed-release install
on 11 November 2026. The live database is now schema 5 with preserved submitted
history. See [Milestone 2 acceptance](MILESTONE_2.md) for current evidence. Personal
resume/facts setup and live account acceptance remain deferred to Milestone 5.
The October results below are preserved as historical verification.

The local single-owner application passed the updated acceptance suite on source commit **b1b1e26** (9 October 2026): **223 tests**, including 11 real Chromium workflows/checks against fake providers, source checks, dependency checks and an isolated installation of the committed source ZIP. The release smoke check exercised Waitress, schema initialization/integrity, worker startup and SQLite backup. No real emails or paid AI requests were used.

The overall workflow review passed 223 tests and all Windows/Linux release gates in [run 37949776032](https://github.com/sai161812/email-outreacher/actions/runs/37949776032). The tested local package is `dist/email-outreacher-b1b1e26f7092.zip`. See [WORKFLOW_AUDIT.md](WORKFLOW_AUDIT.md) and `audit/2026-10-09/workflow_verification.json` for the seven additional defects repaired. Drafting guidance remains in [DRAFTING_QUALITY.md](DRAFTING_QUALITY.md); its earlier verification is preserved in `audit/2026-10-09/drafting_verification.json`.

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

Milestone 1 restored `.venv` using workspace-local Python 3.12.16. The previous
environment is preserved in `.venv-preserved-milestone1`. For a new machine or
extracted source package, install Python 3.12 and follow the README's locked
installation steps first. October verification below is historical; see
[Milestone 1 progress](MILESTONE_1.md) for current checks and remaining personal setup.

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
3. Add or select a company/contact. In Contacts choose automatic resume matching, a specific variant, or No resume before drafting, then inspect the job result. Confirm that your Gemini account successfully produces a draft.
4. Verify the recipient, facts, content and selected resume in Review. Save changes, then approve the saved revision. New edits typed during a save require another save.
5. Preview the approved batch and inspect its result. Queue a real send only when you intend to send it; the worker enforces the configured window and quotas. Defaults allow weekdays 09:00–18:00 Asia/Kolkata.
6. Verify the first intended message in Sent Mail and check its recipient's receipt. Run Check replies after receiving a real response. Ambiguous delivery requires manual Message-ID reconciliation in Tracking.

## Verification scope

| Area | Acceptance evidence |
| --- | --- |
| Setup/import/contact management | Validated APIs, CSV partial failures, concurrent duplicate guards, browser setup |
| Candidate settings | Atomic profile/facts saves, database backup coverage, file fallback compatibility, unsaved-edit protection |
| Draft review | Saved revisions, dirty-state protection during slow writes, serialized actions, safe rendering |
| Delivery | Atomic claims/quotas, MIME assets, classified failures, restart recovery, atomic reconciliation |
| Replies and follow-ups | Exact threading, per-recipient permanent bounces, bounded UID scans, due-thread browser lifecycle |
| Tracking metrics | Actual sends, stable cumulative outcomes and explicit recorded interview evidence |
| Operations | Clean locked runtime install, Waitress, worker, integrity check, consistent backup, source packaging |
| Live accounts | **Pending account configuration and actual provider checks** |
| Public deployment | **Not exercised**; the supported acceptance target is local loopback use |

See `IMPLEMENTATION_PROGRESS.md` for the fixes and CI evidence. This verifies the tested workflows and failure cases; it is not a guarantee that all possible defects or provider failures are eliminated.
