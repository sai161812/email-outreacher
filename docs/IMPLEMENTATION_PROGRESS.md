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
