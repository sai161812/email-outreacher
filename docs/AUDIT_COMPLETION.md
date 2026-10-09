# Repair verification ledger

Original audit application revision: `24b929a` (7 October 2026), **150 passed**. The subsequent product acceptance pass on `63dd14f` passed **167 tests** locally, adding slow-save/reconciliation, delivery-report and end-to-end follow-up checks. See [product readiness](PRODUCT_READINESS.md) and `audit/2026-10-07/verification_product.json` for current scope and release gates. This is verification of the listed repairs under the stated tests, not proof that all possible bugs are absent.

The 9 October recruiter-drafting update on `6052781` passed **208 tests** locally and on Windows/Linux CI. Its follow-up-subject refinement on `bed935e` passed **209 tests** locally and on both CI platforms, with bounded quality revision, recipient-aware writing and improved content checks. See [the drafting policy](DRAFTING_QUALITY.md) for scope, source guidance and live-evaluation limits; current cross-platform results are recorded in `IMPLEMENTATION_PROGRESS.md` and `audit/2026-10-09/drafting_verification.json`.

`Verified` below means the implemented application behavior passed the named isolated checks. Provider transports are fake. Existing private data requiring an owner decision is listed separately and is not silently changed.

The subsequent overall workflow review on `b1b1e26` passed **223 tests** locally and on Windows/Linux CI, including all source, dependency and isolated-release gates in [run 37949776032](https://github.com/sai161812/email-outreacher/actions/runs/37949776032). It repaired seven additional settings, drafting, preview, follow-up, browser and tracking-metric defects in four commits. See [WORKFLOW_AUDIT.md](WORKFLOW_AUDIT.md) and `audit/2026-10-09/workflow_verification.json` for the current evidence and remaining live-account acceptance. The original issue ledger below retains its historical results.

| Issue | State | Implemented behavior | Evidence | Commits |
| --- | --- | --- | --- | --- |
| A01 | Verified | Regression suite collects and exercises real service contracts | pytest: 150 passed | f0b3959 |
| A02 | Verified | One application factory initializes every supported launch path | test_api fresh routes; clean-runtime Waitress smoke | a8846e2 |
| A03 | Verified | Typed configuration, model override, absolute paths, timezone/timeouts | test_config; local/DST delivery tests | f0b3959, b8441b8 |
| A04 | Verified | Transactional schema v2, backups, guards, root backfill and serialized WAL initialization | test_migrations; actual protected-snapshot upgrade preserves history | f0b3959, b8441b8, 24b929a |
| A05 | Verified | Canonical duplicate guards and reviewed legacy reporting | test_contacts concurrency/reimport; three legacy duplicate groups retained for review | 5bf23a4, 135ac3a |
| A06 | Verified | Company/contact/parent relationships checked before persistence | test_migrations relationship guard; API compose checks | f0b3959, b8441b8 |
| A07 | Verified | Canonical mailbox and suppression identity | test_contacts canonical dedup; test_sender suppression | f0b3959, 5bf23a4 |
| A08 | Verified | Supported syntax and optional cached DNS warnings | test_contacts invalid addresses; test_dns error/null-MX/cache; API warning | 5bf23a4, b8441b8 |
| A09 | Verified | Validated, repeatable CSV with accurate partial reports | test_contacts malformed/header/reimport; test_api encoding; sample import | 5bf23a4, ebc63c8 |
| A10 | Verified | Bounded streamed imports and uniquely named PDFs | test_api uploads/encoding; test_resumes size/type; no shared temp file | a8846e2 |
| A11 | Verified | Save remains pending and revokes approval | test_sender edit requires approval; browser save/approve workflow | f0b3959 |
| A12 | Verified | Explicit lifecycle and required sent history for outcomes | test_sender outcomes/reapproval; API unsent offer/reply rejection | f0b3959, b8441b8 |
| A13 | Verified | Revision-aware exact approval snapshot | test_sender stale review/changed attachment; browser dirty approval | f0b3959 |
| A14 | Verified | Atomic claims/quota reservations plus worker lock | test_sender barrier concurrent batches and claim/cap contention; test_jobs | f0b3959, a8846e2 |
| A15 | Verified | Durable stable attempt IDs and explicit uncertain recovery | test_sender SMTP/DB failures/recovery; test_jobs restart | f0b3959, b8441b8 |
| A16 | Verified | Immutable sent counts and conservative reservations | test_delivery_edges local midnight/DST/legacy dates; sender quota tests | f0b3959, b8441b8 |
| A17 | Verified | Window enforcement at claim preparation and each candidate | test_sender outside window; test_delivery_edges window closes mid-batch | f0b3959, b8441b8 |
| A18 | Verified | Timeout/preflight/cleanup and classified SMTP outcomes | test_sender auth/unknown submission/MIME headers; test_delivery_edges TLS/cleanup failures | f0b3959, b8441b8 |
| A19 | Verified | Suppression precedes allocation; every candidate receives a result | test_delivery_edges suppressed capacity and transport-failure accounting | b8441b8 |
| A20 | Verified | Resume lookup and validation before generation | test_composer assigned resume; test_resumes unknown ID | f0b3959, 5bf23a4 |
| A21 | Verified | Dictionary boundaries and selected resume lookup | test_sender MIME attachment; test_resumes link delivery | f0b3959 |
| A22 | Verified | Checked PDF/HTTPS, approval hash and explicit no-resume review | test_resumes invalid/missing/oversize/outside/link; sender changed PDF/MIME | f0b3959, ebc63c8 |
| A23 | Verified | Deterministic null-safe matching and browser registration/override | test_resumes matching tie/null; browser uploads/selects resume | 5bf23a4, a8846e2 |
| A24 | Verified | Approved company name supplies safe attachment basename | test_sender personalized MIME filename | f0b3959 |
| A25 | Verified | Validated provider output, bounded retry and no error drafts | test_composer invalid output, real SDK 503/401 objects, cleanup | 5bf23a4, b8441b8 |
| A26 | Verified | Persisted research/grounding and safe review display | test_composer source round-trip/SDK metadata; browser literal strings | 5bf23a4, a8846e2 |
| A27 | Verified | Verified candidate context and no invented follow-up achievements | test_composer prompt/context/provider preflight; explicit review remains required | 5bf23a4 |
| A28 | Verified | Hard blockers versus draft-specific pitch advisories | test_sender empty approval; composer placeholders; browser save refreshes QC | f0b3959, 5bf23a4 |
| A29 | Verified | Profile/context onboarding, ignored personal facts, safe greeting | test_composer missing profile; browser setup; tracked-source exclusion check | 5bf23a4, a8846e2 |
| A30 | Verified | Generation reservation plus persistence guard | test_composer concurrent generation; test_migrations direct duplicate draft | 5bf23a4, b8441b8 |
| A31 | Verified | Shared due/closed/suppressed policy at each boundary | test_followups early/replied/canceled and reply-after-generation persistence | 5bf23a4, b8441b8 |
| A32 | Verified | Root-thread identity, replacement and maximum spacing/count | test_followups replacement/limit and large closed-history pagination | 5bf23a4, 135ac3a |
| A33 | Verified | Exact thread/date/sender matching; auto/DSN classification | test_replies old/unrelated/substrings/auto/valid exact reply | 5bf23a4 |
| A34 | Verified | Late reply/thread updates preserve advanced outcomes | test_replies ghosted incremental reply; test_followups cancellation/cumulative outcomes | 5bf23a4 |
| A35 | Verified | Read-only incremental IMAP, checked errors and UID reset | test_replies login/select/search/fetch failure, cleanup, dedupe/reset | 5bf23a4, b8441b8 |
| A36 | Verified | Actual-sent tracking and cumulative per-message metrics | test_followups funnel; test_sender quota through outcomes; local weekday logic | 5bf23a4 |
| A37 | Verified | Safe DOM values/text and compatible CSP | browser quoted subject and closing-textarea payload with no script execution | a8846e2 |
| A38 | Verified | Loopback defaults, Host/Origin/CSRF, owner login and HTTPS gate | test_api hostile requests/login/remote HTTP rejection | a8846e2, b8441b8 |
| A39 | Verified | Shared payload/ID validation and safe JSON errors | test_api null bodies across mutations, bad fields/actions/IDs, conflicts | a8846e2, ebc63c8 |
| A40 | Verified | Durable worker jobs with idempotency/progress/recovery | test_jobs concurrency/restart/mode conflict; API quick enqueue; browser workflow | a8846e2, b8441b8 |
| A41 | Verified | Single-owner setup/management, assets, suppression, queue and retry | full browser setup→draft→review→send→outcome; duplicate review UI | a8846e2, 135ac3a |
| A42 | Verified | Actual job counts/reasons and remaining capacity | browser asserts result sent count=1; delivery summaries cover failed/deferred/skipped | a8846e2, 135ac3a |
| A43 | Verified | Dirty review blocks approval until saving the latest revision | browser edit/save/approve; API stale revision conflict | a8846e2 |
| A44 | Verified | Handled requests, view ordering, dirty protection and setup race fix | browser no page errors; intentionally delayed profile-save input preservation | a8846e2, 135ac3a |
| A45 | Verified | Semantic controls, focus-managed dialogs and responsive layout | browser keyboard Enter/Escape/focus return; 375/768/1440px screenshots inspected | a8846e2 |
| A46 | Verified | Indexed joins/direct lookups, bounded API/UI pages | test_operations 1,001 contacts: one joined SELECT, correct offset, company index | ebc63c8, 135ac3a |
| A47 | Verified | Candidate module renamed; shared persistence and transition boundaries | test_config stdlib cProfile import; transactional management/delivery regressions | f0b3959, ebc63c8 |
| A48 | Verified | Durable review/send/reply history, job IDs and redacted errors | test_jobs secret failure hidden; sender attempts/recovery and reply event dedupe | f0b3959, a8846e2 |
| A49 | Verified | Exact hashed locks and upgraded isolated dependencies | pip check passes; dependency_final.json: no known vulnerabilities | f0b3959, ebc63c8 |
| A50 | Verified | Private artifacts ignored; tests tracked; committed-source releases | scripts/check_source.py passes; release path policy; clean ZIP runtime install | f0b3959, ebc63c8 |
| A51 | Verified | Verified PowerShell/POSIX instructions, Gmail guidance and valid sample | test_operations sample import; clean locked-runtime Waitress/worker/backup smoke | ebc63c8 |
| A52 | Verified | Pinned Windows/Linux CI, browser/security/package/release gates | Windows/Linux full gates passed on 24b929a: 150 tests, audits and clean runtime | ebc63c8, 24b929a |

## Acceptance gates

- Full Windows local suite on application revision 24b929a: 150 passed; browser checks include deliberate slow setup-save responses.
- Source syntax/private-file/credential-format check passed. This checks common token formats and prohibited paths; it is not an exhaustive secrets audit.
- Locked installed environment: pip check passed; current advisory scan reported no known vulnerabilities. Findings can change with new advisories.
- Committed release ebc63c8 installed into a new temporary virtual environment using the hashed runtime lock. Waitress served fresh read routes; schema initialization/check, worker --once and SQLite backup passed. The final 24b929a release also passed locally, and Windows/Linux CI passed all 150 tests, source/dependency checks and clean-runtime release verification: [run 37657473857](https://github.com/sai161812/email-outreacher/actions/runs/37657473857).
- Actual legacy database: inspected and migrated only through protected SQLite snapshots. Integrity and FK checks passed; email IDs/content/send timestamps were preserved; original database content hash remained unchanged. Three duplicate-contact groups need owner review. Settings exposes their records; archiving preserves history and cancels unsubmitted drafts.
- GitHub's initial Linux run passed 145 tests and caught a setup-save race in the browser scenario. The patch and deterministic delayed-response regression are in 135ac3a, whose Windows and Linux pipelines passed. Initial Windows CI also exposed a per-request WAL setup race; 24b929a serializes journal-mode initialization and adds concurrent startup/read regressions. See IMPLEMENTATION_PROGRESS.md for the final rerun result.

## Remaining integration and operational checks

1. Live Gemini account/model/search-grounding and Gmail SMTP/IMAP behavior have not been exercised. No real email, mailbox access or paid AI request was used. Local tests validate installed SDK contracts, classified errors and provider boundaries.
2. Public HTTPS reverse-proxy deployment and assistive-technology testing beyond browser semantics/keyboard checks remain unverified. Local access is the supported acceptance target for this repair.
3. Review the three existing duplicate-contact groups before routine outreach. No production contact records were merged, deleted or archived automatically.
4. The original database has not been migrated in place. Back it up, stop both processes during the code upgrade, initialize/check with manage.py, then review migration findings before use.
5. A historical personal context file was removed from the current tracked tree, but old commits may still contain it. Git history was preserved; unrelated local fix.py and rewrite.py were never executed or committed.
6. SMTP ambiguity still requires manual Message-ID reconciliation. Caps, delays and successful submission do not prove inbox placement.

Further product development remains optional: Gmail OAuth, automated scheduling, richer campaign management, contact discovery and multi-user access. These are outside the single-owner repair scope.
