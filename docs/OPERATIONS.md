# Local operation, releases and upkeep

**Start and stop**

Install supported Python 3.12 and the hashed runtime requirements from README.md.
A copied or broken virtual environment must be recreated, not reused. On this
workspace `.venv` depends on the private `.python` runtime; keep both. New machines
install their own Python and environment from the source package.

~~~powershell
.\.venv\Scripts\python.exe run.py start
# In another terminal:
.\.venv\Scripts\python.exe run.py status
.\.venv\Scripts\python.exe run.py stop
~~~

Use `--port 5001` for an alternative local web port. Windows also has
`start.ps1 start|status|stop -Port 5001`; if local script policy blocks it, use the
Python commands instead of changing machine policy. Linux/macOS use
`.venv/bin/python run.py start|status|stop`.

The launcher stays in its foreground terminal and starts only one loopback
Waitress server and worker for the database. It confirms its own server readiness
before starting the worker. Logs are under ignored `.runtime/logs`; protect them
like the database. No login/model diagnostic or send is queued automatically by
startup. Previously queued owner operations can resume when the worker starts.

Use Ctrl+C or the authenticated local stop command. The helper controls only its
owned children; it never kills a PID from a stale file. Private stdin pipes stop
managed children if their supervisor disappears. It rejects occupied ports,
duplicate launchers and an already running external worker. Do not mix it with
the separately documented manual server/worker commands. Stop before upgrading
code or editing `.env`. This helper is for local operation, not a TLS deployment
or a Windows service installer.

Stopping can interrupt SMTP after possible acceptance. The durable submitting
attempt is recovered as uncertain on restart and is never resent automatically.
Inspect Tracking and reconcile the exact Message-ID before considering another
reviewed send. Ending a launcher process is not evidence that a message was not sent.

**Release and recovery**

Use the current verification record linked at the start of PRODUCT_READINESS.md.
It identifies the tested application commit and ZIP. `scripts/release.py` packages
committed source only and refuses overwriting an existing archive. Local edits,
private artifacts and unrelated scripts are not release inputs.

Before a release: full pytest/browser/provider-failure/recovery gates, source and
JavaScript syntax checks, `pip check`, current advisory review, committed-source
packaging and `scripts/smoke_release.py <exact-zip>`. The clean-runtime smoke checks
Waitress, schema, worker, launcher status, unconfigured diagnostics and consistent
backup. Windows/Linux CI and weekly advisory refresh remain enabled. A local pass
does not imply a remote CI pass; inspect the pushed commit's CI separately.

Back up database and referenced resumes together using `manage.py backup --bundle`.
Keep credentials in separately protected storage. To rehearse restore, stop both
processes, choose new database/resume paths, restore, set both configuration paths,
then initialize/check and open the selected assets before starting. Verify row
counts, submitted history, facts and every chosen resume; a successful SQLite
integrity check alone does not prove personal setup or resume quality.

**Artifact and Git review**

~~~powershell
.\.venv\Scripts\python.exe scripts/audit_local.py --output backups\local-review-<new-name>.json
~~~

This inventories ZIPs/backups/environments and scans reachable blobs across all
local heads, remote-tracking refs and tags for private paths and known credential
shapes. Candidate values are never printed; findings need private review. It does
not prove absence of every possible secret or validate a candidate credential.

The 12 November baseline review found four environments, 13 source ZIPs under
dist, one older release ZIP and 63 backup artifacts. `.venv` is active; other
environments/archives are preserved. No deletion was performed. The record is
under ignored `backups/milestone5-local-review.json`; counts grow with new evidence.
The current release is the commit-specific ZIP named by the latest verification
record, not whichever older ZIP happens to sort first in the local dist folder.

Historical `context.txt` versions remain reachable. The shape scan found no
credential-shaped candidates at baseline, but historical candidate facts may be
private. Review that exposure before presenting repository history as a portfolio.
Clean source releases exclude private context. Shared history is preserved; no
force-push, secret rotation, credential validation, automatic history rewriting or
unrelated fix.py/rewrite.py execution was performed. If an actual secret is found,
handle its exposure specifically and privately before publication.

**Maintenance**

- Back up before upgrades and periodically rehearse restore to new paths, including
  PDFs and saved facts. Retain previous snapshots until the restored copy is checked.
- Review weekly CI/dependency advisories. Change affected packages deliberately,
  regenerate hashed locks and rerun compatibility/security/regression/release gates.
- Check provider deprecation notices and account policies after failures or before
  changing the model/authentication method. Keep defaults unless evidence requires change.
- Repeat explicit connection/model compatibility checks after relevant configuration
  changes. Record controlled live acceptance separately from automated tests.
- Recheck unresolved attempts, suppressions, reply backlog and worker health before
  outreach. Stop follow-ups after replies, opt-outs or closed outcomes.
- Inventory old artifacts before any deliberate cleanup; preserve the active runtime,
  verified release, needed backups and private acceptance evidence.
