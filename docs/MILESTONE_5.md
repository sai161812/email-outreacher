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

**Final local verification — 12 November 2026**

Application source `3b034536047cba20b06c315947fc4287182e1c0f` includes the diagnostic
and launcher implementation commits `564edbb` and `c56391f`. Verification-only
documentation follows that source commit. Machine-readable results are in
[milestone5_verification.json](audit/2026-11-12/milestone5_verification.json).

- Full suite: `python -m pytest -q -p no:cacheprovider
  --junitxml=test-results/milestone5-final.xml` — **303 passed in 113.20 seconds**,
  including 20 Chromium workflows and a separate loopback launcher lifecycle case.
  New coverage verifies non-sending diagnostics, safe failures/configuration
  scope, visible Settings/Jobs results, startup/port/duplicate protection, parent
  pipe closure and stop/restart of a submitting attempt as uncertain with one
  retained attempt. Existing migration, readable synthetic PDF restore, review,
  bounded generation, delivery and reply regressions also pass.
- `scripts/check_source.py`, JavaScript syntax and `git diff --check` pass.
  `pip check` passes. Both the 38 locked runtime dependencies and the entire
  installed development/runtime environment report no known vulnerabilities
  under the current `pip_audit` checks. This is time-specific advisory evidence.
- Both Windows and Linux CI passed every gate for this exact source in
  [run 43275806808](https://github.com/sai161812/email-outreacher/actions/runs/43275806808),
  including regression/browser tests, installed dependency advisories, source
  packaging and clean-release runtime installation.
- Exact release: `dist/email-outreacher-3b034536047c.zip`, SHA-256
  `7d26adcb23a22a99141465e2a222bddae3eea5a9ea31d83752b8b7a1372cc3a0`.
  `scripts/smoke_release.py` created a new environment, installed hashed runtime
  dependencies, checked Waitress routes, schema 7 integrity, one worker iteration,
  backup, launcher status and zero-call unconfigured account/model diagnostics.
- A consistent copy of the actual database was initialized and bundled/restored
  into new paths: schema 7, integrity `ok`, zero foreign-key violations, unchanged
  company/contact/email/resume/opportunity counts and submitted message history/
  generation inputs. Both stored files were preserved byte-for-byte; preservation
  does not make these existing placeholders valid resumes. The live database was
  not changed by the rehearsal. Private evidence stays in ignored backups.
- Final reachable-history review: **8 refs, 494 unique blobs, zero known
  credential-shape candidates, zero oversized blobs skipped**. Two historical
  private context paths remain reachable. Inventory: 14 dist files, one release
  file and 73 backup files; four virtual environments retained. The exact source
  ZIP above is the current tested release. No files or history were removed.

Tests use synthetic providers/temp data and cannot substitute for the remaining
R16 live steps. No paid model requests or live email submissions occurred.
**R17 local acceptance passes; R16 live acceptance remains pending.**
