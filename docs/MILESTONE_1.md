# Milestone 1 execution — 11 November 2026

Base source: `fe2bec9`; implementation is in the current uncommitted working tree.
Scope: R01 and R02 of `RELIABILITY_AND_HIRING_PLAN.md` only.

Status: **Complete under revised scope.** The owner requested deferring personal
resume registration; resume registration and candidate-facts review are now
tracked in Milestone 5 / R16 before live acceptance. Milestones 2–4 can proceed.

**Implemented**

- Installed workspace-local CPython 3.12.16 and rebuilt `.venv` from hashed locks.
  The previous environment is preserved as `.venv-preserved-milestone1`;
  the separate original `venv` is retained. `.python` is required by the new
  environment and excluded from version control/source packaging.
- Added `manage.py diagnose`: runtime, resolved paths, schema, configuration
  presence and worker last-seen state; no initialization, secrets or provider calls.
  Settings explicitly distinguishes configuration presence from verified access.
- Added bounded PDF input reading and pypdf parsing, encryption/page validation,
  upload rejection before storage, and real PDF fixtures. Approval hashes remain.
- Added `manage.py backup --bundle` and `restore` with database/PDF checksums,
  asset path rebasing, new destination requirements and approval invalidation.
  Fixed SQLite backup connections remaining open on Windows.
- Added Settings preview of `context.txt`; importing requires reviewing the text
  and saving. Existing facts are never overwritten by a preview request.
- Added regression cases and a schema-only fixture matching the actual legacy
  database, including extra legacy tables. The fixture contains no personal data.
- Updated certifi, dnspython, filelock and pyasn1 after the current advisory scan
  found vulnerabilities. Other locked package versions were retained. pypdf is
  the single added runtime dependency for the required PDF validation.

**Local data execution**

A consistent original snapshot, migrated copy, backup bundle and restored copy
are preserved under ignored `backups/milestone1-c492cfef`. Copy migration and
restore passed integrity checks, preserving 6 companies, 15 contacts, 1 email and
2 resume registrations. Extra legacy tables were preserved.

Following rehearsal, `manage.py init` migrated the actual database to schema 2
with its automatic pre-migration backup. Three duplicate groups were resolved by
keeping the record with correspondence first, then the most populated record,
then the oldest record on ties. Four redundant contacts were archived; all
15 records and the replied email remain. The protected decision ledger is
`backups/milestone1-contact-resolution.json`. Current integrity is `ok`, foreign
key violations are zero and there are no active duplicate groups.

**Verification**

- Final consolidated regression: **231 passed**, including 11 browser cases,
  in 50.67 seconds. Command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.
- Eight Milestone 1 cases cover real/malformed/encrypted/empty PDFs, bundle
  restoration, tamper rejection, diagnostics, observed-schema preservation,
  non-saving facts preview and malformed upload cleanup.
- Source syntax/private-file checks, `pip check`, JavaScript syntax and whitespace
  checks passed.
- Updated installed dependency audit: **no known vulnerabilities found**.
  Raw current/initial reports are in ignored `test-results/milestone1-dependency-*.json`.
- Clean-install smoke passed using `dist/milestone1-final-working-tree.zip`, built from current
  source bytes, including the new modules/tests. It is explicitly a working-tree
  acceptance artifact; `scripts/release.py` continues to ship committed source.
  The clean hashed install, Waitress read routes, schema initialization/integrity,
  worker startup and SQLite backup passed. Source hashes are retained in
  `test-results/milestone1-source-hashes.json`. Subsequent documentation-only
  verification updates are not included in that acceptance archive.

**Deferred personal setup / acceptance limits**

R01 and R02 software/runtime acceptance is complete. Personal setup is deferred
to Milestone 5 / R16, when the owner can supply the actual resume PDF and review
candidate facts. The current
registered PDF is a 30-byte malformed placeholder; validation correctly blocks it.
No replacement biography or resume was invented. Use Settings to register the
real PDF and select it for future drafts. Preview legacy facts there, verify them,
then save. No facts have been imported without review.

Gemini/Gmail are unconfigured in the effective environment. Live account access,
AI generation and email delivery were not exercised and belong to later account
acceptance. No emails were sent. Milestones 2–5 were not implemented.
