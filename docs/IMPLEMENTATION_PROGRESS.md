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
