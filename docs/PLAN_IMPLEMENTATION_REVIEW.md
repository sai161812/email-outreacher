# Implementation review and fix plan

Reviewed 15 November 2026 against `59feb8d`, using
[RELIABILITY_AND_HIRING_PLAN.md](RELIABILITY_AND_HIRING_PLAN.md).
This is a review and proposed fix sequence, not an implementation of the fixes.
The owner's resume update remains deferred; no replacement facts or assets are
invented, and an absent resume is not counted as a new software defect.

**Current evidence**

- Full existing regression suite rerun: **303 passed in 137.38 seconds**, including
  20 Chromium cases. Command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.
- Tracked source/JavaScript checks, `pip check` and whitespace checks pass.
- Effective runtime: Python 3.12.16, database schema 7. Read-only diagnostics still
  report Gmail/Gemini unconfigured and no worker heartbeat.
- Four additional isolated probes reproduced the findings below using temporary
  databases, synthetic PDF/facts and fake generation. Their four passing assertions
  confirm the defects' observed behavior; they are not fixes or acceptance tests.
  The local probe file is `test-results/plan_review_probes.py` (ignored).
- Source review covered the plan, milestone evidence, delivery/reply/approval,
  generation/evidence, jobs/request recovery, resume management, metrics, diagnostics,
  launcher and release/restore paths. The previously recorded clean-install and
  Windows/Linux CI results remain historical evidence from 12 November; neither
  fresh installation nor remote CI nor current advisory lookup was rerun here.
  `pip check` verifies compatibility, not current security advisories.
- No live email, mailbox connection or paid model call was made. Production data,
  the personal resume and unrelated untracked scripts were left unchanged.

**Findings, in fix order**

| ID | Priority / plan item | Finding and impact | Smallest proposed fix |
| --- | --- | --- | --- |
| F01 | P1 / R02, R17 | Restore can report success with a referenced PDF omitted from the manifest. The restored row keeps its old absolute path, and the new asset directory is empty. On another machine this breaks asset access; on the same machine it can conceal an incomplete restore. | Validate the manifest against every database row with a nonempty file path before creating destinations. Require exactly one matching asset per referenced row, validate all hashes, integrity and foreign keys, then restore/remap. |
| F02 | P1 / R10 | Follow-up generation stores the initial-outreach request in `input_snapshot_json.request`, rather than the actual follow-up request. New follow-ups also omit the changed-role warning when the role is edited during generation. A reviewer can see an inaccurate request record and no stale-context warning. | Build the actual follow-up request once, use that same captured request for generation and storage, and run the existing stale-role check before storing. Apply the request correction to follow-up regeneration too. |
| F03 | P2 / R12, R16 | Invalid cached connection-check data can break the entire Settings endpoint. A record with matching scope but missing result fields raises `KeyError` and produces HTTP 500. Optional diagnostic metadata should not prevent setup/recovery. | Validate the cached report's shape and required fields. Treat malformed data as unavailable/not verified with an explicit recheck action; preserve access to Settings. Never infer a successful check. |
| F04 | P2 / R17 | A launcher state file containing valid JSON `null` causes `run.py status` to raise uncaught `TypeError`. Related control-listener input assumes a JSON object before reading `.get`. | Validate state/control request types and field ranges, handle malformed state with an actionable unknown/unavailable result, and keep the listener alive after malformed requests. Continue to control only authenticated, owned children. |

F01 reproduction: create a valid synthetic PDF and normal bundle; remove its
entry from `manifest.assets` while retaining the database and its valid checksum;
restore into new destinations. Restore returns success, but the registration
still points to the original source path. This requires an incomplete/modified
manifest; it does not mean ordinary valid bundles currently fail.
Evidence: `operations.py:61`, especially the manifest-only iteration at line 72.

F02 reproduction: create a due synthetic parent with an opportunity, intercept
`_generate`, change that opportunity during the call, and return a valid synthetic
follow-up. The saved request differs from the intercepted request, and the saved
warnings omit the changed-role warning. Approval is still required; this finding
does not establish an automatic send or approval bypass.
Evidence: `composer.py:38`, `compose_follow_up` at line 301 and
`compose_follow_up_and_store` at line 313; compare `snapshot_warning` at line 42
with the initial-draft use at line 296 and follow-up storage at line 349.

F03 reproduction: with synthetic configured credentials, put a JSON object
containing only the current scope into `settings.mail_connection_check`; GET
`/api/settings` returns 500 without contacting a provider.
Evidence: `account_checks.py:59` and `app.py:136`.

F04 reproduction: write `null` to a temporary state file and call
`run.control(path, 'status')`; it raises `TypeError`. The listener's analogous
non-object request issue is source-derived, not exercised against a live process
in this review. Evidence: `run.py:21` and `run.py:82`.

**Coverage against all milestones**

| Milestone | Assessment |
| --- | --- |
| 1 / R01–R02 | Runtime, migration, PDF validation and ordinary restore checks pass. F01 needs a restore-validation follow-up. Personal resume remains deferred. |
| 2 / R03–R08 | Existing tests pass for uncertain delivery, fixed batches, sender binding, held replies, scan freshness and SMTP rejection/suppression policy. No new defect was confirmed in these reviewed paths. |
| 3 / R09–R11 | Manual drafts, regeneration, role/project inputs and evaluation tooling exist. F02 leaves R10 incomplete at the follow-up evidence boundary. R11 live output/human acceptance remains pending within Milestone 3. |
| 4 / R12–R15 | Existing recovery/UI/resume/funnel tests pass. F03 adds a Settings recovery gap. No hiring-uplift claim is supported by automated tests. |
| 5 / R16–R17 | Diagnostics, launcher, release and maintenance tooling exist. F01/F03/F04 need fixes. R16 real account/delivery acceptance remains pending independently of the resume update. |

No new P0 delivery defect was reproduced. Passing the existing suite does not
close these newly demonstrated coverage gaps or the explicit live acceptance gates.

**Implementation sequence and acceptance checks**

1. Fix F01 in one commit: compare database asset identities with the manifest
   before writing outputs. Cover omitted/unknown/duplicate assets, checksum or
   database failure and a normal portable restore. On validation failure, leave
   neither destination published. Preserve submitted history and invalidate old
   approvals as today. Use synthetic PDFs; this needs no personal resume.
2. Fix F02 in one commit: share a small follow-up request builder between generation
   and snapshot capture, including regeneration, and reuse the stale-role warning.
   Assert actual provider input equals the saved request, original thread content
   is retained, concurrent role changes are visible, and failed regeneration
   preserves the prior draft. Keep the current call/revision budget.
3. Fix F03 in one commit: add defensive cache parsing and endpoint/browser coverage
   for invalid JSON, null, missing keys and stale scope. Settings must load and
   let the owner recheck; valid scoped results must still show their check time.
4. Fix F04 in one commit: validate state/control payloads and test malformed state,
   malformed local requests followed by a working status/stop, duplicate start,
   and conservative interrupted-send recovery. No new service manager is needed.
5. Run the full suite, source checks, current dependency advisory checks and clean
   installation of the exact committed archive; verify Windows/Linux CI and update
   the current verification record. Commit and push each meaningful change.

**Separate acceptance work and deferred work**

- R11 remains in Milestone 3: configured Gemini access and an explicit bounded
  live evaluation, followed by genuine human ratings of all 12 cases. Require
  no hard factual failures and at least 10 samples needing no substantial rewrite.
  Synthetic evaluation can proceed without the personal resume once access and
  paid execution are authorized. An owner-specific set waits for verified facts.
- R16: configure accounts and review/save accurate candidate facts, run explicit
  diagnostics, then perform the separately authorized test-recipient workflow in
  [LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md). Record real receipt, receiver-added
  authentication, sender/thread identity and a matched human reply. Do not mark
  this passed from fake-provider tests.
- **Personal resume update stays deferred at the owner's request.** Later, register
  and preview the real PDF for attachment acceptance. Intentional No resume remains
  supported, but the review does not silently select it on the owner's behalf.
- Historical private context is already documented as reachable in Git history.
  That privacy review remains open before portfolio publication; it is not a new
  confirmed credential leak. Do not rewrite shared history as routine cleanup.

Keep Flask, SQLite, one worker, manual approval and the current UI. These fixes
need no new dependencies, new queue system or autonomous outreach.
