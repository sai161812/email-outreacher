# Milestone 2 — delivery and reply correctness

Scope: R03–R08 of `RELIABILITY_AND_HIRING_PLAN.md`. Milestone 1 personal
resume/facts setup remains deferred to Milestone 5. Milestones 3–5 are outside
this implementation.

| Item | Implemented behavior | Regression evidence |
| --- | --- | --- |
| R03 | A failure to store an unknown SMTP result retains a durable submitting/uncertain attempt. Broader exception handlers cannot downgrade it to a retryable failure. | `test_transport_recovery.py`; fault injection reproduced two failures before repair; transport suite then passed 30 cases |
| R04 | Send jobs freeze approved IDs/revisions/account when queued. Confirmation covers all pages, shows recipient/subject/revision, projected eligibility and exclusion reasons. Changed rows are skipped. Pending jobs can be canceled; running batches stop between messages and during delays. | `test_fixed_batches.py`; updated browser initial/follow-up confirmation workflows |
| R05 | Approvals include the configured sending account; attempts retain it. A database binds to its account on first send claim or mailbox scan. Different accounts are rejected; password changes remain allowed. | `test_sender_identity.py`; 51 adjacent identity/transport/migration/reply tests passed |
| R06 | Minimal exact-thread evidence for unresolved submissions is retained as the UID cursor advances. Reconciliation replays outcomes once; failed reconciliation does not create a sent/replied outcome. Later scans recover pending replay. | `test_reply_reconciliation.py`; human reply, delivery report and not-sent reconciliation cases |
| R07 | Reply jobs report scanned/skipped/remaining counts, mailbox, completeness and last complete check. Follow-ups require a fresh complete scan immediately before claiming. Oversized reports remain blocking until acknowledged after manual inspection. Configurable mailbox names have separate UID progress. | `test_reply_freshness.py`; 501-message backlog, IMAP outage, mailbox selection and skipped-report review |
| R08 | SMTP/enhanced codes distinguish invalid mailbox, temporary limit, authentication, policy and other rejection. Only an explicit permanent `5.1.1` invalid-mailbox response automatically suppresses an address. Other failures pause the batch for review. Suppression timestamps and addition/removal reasons are preserved; contact/tracking screens expose Do not contact. | `test_smtp_policy.py`; 55 adjacent recovery/transport/reply cases and 36 policy/freshness cases passed |

SMTP policy follows the distinction between address and security/policy status
in [RFC 3463](https://www.rfc-editor.org/rfc/rfc3463.html), with SMTP reply handling
specified by [RFC 5321](https://www.rfc-editor.org/rfc/rfc5321.html). Policy delivery
reports can close a failed thread without declaring its recipient address invalid.
No provider text, message body or credential is retained in rejection diagnostics.

Schema 5 adds attempt sender identity, pending reply evidence and suppression
history. Existing submitted history is preserved. Old approvals lacking sender
identity return to review; legacy send jobs lacking fixed membership fail safely
and require a newly reviewed batch. Pre-identity attempts retain an empty sender
as unknown history; this upgrade does not invent an original account. For an
unbound legacy database, configure its original account before its first send
claim/scan. Use a separate database for another account.

Cancellation cannot recall a message already being submitted. Rows not yet claimed
remain approved; a claimed row canceled before submission needs fresh review.
An incoming reply can race a completed mailbox check, so no scan provides an
absolute guarantee against a reply arriving just before submission. Only the
configured mailbox is covered; filters that move replies require choosing that
mailbox deliberately. Acknowledging a skipped report is an owner assertion after
manual inspection, not automatic validation of that report.

The actual schema 2 database was backed up and rehearsed through migration and
bundle restore in ignored `backups/milestone2-e9164b90`. All 6 companies, 15 contacts,
1 submitted email and 2 resume registrations were preserved, along with exact
submitted content/status/timestamp. Integrity and foreign-key checks passed.

Implementation commits already pushed: `a6bdd20` (R03), `634764a` (R05),
`57ee6d6` (fixed batches and retained evidence). Final verification and remaining
commit identifiers are recorded after the final gates. All automated providers
are synthetic; no live message or paid AI request is used for acceptance.
