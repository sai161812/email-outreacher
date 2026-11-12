# Email Outreacher implementation plan

Prepared 11 November 2026 against `main` at `fe2bec9`.

Milestone 1 is complete under the revised scope, with 231 passing tests; see
[MILESTONE_1.md](MILESTONE_1.md). At the owner's request, personal resume
registration and candidate-facts review are deferred to Milestone 5 / R16,
before controlled live acceptance. They do not block Milestones 2–4.
Milestone 2 / R03–R08 is also complete: see [MILESTONE_2.md](MILESTONE_2.md)
for 258 passing tests, schema 5 migration and exact committed-release verification.
Milestone 3 implementation is recorded in [MILESTONE_3.md](MILESTONE_3.md):
R09/R10 are complete and R11 tooling is verified with 273 tests. At the owner's
request, R11 live-provider/human quality acceptance stays pending in Milestone 3;
it has not been moved to Milestone 5 or counted as passing.
Milestone 4 / R12–R15 is complete: [MILESTONE_4.md](MILESTONE_4.md) records
293 passing tests, schema 7 migration/restore, responsive workflow verification
and exact committed-release acceptance. R11's pending status is unchanged.
Milestone 5 software is implemented: [MILESTONE_5.md](MILESTONE_5.md) is the
current verification record for 303 passing tests, clean release installation,
restore, diagnostics and upkeep. R17's local release/recovery gates pass; R16's
live acceptance remains pending verified owner facts, an actual resume or
deliberate No resume choice, account access and a separately authorized controlled
message/receipt/reply check. Milestone 5 and the overall plan are **not fully
accepted**. R11 remains pending in Milestone 3.
The findings below preserve the pre-implementation review baseline.

**Decision:** keep Flask, SQLite, the single worker, Gmail SMTP/IMAP, Gemini and the current browser UI. The project has a useful foundation. Finish operational setup, close the remaining delivery/recovery gaps, then improve how the candidate demonstrates fit. A rewrite would increase risk without improving the intended workflow.

This is a plan, not a completed implementation. Application files and private records were not modified during this review. No AI requests, mailbox access or email submission were performed. Reliable operation and credible writing are achievable acceptance goals; perfect inbox placement, uninterrupted external services and recruiter responses are not guarantees the application can make.

**Review scope and current evidence**

Reviewed application modules, persistence and migrations, frontend assets, test coverage, configuration and dependency manifests, CI/release scripts, previous audit records, local artifact inventory and Git history. There are 71 tracked files, 36 commits reachable from `main`, and 608 commits across all local refs. History review covered commit metadata across refs and the current implementation and relevant changes; it did not independently execute every historical revision. Local `main` matches the cached `origin/main` ref; no fetch or remote CI revalidation was performed.

| Area | Finding on this checkout | Meaning |
| --- | --- | --- |
| Architecture | Explicit review, approval snapshots, atomic send claims, quotas, uncertain-delivery reconciliation, bounded AI calls, exact reply matching and isolated tests already exist | Preserve these contracts and extend the existing code |
| Historical verification | The October 9 record reports 223 passing cases, including 11 browser cases, on application commit `b1b1e26` | Historical evidence, not a new test result |
| Current Python runtime | `.venv` and `venv` reference an unavailable Python 3.12 installation; the documented pytest command fails before collection. `uv --no-cache python find --system 3.12 --no-python-downloads` finds no interpreter available to this session | Restore a supported local runtime before claiming the project works here |
| Current checks | `node --check static/app.js` and `git diff --check` pass. A limited scan of tracked text found no Google-key, GitHub-token or private-key shapes | These checks do not replace Python tests, dependency auditing or a complete history secret scan |
| Local database | Read-only inspection: schema version 0; integrity check `ok`; zero foreign-key violations; 6 companies, 15 contacts, 1 email, 2 resume variants; 3 duplicate contact groups | Migrate a consistent copy and rehearse recovery before using the actual database |
| Local assets/settings | `.env` and default `candidate_context.txt` are absent; legacy `context.txt` exists. Both registered PDF paths resolve to a 30-byte file | Verify effective environment configuration, import the intended candidate facts explicitly, and replace/validate the resume before real use. Absence of `.env` alone does not prove credentials are absent from the environment |
| Local artifacts | Old release ZIPs, backups, two environments and historical screenshots are present. Untracked `fix.py` and `rewrite.py` predate this review | Keep personal artifacts private. Do not run `rewrite.py`: it checks out, amends and cherry-picks history |
| Git history | `context.txt` exists in earlier history despite being absent from the tracked tip | Review historical exposure before public portfolio publication. Do not rewrite shared history as routine cleanup |

The previous A01–A52 audit remains historical evidence. This plan records current gaps rather than reopening every previously repaired issue. References below identify current files/functions; source findings that require execution are explicitly labeled.

**Delivery order**

| Milestone | Work | Exit condition |
| --- | --- | --- |
| 1. Reproducible local operation | R01–R02 | Supported runtime, verified baseline, migration/restore and asset validation pass using synthetic fixtures; complete |
| 2. Delivery and reply correctness | R03–R08 | Complete: uncertain recovery, fixed batches, sender identity, retained replies, fresh scans and rejection policy verified |
| 3. Useful, truthful outreach | R09–R11 | R09/R10 complete; evaluation tooling implemented; R11 live-output/human acceptance pending |
| 4. Finish everyday workflows | R12–R15 | Complete: recoverable jobs, resume versions/preview, protected forms, audited outcomes and unique-person funnel |
| 5. Release and account acceptance | R16–R17 | Software and local release/recovery checks pass; R16 personal setup and controlled live acceptance remain pending; see the current verification record |

P0 means release-blocking reliability or setup work. P1 means required for the intended complete product. P2 means a useful finishing step after correctness. Keep each change small enough to review and revert; linked schema/service/UI changes belong together.

**Milestone 1 — establish a working baseline**

**R01 · P0 · Repair local startup and rerun verification.** Evidence: the current pytest launch fails with `No Python at ...Python312...`; both environment configurations reference that location. Install or locate supported Python 3.12, recreate one environment from the existing hashed locks, and document the missing prerequisite clearly. Preserve the old environments until replacement works. Add a small diagnostic command to report runtime, resolved data paths, schema, configuration presence and worker status without printing secrets. Distinguish “configured” from “connection verified”; current `/api/settings` readiness only tests whether strings exist.

Acceptance: fresh startup using the README; full pytest suite including Chromium; source checks; `pip check`; current dependency audit; and clean-release smoke test. Record the actual commit, commands and results. Do not copy the October pass count into a new acceptance claim. Upgrade dependencies only for a demonstrated advisory, compatibility issue or required capability.

**R02 · P0 · Finish the actual data and asset setup.** Evidence: the local database is schema 0, while `db.py` expects schema 2; three duplicate groups remain. Rehearse the existing migration against an SQLite-consistent backup, verify row/history preservation, and rehearse restoration to a new database filename. Resolve duplicate contacts by keeping the intended record and archiving redundant records after reviewing history. Import the intended legacy facts into Settings with a visible preview; do not silently choose one facts source over another.

Personal setup scope update: registration of the owner's actual resume and review/save of legacy candidate facts are assigned to R16. R02 provides the preview/import workflow without requiring the owner's input now. In `resume.checked_pdf` and upload handling, replace header-only acceptance with bounded parsing that requires a readable, nonempty PDF with pages; reject unreadable/encrypted files unless deliberately supported. One maintained PDF parser is sufficient; do not build a resume extraction service. Preserve approval-time content hashes. Back up the database and referenced PDF assets together, with a small manifest; document credentials separately and keep them out of source releases.

Acceptance: migration and restore preserve the existing counts/history and saved facts; duplicate resolution preserves submitted mail; malformed/header-only PDF fixtures fail; a real small PDF passes; changed assets still revoke/block delivery. A restored installation can open every selected resume. Add a fixture matching the observed legacy schema, including its extra legacy tables; do not drop unknown tables to make migration pass.

**Milestone 2 — make failure handling conservative and predictable**

**R03 · P0 · Prevent uncertain SMTP outcomes from being downgraded by error handling.** Source-derived risk, not executed here: in `sender.run_send_batch`, an exception from `sendmail` enters the `submission_interrupted` branch. If persisting `delivery.finish(..., "uncertain")` then fails, the outer generic exception handler calls `finish(..., "failed", "transport_setup_failed")`. If that second write succeeds, a possibly submitted message becomes eligible for a later reviewed retry.

Separate transport setup from submission/result persistence. Once submission may have begun, all unknown outcomes remain `submitting`/`uncertain`, including failure to record uncertainty. Preserve the durable attempt for restart recovery. Do not let a broader exception handler reinterpret its phase. Avoid adding another delivery state system.

Acceptance: fault-inject a timeout after possible acceptance plus a one-time database write failure; the result must remain nonretryable until reconciliation. Cover successful SMTP followed by multiple recording failures, worker interruption, and definite rejection separately. Assert SMTP call counts and durable attempt/email states.

**R04 · P1 · Freeze the batch the user intends to send.** Source finding: `app.py` queues only `{dry_run: ...}`; `sender.py:66` reads all approved messages when the worker eventually starts. Later approvals can join an earlier send request, and the UI's paginated queue is not the batch boundary. A preview is also a separate unbound job.

Introduce a small batch payload containing the intended email IDs and approved revisions. Show the exact count/recipients, sender, exclusions and projected capacity before submission. Recheck eligibility at execution and skip changed rows; never add newly approved rows to an existing batch. Reuse current claim/quota rules. Normalize omitted/false `dry_run` consistently. Provide pending cancellation and a cooperative “Stop remaining” action for long batches, checked between messages; accurately report any in-flight message that cannot be recalled.

Acceptance: approving a second draft after queuing a batch does not send it; edits invalidate that batch member; page boundaries cannot hide the scope of a send; duplicate requests reuse the same job; stopping during a delay prevents subsequent submissions. A preview never sends or reserves quota.

**R05 · P1 · Bind approval and mailbox tracking to the sending identity.** Source finding: `repository.snapshot` captures content, recipient and resume but not the sender; `_send_one` takes the current `GMAIL_ADDRESS`. Changing account configuration between approval and execution changes who sends the message without a new approval.

Include the normalized sending account in approval and attempt snapshots; show it in Review and batch confirmation. Changing the account must require review again, with no credentials stored in snapshots. Associate reply tracking with that account and prevent silent reuse of one database's active workflow under a different mailbox. Optionally use the reviewed candidate name as a display name, while retaining the actual authenticated address.

Acceptance: changing accounts after approval blocks send; changing only the password does not invalidate content; previous attempts retain their account identity; an unrelated mailbox cannot advance the old account's reply workflow.

**R06 · P1 · Retain replies seen before uncertain delivery is reconciled.** Source-derived edge case: `EmailRepository.get_sent_candidates_for_replies` excludes rows without `sent_at`; `replies.check_replies` marks scanned UIDs processed and advances its cursor even when no candidate matches. If another sent message makes the scan run, a reply to an uncertain attempt can be consumed before that attempt is confirmed sent, and never reconsidered.

Retain minimal thread evidence for messages referencing unresolved attempts, then reconsider it after reconciliation; alternatively perform a narrowly scoped, explicit Message-ID backfill for that attempt. Do not reset and repeatedly scan the whole mailbox. Keep transport acceptance separate from human-reply evidence and preserve exact sender/thread/date checks.

Acceptance: one confirmed send plus one uncertain send; scan a valid reply to the uncertain attempt; reconcile it as delivered; the reply is applied exactly once and follow-up eligibility closes. Test a bounce through the same sequence and reconciliation as not sent. No address-only matching or automatic resend.

**R07 · P1 · Make reply freshness and backlog visible before follow-ups.** Source finding: scans read only INBOX and process at most 500 new UIDs; they return matches without scanned/remaining counts or a completed-mailbox freshness indicator. Follow-up checks consult recorded outcomes, not unread mailbox state. The single FIFO worker can also leave a reply scan waiting behind a long send batch.

Report scanned/skipped counts, whether more work remains, selected mailbox and last successful catch-up time. Provide “Continue scan” for a backlog. Require a successful current reply check before sending follow-ups; defer follow-ups if that check fails or is incomplete. Recheck the database immediately before submission as today. Explain the unavoidable gap between a mailbox check and a later incoming reply. Keep INBOX as a documented default; offer a single configurable mailbox if the owner uses archiving/filter rules, with independently scoped UID state. No mailbox crawler or parallel worker fleet.

Acceptance: a relevant reply after UID 500 cannot be hidden behind a “no replies” success; IMAP outage defers follow-ups; a recorded reply cancels queued work; the UI explains mailbox coverage. A fresh connection check alone must not count as a complete scan.

**R08 · P1 · Separate recipient failures from provider throttling/policy rejection.** Source finding: every `SMTPRecipientsRefused` response with codes at least 500 becomes a `hard bounce` suppression in `sender.py`; sender/DATA rejection handling continues through the batch. Preserve the distinction between a rejected message and proof that an address is invalid. Store safe SMTP/enhanced status codes; apply permanent automatic address suppression only when the available evidence justifies it, otherwise expose a reviewable rejection. Pause remaining submissions after account-level throttling, authentication or policy failures instead of repeatedly trying other recruiters. Uncertain outcomes retain R03 behavior.

Preserve suppression creation time and record additions/removals/reasons: `SuppressionRepository.add` currently deletes and reinserts the record, while remove erases it. Add a direct “Do not contact” action from contact/tracking views using that same suppression policy.

Acceptance: invalid mailbox, recipient policy rejection, temporary limit, authentication failure and post-DATA disconnect produce distinct actionable outcomes. Policy rejection does not falsely label a recruiter address invalid. Suppression still cancels unsubmitted work and is rechecked at delivery; it never recalls accepted mail.

**Milestone 3 — improve relevance and writing without a large AI system**

**R09 · P1 · Let the owner draft when Gemini is unavailable.** Source finding: the API/UI can edit existing drafts but cannot create a new manual initial draft. Missing credentials, exhausted quota or unavailable model/search therefore block new outreach even when the owner can write the message.

Add “Write manually” for an eligible contact, using the same draft creation, QC, resume selection, duplicate checks and explicit approval. Add explicit regeneration of a pending draft as a new revision; keep the current text until replacement succeeds and warn before replacing manual edits. Permit follow-up resume selection/no-resume before generation so a missing old PDF does not block writing a new message.

Acceptance: with Gemini disabled, manually create, save, review and send through the fake-provider workflow. A failed regeneration preserves prior text; success revokes approval; suppressed/duplicate/early follow-up work remains blocked. Keep the existing bounded generation/revision budget.

**R10 · P1 · Make role fit and evidence first-class inputs.** The existing prompt already asks for a supported proof point, audience-specific request, natural keywords and truthful qualifiers. Repeating those prompt instructions is not the main improvement. Current weaknesses: candidate facts are free text; one job description is stored on the company; source notes are AI-written text; the exact generation inputs/model/prompt version are not retained with a draft.

Add a compact target brief: target role/level, role URL or requisition, application status/date, relevant constraints, selected project proof and genuine relationship context. Do not label an application submitted or a referral real without the owner's input. Give the owner a simple place to record two or three concrete projects with proof links and actual results. Preserve free text as an escape hatch.

Support multiple roles at a company with one small `opportunities` table and an optional draft link; migrate the existing company job fields into a default opportunity while keeping old drafts readable. This removes ambiguity without a general CRM. Keep contact-level suppression and duplicate outreach protection across roles; a second vacancy must not silently authorize emailing the same person again.

Save a local input snapshot plus model/prompt version with generation. Display the chosen proof, role, company source and verification date next to the email. Distinguish user-supplied facts, model claims and externally checked evidence. A changed opportunity during generation should produce a visible stale-context warning. Human verification remains necessary; a JSON schema or source URL is not a fact checker.

Acceptance: two roles at one company use the correct description/resume/proof without overwriting each other; unsupported skills/metrics are rejected by human review; a saved draft remains explainable after settings change; edits to its evidence clear the associated verification acknowledgment. Migrations preserve existing contacts and correspondence.

**R11 · P1 · Evaluate actual drafts before changing more prompts.** Build a small, versioned evaluation set: about 12 scenarios spanning recruiters, managers and unknown titles; strong/sparse evidence; no named vacancy; a real submitted application; unsuitable role; weak company evidence; initial outreach and follow-ups. Include misleading job-text instructions and invented source/metric traps. Use synthetic facts for regression tests, plus a private owner-specific review set once facts are verified.

Human review uses a short rubric: truthful claims, relevant proof, correct audience/purpose, readable natural voice, useful subject and one easy next step. Unsupported claims, invented relationships and wrong-role details are hard failures regardless of prose score. Keep current 80–120 initial / 30–60 follow-up targets as soft defaults; shorter factual mail is acceptable. Retain at most one quality revision rather than adding critic agents or an elaborate scoring service. Inspect whether the final appended resume link/signature makes the actual message unnecessarily long.

Acceptance: every release sample is free of unsupported claims; at least 10 of 12 representative samples need no substantial rewrite under the agreed rubric. This is an internal quality target, not evidence of hiring uplift. Record latency/call count and provider failures alongside ratings. Run paid live evaluations only with configured account access and an explicit bounded execution decision.

For outreach strategy, prioritize actual role fit and appropriate existing relationships; make the recipient's next step easy. This aligns with [Berkeley's networking guidance](https://www.career.berkeley.edu/prepare-for-success/networking/). The application should support the employer's application process and follow-up conversations, with outreach complementing an application where one is required.

**Milestone 4 — remove daily workflow interruptions**

**R12 · P1 · Make jobs and requests recoverable.** Source findings: `static/app.js:21` has no fetch timeout and creates a new idempotency key for every invocation. A lost response leaves the owner unsure whether work was queued; resubmitting after completion can create new work. `jobs.py` heartbeat updates occur between jobs and send items, not during a long generation/provider call. Jobs currently display raw JSON, and the latest-operation ID is lost on reload.

Use one stable key for one user intent and reconcile its result before retrying an ambiguous POST. Add bounded request timeouts and a clear “request outcome unknown; check job” state; do not automatically retry sends with a new key. Recover pending/running jobs from the server on reload. Render item-level result rows with “Open draft,” “Return to review,” “Continue scan” and “Resolve uncertain send.” Keep raw diagnostics in a collapsed detail panel.

Expose active job, stage, last progress and worker health separately, with a heartbeat mechanism that also works during provider calls/delays. Distinguish busy, stopped and suspected stalled states rather than declaring every old heartbeat dead. Log correlation/job/attempt IDs and error categories with secrets and message contents redacted. Do not add a general monitoring stack.

Acceptance: dropped enqueue response, stalled fetch, worker stopped/restarted, long AI call and long send delay all produce actionable UI states; reload recovers job progress; no duplicate send; navigation/buttons recover after request failure.

**R13 · P1 · Finish contact, resume and review management.** Source findings: Contacts loads only the first 100 companies for its company selector; later companies are reachable through a Companies-page workaround but absent from that selector. Resume variants can be registered but cannot be renamed, replaced or archived through supported APIs/UI. Review does not display the complete final message, including sender and appended resume link, in one place.

Use a searchable company selector with pagination and preserve the current selection. Add resume edit/archive/replacement using immutable replacement files; revoke affected approvals without breaking submitted history, and stop automatic matching from choosing archived/unusable variants. Provide a final recipient-view preview of the actual sender, subject, full text, links and attachment. Show “No resume” as an intentional choice. Warn when automatic matching falls back with no keyword match.

Acceptance: select a company beyond the first page; replace/archive an asset without losing old send evidence; changed asset requires reapproval; preview and MIME construction agree. No resume is an explicit valid option. Do not silently switch to a different resume if the selected file fails.

**R14 · P2 · Polish the existing interface.** Keep the current framework and information architecture. Make the next action obvious: finish setup, add/select target, draft, review, preview/send, check replies. Show concise contextual errors, permanent import-result summaries and progress instead of relying only on six-second toasts. Protect unsaved company/contact/resume forms as well as the already protected draft/profile forms. Put important sources into readable rows rather than raw grounding JSON.

Tracking currently offers every outcome for every sent row, including invalid transitions, and “sent” is absent from the select options; a new row can default to “replied” without an intentional selection. Use a neutral “Choose outcome” entry and only valid actions. Provide a narrow, audited correction workflow for mistaken manual outcomes without changing submission history or silently removing suppressions.

Acceptance: keyboard-only and narrow-screen setup/review/recovery work; errors preserve input and focus; accidental Apply cannot create a reply; unsupported transitions are unavailable; a correction preserves its audit trail. Review actual rendered screens at 375/768/1440 widths using realistic text, not only empty-table screenshots.

**R15 · P2 · Measure hiring progress honestly.** Current metrics explicitly count messages, including follow-ups, and any human reply is a reply; this is useful operationally but can obscure actual conversations. Add a unique-contact/thread funnel alongside the existing message counts: initial contacts, human responses, positive interest/referral, interviews and offers. Record response categories manually, with “unknown” available; do not infer enthusiasm using AI. Use actual interview events, preserving the recent fix in `b1b1e26`.

Acceptance: an initial email plus follow-up to one person is two messages and one contacted person; one answer is one responding conversation; a rejection is not positive interest. Display denominators and sample sizes. Review results by role/proof/approach over time without claiming causal improvements from small samples. Do not add tracking pixels, open-rate optimization or automatic A/B sending.

**Milestone 5 — account acceptance, release and upkeep**

**R16 · P1 · Check provider behavior and realistic delivery.** Current external check: Google's deprecation table lists no announced shutdown date for `gemini-3.1-pro-preview`; its presence in configuration is not by itself a defect. Keep model selection configurable and test the chosen model/account combination. Google documents structured output with built-in tools for Gemini 3, but live account, quota and SDK compatibility still need verification. See [deprecations](https://ai.google.dev/gemini-api/docs/deprecations) and [structured outputs](https://ai.google.dev/gemini-api/docs/structured-output).

Deferred personal setup from Milestone 1: when the owner is ready, register the
actual resume PDF, verify its preview and select it for resume-bearing drafts.
Review the legacy candidate facts and save the accurate current version in
Settings. A deliberate **No resume** selection remains supported. Do not use the
30-byte placeholder or synthetic test facts for live outreach. Verify the chosen
asset or intentional no-resume selection and saved facts before live acceptance.

Add explicit, non-sending connection diagnostics for SMTP/IMAP and a separately invoked bounded draft-generation check. An eventual live-send acceptance step must use an owner-designated test recipient after the exact message is reviewed. Verify receipt, readable attachment, threading, Sent Mail identity and a real reply; record ambiguous outcomes accurately. This planning request does not authorize sending test messages now.

For a custom sending domain, verify the relevant SPF/DKIM/DMARC configuration and inspect received authentication headers; for a personal Gmail address, verify actual received authentication rather than asking the owner to configure Google's DNS. Retain TLS, honest subjects/identity, individual relevance, suppressions and restrained contact frequency. Daily caps/random delays are resource and safety controls, not spam-filter evasion. Gmail distinguishes ordinary sender requirements from its additional bulk-sender requirements; do not indiscriminately impose a bulk-mail subsystem on this personal tool. See [Google's sender guidelines](https://support.google.com/mail/answer/81126?hl=en).

Acceptance: account/model diagnostics give safe actionable errors; controlled messages arrive and their authentication/attachment/thread behavior is inspected; reply scanning works on the actual chosen mailbox. Record results as account-specific observations, not proof that recruiter inboxes will accept future mail. Keep the default one follow-up after seven days, with explicit review and stop on replies, opt-out or a closed outcome.

**R17 · P1 · Produce a reproducible release and recovery guide.** Keep the existing Windows/Linux CI and committed-source packaging. Extend regression coverage for the new failures, rerun current advisory checks and smoke-test the exact new release archive. Update the README/readiness document so it links one current verification record and clearly separates application checks, local setup and live acceptance. Provide a simple local start/stop helper with logs, port-conflict handling, duplicate-worker protection and actionable interpreter errors; avoid an installer/service manager until needed. Stopping during possible SMTP acceptance must retain uncertain recovery semantics.

Inventory stale ZIPs/environments/backups and identify the current release; remove artifacts only as a separate deliberate cleanup after preserving needed records. Check all publishable refs for private context/credentials before using the repository as a portfolio. Preserve history by default; confirm any actual secret exposure privately and remediate it specifically. Keep a short maintenance checklist: periodic backup/restore rehearsal, dependency advisories, provider deprecation notices and controlled compatibility checks after changes.

Acceptance: fresh installation from the exact source archive, browser workflow with fake providers, worker recovery, migration and restored asset checks pass. Release includes no database, credentials, private candidate facts, resumes or history-rewrite scripts. No “complete” label while a P0 issue or unacknowledged live-acceptance gap remains.

**Implementation discipline and scope limits**

Reproduce each suspected defect on a temporary database first, add a regression at the affected API/service/browser boundary, apply the smallest fix, then run targeted and adjacent tests. Run full gates at milestones and the final release. Never use the live outreach database as a test fixture. New schema changes need versioned, transactional migrations and a tested restore path; preserve old approval snapshots conservatively when their schema changes.

Keep existing plain-text email, manual approval and one worker. Defer React migration, Redis/Celery, microservices, multi-user hosting, autonomous outreach, scraping/contact enrichment, purchased lists, vector databases, multi-agent drafting, automatic model failover and resume rewriting. OAuth becomes a scoped requirement only if the intended account cannot use the existing authentication method. Add tools and dependencies only where a demonstrated acceptance gap requires them.

**Definition of done**

The owner can start the app reliably, recover a backup, choose an actual role and truthful proof, create a draft with or without AI, inspect the final email and resume, approve that revision, send only the intended batch, understand every failure, reconcile uncertain delivery without duplicates, record replies and stop unwanted follow-ups. The current full automated gates pass; the exact release installs cleanly; controlled live acceptance is documented separately. Hiring progress is assessed through relevant conversations and interviews, not the number of emails sent.
