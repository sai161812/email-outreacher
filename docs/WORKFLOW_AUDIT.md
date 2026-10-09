# Overall workflow audit - 9 October 2026

Application revision: `b1b1e26f709247076bc71303dab5a4889cfc4bfe`.

The intended local, single-owner workflow passes **223 automated tests**, including **11 Chromium browser tests**. The baseline was 209 passing tests; this review reproduced additional failures and added 14 regression cases. Provider calls use synthetic responses and temporary databases. Live account acceptance remains outstanding.

## Intended workflow and verification

| Stage | Required behavior | Verification |
| --- | --- | --- |
| Startup and data | Initialize fresh databases; back up and migrate supported older schemas; preserve history | Factory/API startup, migration rollback/idempotence, concurrent WAL startup, integrity/FK and consistent backup tests |
| Setup and contacts | Save candidate identity/facts; register assets; add/import valid contacts; reject duplicate active identities | API validation, CSV partial-error reporting, concurrent duplicate guards, full browser setup |
| AI drafting | Use verified facts, relevant company evidence and recipient context; persist reviewable drafts; bound retries/revision costs | Structured-output and installed SDK contracts, quality revision, failure handling, suppression and duplicate-generation tests |
| Review and approval | Display safe text/source evidence; save the latest visible revision; approve exact content and resume | Browser injection fixture, edits during slow saves, revision conflicts, asset snapshots and approval invalidation |
| Delivery | Queue durable work; allow one worker; enforce current approval, send window, quotas and suppression; submit conservatively | Concurrent claims, batch capacity, TLS/setup failures, MIME threading/assets, ambiguous SMTP outcomes and restart recovery |
| Replies and follow-ups | Match exact threads and recipients; suppress permanent bounces; stop follow-ups after closed outcomes | Incremental IMAP UID/report cases, stale outcome protection, due eligibility, browser draft/review/send/reply lifecycle |
| Tracking and recovery | Preserve send totals and recorded outcomes; reconcile uncertain submissions; require review before retry | Cumulative metrics, recorded interview evidence, atomic conflicting reconciliation, failed/canceled retry tests |
| Release | Ship committed source without private artifacts; install locked runtime and start documented commands | Source checks, dependency compatibility/advisories, clean ZIP install, Waitress routes, worker, integrity and backup smoke checks |

## Failures fixed in this review

| Failure | Result after repair | Commit / regression coverage |
| --- | --- | --- |
| A failed profile database write left replacement candidate facts saved in a separate file | Profile and facts save in one SQLite transaction and are included together in database backups | `834ccc1`; `test_api` storage-failure rollback, fallback precedence, backup and partial updates |
| Editing the profile during generation mixed old facts with a new signature | Initial and follow-up drafting capture the profile/facts snapshot before calling the provider | `834ccc1`; `test_composer` profile change inside the provider call |
| Previewing a stale queue reported an already sent message as eligible | Preview rereads current status and skips sent or claimed work | `1bc7e19`; `test_delivery_edges` send followed by stale-queue preview |
| Adding `Re: ` to a valid 197-200 character original subject made follow-up generation fail | Preserve the complete original subject when the prefix would overflow; MIME reply headers retain thread linkage | `1bc7e19`; `test_followups` 196/197/200-character boundaries |
| Navigation silently discarded Settings edits; slow saves treated newer edits as saved | Navigation/sign-out protects unsaved profile/facts, and saving only clears the edits actually submitted | `c0ae2f1`; `test_browser` navigation dismissal and edits during a held save |
| An unusable automatically selected resume blocked drafting with no UI escape | Contacts offers automatic matching, a specific variant, or explicit No resume | `c0ae2f1`; `test_browser` link-only variant in attachment mode followed by a no-resume compose job |
| Direct terminal outcomes inflated interview statistics | Interview counts use recorded interview events or current interview status and survive later rejection/offer outcomes | `b1b1e26`; `test_followups` direct offer/rejection and recorded interview followed by rejection |

## Release evidence

- Local full suite: **223 passed in 40.03 seconds**.
- Tracked-source syntax/private-file/common-credential checks: passed.
- Installed dependency compatibility: no broken requirements.
- Current dependency advisory scan: no known vulnerabilities.
- Package: `dist/email-outreacher-b1b1e26f7092.zip`, built from committed source.
- Fresh temporary runtime: hashed dependencies installed; Waitress read routes, schema v2 initialization/check, worker `--once`, and consistent SQLite backup passed.
- Windows/Linux CI: **223 passed on each platform**, with all source, dependency, packaging and clean-runtime gates successful in [run 37949776032](https://github.com/sai161812/email-outreacher/actions/runs/37949776032). Linux tests took 32.24 seconds; Windows tests 64.19 seconds. Results are recorded in `audit/2026-10-09/workflow_verification.json`.

## Operational notes and remaining acceptance

Settings now stores saved facts in SQLite. An existing `CONTEXT_PATH` file is the fallback only until facts are saved through Settings. That file is preserved; later file edits do not override saved database facts. Continue to back up PDFs and credentials separately. Restoring a database restores its saved candidate facts as well as the profile.

Interview counts require recorded evidence. Historical terminal outcomes without interview events do not establish an interview and are not automatically backfilled. Rates remain per sent message, including follow-ups.

Neither Gemini nor Gmail credentials are configured in this checkout. Live generation/model/search behavior, SMTP delivery, IMAP permissions and first real reply recognition need account validation. Recruiter response improvement and inbox placement are not established by these checks. Use [PRODUCT_READINESS.md](PRODUCT_READINESS.md) for startup and the first intended live workflow.

Private user records were not changed by this audit. The earlier protected legacy snapshot contained three duplicate-contact groups that still require owner review before routine outreach. Unrelated local `fix.py` and `rewrite.py` were not executed, modified or committed. The visual redesign remains a separate task. Public deployment, OAuth, multi-user support, campaign scheduling and contact discovery are outside this local workflow acceptance.

These checks establish the listed behavior under the tested conditions; they cannot prove that every possible defect or external-provider failure is eliminated.
