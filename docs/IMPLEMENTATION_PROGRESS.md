# Repair progress

The original findings remain in AUDIT_IMPLEMENTATION_PLAN.md; this log records actual implementation and verification, not just planned work.

## Foundation, review and delivery

- Added isolated test fixtures with real networking blocked, validated timezone/settings, reproducible hashed runtime/development locks, and an isolated upgraded `.venv`.
- Added versioned transactional schema upgrades, pre-upgrade SQLite backups, relationship/identity guards and attempt/event history. Legacy approvals without a snapshot are revoked without dropping history.
- Draft edits revoke approval; revisions reject stale review; state rules prevent sent messages being reapproved and unsent messages receiving outcomes.
- SMTP claims and quota reservations are atomic across connections; snapshots include recipient and attachment content; uncertain delivery never retries automatically.
- Restored resume lookup, PDF validation and personalized attachments. Renamed candidate profile module to stop shadowing stdlib profiling.
- Verification: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`: **26 passed**. Includes two-worker duplicate delivery, quota contention, SMTP success plus DB failure, connection cleanup, recovery, stale approval, modified PDFs and legacy migration tests.

Remaining work includes validated import/API/setup flows, AI generation, replies/follow-ups, durable jobs, actual browser regression, documentation and CI. No real-provider integration has been run.

## Contact, drafting, reply and follow-up repairs

- Imports now validate headers/rows and report skipped duplicates; canonical addresses and concurrent identity guards prevent duplicate contacts.
- AI generation validates schema/content, closes clients, uses verified profile/context, retains research and grounding metadata, and reserves generation per recipient to prevent concurrent drafts. Provider failures create no approvable draft.
- Follow-ups share one due/answered/suppressed/limit policy across listing, approval and delivery. Replies invalidate queued follow-ups and preserve advanced outcomes.
- IMAP uses read-only incremental UID scanning and exact Message-ID/date/sender validation; historical/address-only/automatic messages do not become human replies. Failures are visible and connections are cleaned up.
- Statistics count actual sent messages cumulatively and use local send dates and resume IDs.
- Personal context is removed from the tracked tree while its local file is preserved; setup uses an ignored candidate_context.txt and an example template.
- Verification: full isolated suite **58 passed**, including concurrent generation/import, invalid output, saved research, resume drafting, early/replied follow-ups, false reply rejection and cumulative outcomes.

## Protected API, durable jobs and browser workflow

- Replaced blocking provider endpoints with durable, idempotent jobs and a process-locked worker with explicit crash recovery. Job results report actual sent/deferred/failed/uncertain counts.
- Added typed JSON errors, revision-aware review endpoints, loopback Host/Origin checks, CSRF protection, optional single-owner login and production server dependency.
- Added browser setup for companies, contacts, candidate facts, resumes and suppression; safe DOM rendering; explicit dirty-review handling; keyboard dialogs and responsive layouts.
- Browser verification found and fixed nested-form rendering and a navigation race during writes.
- Verification: full isolated suite **80 passed**; fresh setup → mocked draft → edit → approval → one mocked SMTP submission → reply outcome; 375/768/1440px screenshots inspected, keyboard focus/Escape checked. No real-provider operations performed.

## Migration recovery and delivery edge cases

- Schema v2 backfills legacy thread roots, retains reviewed v1 approvals, reports invalid threads, permits safe rejection of mismatched legacy rows, and prevents direct duplicate active initial drafts. Concurrent startup rechecks schema ownership.
- Backup refuses overwrite; interrupted migrations roll back; an SQLite backup is restored and checked in regression tests.
- Preview and live-send jobs cannot be coalesced together. Preview projects batch quotas without claims; all candidates receive a result after transport failure; interrupted connections close safely.
- Local midnight, DST and legacy timestamp formats count correctly. Follow-up persistence rechecks eligibility atomically after generation.
- Profile validation precedes candidate-facts writes; optional bounded/cached DNS checks are available; remote mode requires owner authentication and HTTPS; canceled unsent work can return to review.
- Lists have UI pagination, review shows the selected delivery asset, and operation status polls real job results.
- Verification: **117 passed** in the full suite, including real Gemini SDK model/error objects with fake transport, incremental IMAP and UID reset, and the browser workflow. No live Gmail/Gemini requests.
