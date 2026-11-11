# Milestone 3 — useful, truthful outreach

Scope: R09–R11 only. R09 and R10 software implementation is complete. R11 tooling
is implemented; **live-provider and human quality acceptance remains pending in
Milestone 3**, as explicitly requested by the owner. This milestone is therefore
not marked fully accepted. Actual personal resume setup remains in Milestone 5.

**R09**

Contacts supports manual pitches without a Gemini key, using the existing
recipient/company, suppression, duplicate, QC, resume, revision and approval
safeguards. Greeting/signature assembly is shared with AI drafts. Regeneration
queues durable work, warns before replacement, uses the existing bounded AI call
budget, preserves old text on failure and rejects replacement after concurrent
edits. Successful replacement creates a new pending revision and clears approval.
Follow-ups can choose a replacement/no resume before generation so a missing
original file does not block a deliberately resume-free follow-up.

**R10**

Schema 6 adds one opportunities table and optional draft links, immutable saved
input snapshots and per-revision evidence acknowledgments. Existing company job
fields backfill a default opportunity without rewriting old drafts. Multiple
roles retain separate descriptions and project choices; automatic resume matching
uses the selected role. Contact-level duplicate protection remains across roles.

Targets provides role/level, URL/requisition, application status/date, constraints,
relationship context, selected project, company source and owner-reported source
verification date. Up to three projects retain concrete actions, actual results
and optional proof URLs. Free-text facts remain available. A target's seniority
never establishes the candidate's credentials. Application submission/referral
claims require owner-supplied context rather than being inferred from job text.

Review distinguishes saved owner inputs from model research notes, displays
selected proof/source/date and preserves model/prompt/call/latency metadata.
Changed role briefs during initial generation produce visible warnings. Edits
to text, role/project evidence or saved candidate facts clear acknowledgment;
relevant approvals return to review. Human acknowledgment is an owner assertion,
not independent verification or a factual classifier.

**R11**

The versioned synthetic 12-case reference pack covers all planned audiences,
evidence limitations, application/relationship contexts and follow-up cases,
including hostile job instructions, fabricated metrics and source traps.
`scripts/evaluate_drafts.py` exports references without network access or explicitly
runs bounded live generation. Reports include final wrappers/simulated resume
link, word counts, suggestions, failures, calls and latency. The ratings template
and scorer require explicit per-case human judgments. Reference output cannot
pass the live quality gate. See [DRAFT_EVALUATION.md](DRAFT_EVALUATION.md).

The required live gate remains: 12 actual generated outputs, no unsupported claims
or wrong-role/relationship implications, and at least 10 needing no substantial
rewrite under explicit human rubric ratings. Gemini is unconfigured, so no live
generation was attempted and no human ratings were invented. Owner-specific
evaluation also requires verified private facts. These remain acceptance work
within R11, not silently deferred or treated as passing.

**Verification**

Final application source: `beaf2bf6178eb9a755924d7fdf54988a57c443f3`.
Implementation commits were pushed individually: `0eb0a87` (R09), `ad34be9`
(R10), `78e8dd3` (R11 tooling), and `beaf2bf` (project-choice timing repair).

Targeted service/API/browser cases cover manual-to-approved fake SMTP delivery,
failed/stale regeneration, suppression/duplicate blocks, no-resume follow-ups,
two roles at one company, source snapshots, acknowledgment invalidation,
role-aware resume matching, migration backfill, browser project/target/manual
review, reference output labeling and scorer hard failures. The browser suite
reproduced a stale project-choice race after saving a project; loading current
choices before opening role briefs and retaining the modal until refresh fixed it.

- Full suite: **273 passed**, including **12 browser cases**, in 58.88 seconds.
- Source syntax/private-file checks, JavaScript syntax, whitespace and `pip check`: passed.
- Current dependency advisory scan: no known vulnerabilities found.
- Exact committed source ZIP `dist/email-outreacher-beaf2bf6178e.zip`: passed
  clean hashed installation, Waitress read routes, schema 6 initialization and
  integrity, worker startup and SQLite-consistent backup smoke checks.
- Actual schema 5 data was rehearsed through migration and bundle restore under
  ignored `backups/milestone3-09659eb8`: all 6 companies, 15 contacts, 1 email and
  2 resume registrations remained, with exact submitted content/status/timestamps.
  The live database then migrated after automatic backup. Integrity is `ok`,
  foreign-key violations are zero and migration reports are empty.
- `scripts/evaluate_drafts.py --output test-results/milestone3-reference-evaluation.json`
  exported 12 curated reference cases without provider calls. None has a known
  forbidden-claim trap hit or deterministic blocker. This establishes neither
  live factual accuracy nor human quality acceptance; human ratings remain pending.

Providers are fake in regression checks; no real email or paid model request was
used for testing. R11's live 12-case / 10-acceptable-sample gate is **not claimed
passed**. Later milestones were not implemented.
