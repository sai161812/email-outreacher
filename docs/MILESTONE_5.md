# Milestone 5 — accounts, release and upkeep

Scope: R16–R17 only. **Software implementation is complete; R16 live acceptance
remains pending.** No overall Milestone 5 completion is claimed while actual
account/receipt/asset/reply acceptance is unverified. R11's separate live/human
quality gate remains pending in Milestone 3.

**R16 implementation**

- Explicit SMTP TLS/login/NOOP and IMAP login/read-only mailbox diagnostics,
  available through `manage.py check-accounts` and Settings/Jobs. They do not
  submit messages, change mailbox state or advance reply cursors. Safe status
  categories, account/configuration scope and check time are retained; provider
  error text and passwords are redacted.
- Separately invoked `manage.py check-model` uses one synthetic draft and the
  existing maximum-three-call budget. It tests configured model/search/schema
  access without saving, approving or sending a draft. Missing configuration
  returns a zero-call not_configured result.
- [LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md) and an unfilled private-record template
  cover verified facts, actual resume or deliberate No resume, the designated
  recipient, review/approval, receipt, receiver authentication, assets, Sent Mail
  identity, thread headers, real reply and uncertain-outcome reconciliation.
- Current official model deprecation, Gmail sender and app-password guidance was
  checked and linked in that guide. No provider/model was changed merely because
  newer models exist. No bulk subsystem or speculative OAuth migration was added.

Actual local checks on 12 November 2026 returned Gmail/Gemini **not_configured**.
The profile exists, saved verified facts do not, and both active resume assets are
unusable. No actual resume, reviewed facts, designated test recipient or reviewed
test message was supplied. No credentials were fabricated/read from unrelated
services, no private facts were silently imported and no placeholder was relabeled
as a valid resume. No paid model call or live email was performed.

**R17 implementation**

`run.py start|status|stop` and optional `start.ps1` provide a small local foreground
launcher with port/worker/launcher conflict checks, actionable runtime errors,
private logs and an authenticated loopback control socket. Readiness must match
the launcher instance before starting the worker. Managed children watch private
stdin pipes and exit if the supervisor disappears. Stop controls owned process
handles, never arbitrary PIDs from a stale file. Restart recovers possible SMTP
submissions as uncertain; it does not create a resend attempt.

Windows/Linux CI, scheduled advisory checks, hashed dependencies and committed-
source packaging remain in place. Runtime state, control tokens, locks, credentials,
databases, PDFs, backups and history-rewrite scripts are excluded from releases.
The clean-install smoke additionally exercises launcher status and unconfigured
account/model diagnostics without provider calls.

[OPERATIONS.md](OPERATIONS.md) documents normal startup/shutdown, upgrades, logs,
backup/restore, exact release checks and a maintenance checklist. `audit_local.py`
inventories preserved archives/backups/environments and scans reachable Git blobs
without printing candidate secret values. The initial review covered 8 refs and
466 unique blobs, with zero known credential-shape candidates and no large blobs
skipped. Two historical private context paths remain reachable; history review
and clean source release privacy are distinguished. No cleanup, history rewriting,
force-push, credential probing or unrelated fix.py/rewrite.py execution occurred.

The final exact-commit suite, package, advisory and restore evidence is recorded
below after the final gates. Tests use synthetic providers/temp data. The full
software regression suite does not substitute for the remaining R16 live steps.
