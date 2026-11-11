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

Targeted service/API/browser cases cover manual-to-approved fake SMTP delivery,
failed/stale regeneration, suppression/duplicate blocks, no-resume follow-ups,
two roles at one company, source snapshots, acknowledgment invalidation,
role-aware resume matching, migration backfill, browser project/target/manual
review, reference output labeling and scorer hard failures. Final suite/release
and migration evidence follows the implementation commits. Providers are fake
in regression checks; no real email or paid model request is used for testing.
