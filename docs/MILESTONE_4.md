# Milestone 4 — everyday workflow completion

Status: **Complete**, R12–R15 only. Verified application source:
`ea80456b8235186618f21b6168e3303e36ab104a` on 12 November 2026.

R11 live-provider/human quality acceptance remains pending in Milestone 3.
The owner's resume and live account acceptance remain in Milestone 5. No later
milestone was implemented, no paid model request was made and no live mail sent.

| Item | Final behavior | Evidence |
| --- | --- | --- |
| R12 | Queued user intents retain request keys through unknown responses; key lookup recovers pending or completed jobs without a new POST. Requests time out after 20 seconds. Reload restores active operations. Jobs displays worker health/stage/last progress, item results and recovery actions; diagnostics are collapsed. A separate two-second heartbeat continues during provider calls and delays. | Lost-response/reload browser regression; request timeout/Retry browser regression; heartbeat during a blocked provider; request-key lookup tests |
| R13 | Company search pages preserve the selection, including companies outside the initial page. Resume edits/replacements create new versions and preserve previous files/IDs for submitted history. Archiving requires an explicit new selection. Automatic matching excludes unusable assets and warns on zero keyword matches; an all-unusable registry requires explicit No resume or replacement. Final preview and SMTP use the same MIME builder. | Company #106 browser workflow; immutable replacement/archive tests; preview/MIME parity for link and attachment modes; explicit no-resume fallback test |
| R14 | Forms protect edits on Cancel/Escape/navigation/unload; session expiry refreshes CSRF and restores unsaved fields after sign-in. CSV import results persist across reload; failures retain selected files. Sources are readable and raw grounding is collapsed. Dashboard provides a next action. Tracking starts at Choose outcome and only lists valid transitions. Narrow, audited correction reverses the latest recorded manual operation while preserving submission history and suppressions. | Populated review/tracking/dialog workflows at 375/768/1440 pixels; owner session-expiry recovery; no-op Apply; correction audit/concurrency guards |
| R15 | A distinct recipient/conversation funnel accompanies the existing message counts. Categories are explicitly owner-recorded, with unknown available; positive interest/referral is never inferred from prose. Known responses close pending follow-ups. Role/proof/approach/month cohorts show sample sizes with explicit denominator and interpretation. Interview counts exclude corrected mistaken evidence while retaining real events. | Two messages/one person; rejection is not positive interest; terminal outcomes do not invent replies/interviews; explicit categories stop follow-ups; corrected interview event excluded |

**Operational details**

Request recovery stores only a request fingerprint and key in the browser; message
bodies and credentials are not saved there. An unknown queued operation is looked
up before retrying. A missing lookup does not authorize an automatic retry with a
new key. The owner can check unresolved requests in Jobs or retry the same action
with the retained key. Non-job mutations report unknown outcomes and preserve
their input; inspect current records before repeating them. Closing a browser
after deliberately discarding its unsaved edits is not an autosave/recovery service.

Worker health distinguishes recent busy/idle work from a stopped worker or a
suspected stall when an old heartbeat still has a held worker lock. Last progress
is separate from heartbeat activity. Logs record job/attempt identifiers and
error categories without provider error text, credentials or message bodies.

Resume versions are created transactionally, including PDF plus metadata when
replacing a file. Old submitted rows retain their version; affected unsent drafts
return to review. In-flight/uncertain assets cannot be changed until resolved.
An archived selection is shown as unavailable rather than silently switching to
No resume. The preview includes sender, recipient, subject, final plain text,
appended resume URL and attachment filename. It performs no SMTP submission or
quota claim; Message-ID/Date are generated separately at actual sending time.

Corrections require an explicit reason and exact latest manual event ID. Automatic
and legacy outcomes without recorded manual provenance cannot be rewritten using
this action. A manual thread-wide reply is corrected as one operation, with guards
against newer outcomes. Correction appends evidence of what was reversed; it does
not delete historical events, restart canceled work, change sent_at, remove a
suppression or silently change a response category. Correct a mistaken category
separately. Unknown means the response type is unspecified, not that no reply
ever occurred.

The unique funnel counts normalized recipient addresses, with separate initial-
contact, sent-message and conversation counts. Recorded human replies or explicit
owner categories establish responses; terminal outcomes alone do not. Only explicit
positive_interest/referral categories establish positive interest. Cohorts use the
saved initial draft inputs and local send month; they describe samples rather than
proving causal effects of a project, approach, date or writing style. The existing
per-message statistics retain their documented denominator.

**Verification**

- Full suite: **293 passed**, including **19 Chromium browser cases**, in
  **106.47 seconds**.
- Tracked source/private-file checks, JavaScript syntax, whitespace checks and
  `pip check`: passed.
- Current installed dependency audit: no known vulnerabilities found.
- Exact committed release `dist/email-outreacher-ea80456b8235.zip`: passed fresh
  hashed dependency installation, Waitress read routes, schema 7 initialization/
  integrity, worker startup and consistent SQLite backup smoke checks.
- Schema 6 data was rehearsed through migration and bundle restore under ignored
  `backups/milestone4-29590fd4`. Counts and submitted content/status/timestamps/
  saved inputs were preserved: 6 companies, 15 contacts, 1 email, 2 resume versions
  and 2 existing opportunities. The live database was then backed up and migrated;
  integrity is `ok`, foreign-key violations are zero and migration reports empty.
- Nine populated screenshots are retained in ignored `test-results`:
  `milestone4-{review,tracking,dialog}-{375,768,1440}.png`. Responsive assertions
  passed; representative phone/tablet/desktop renders were visually inspected.

Implementation was committed and pushed in `a21b507` (R12), `6039314` (R13),
and `ea80456` (R14/R15 and integration safeguards). The final documentation commit
does not alter tested application code. Tests use temporary databases and synthetic
providers; these results do not establish account permissions or inbox placement.
