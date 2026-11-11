# Draft evaluation v1

R11 implementation is available; its live-output/human-review acceptance remains
pending **within Milestone 3**, at the owner's request. A clean linter or curated
reference output does not satisfy that acceptance gate.

The versioned [12-case set](../tests/fixtures/drafting_evaluation_v1.json) covers
recruiters, managers, unknown titles, sparse facts, no named vacancy, an explicitly
submitted application, a seniority mismatch, weak research, hostile job-text
instructions, an unanswered follow-up, a dated update and a genuine relationship
that is not a referral. All identities, facts and URLs are synthetic. Its reference
pitches are curated examples, not Gemini responses or owner-rated examples.

Export the references without network calls, credentials or database changes:

~~~powershell
.\.venv\Scripts\python.exe scripts/evaluate_drafts.py --output test-results\reference-review.json
~~~

For each output, the report includes its supplied facts/company context, final
greeting/pitch/signature and simulated resume link, pitch/final word counts,
deterministic suggestions, known forbidden-claim traps, call count and latency.
Reference calls are explicitly zero. These exports let a reviewer inspect how
wrappers/links affect the actual reading length. Short factual pitches remain
acceptable; the 80–120 / 30–60 word ranges are soft targets.

After configuring Gemini and deliberately deciding to incur bounded API charges:

~~~powershell
.\.venv\Scripts\python.exe scripts/evaluate_drafts.py --live --max-cases 12 --output test-results\live-review.json
~~~

This command can make up to **36 generation calls**, with additional provider
search charges where applicable. It uses the existing one-revision/one-transient-
retry budget, not extra critic calls. It never sends mail. Use `--max-cases 1` for
a small account check; a one-case check cannot pass the 12-case release gate.
Each provider failure records its exception category, duration and available call
count without persisting private provider error text. Missing credentials fail
before the run. Output filenames must be new, preserving prior results.

Copy [the ratings template](drafting_ratings_template.json) to a private location
under `test-results`, set the reviewer identity, and replace every null rating
with true or false after inspecting the actual exported output. Record supporting
notes; do not prefill positive ratings from passing code tests.

| Criterion | Reviewer question |
| --- | --- |
| truthful | Is every candidate/company/application/relationship claim supported, including qualifiers and metrics? |
| relevant_proof | Does one concrete project fact explain the fit without a skills inventory? |
| correct_audience | Are role, seniority, recipient authority and purpose accurate? |
| natural_voice | Is it clear, professional and readable without padding, hype or pressure? |
| useful_subject | Is the subject honest, specific and appropriate to the thread? |
| single_next_step | Is there one low-effort, appropriate request? |
| needs_substantial_rewrite | Would it require a material rewrite before the owner could consider sending it? |

Unsupported claims, invented referrals/applications and wrong-role implications
are hard failures regardless of prose quality. Mark truthful/correct_audience false
as applicable, even if an automated trap check missed the problem. Forbidden-term
checks are deliberately limited and do not constitute a factual verifier.

Score a saved run without making further model calls:

~~~powershell
.\.venv\Scripts\python.exe scripts/evaluate_drafts.py --report test-results\live-review.json --ratings test-results\my-ratings.json --output test-results\scored-review.json
~~~

The release gate requires live outputs for all 12 cases, explicit ratings for each,
no hard failures and at least 10 samples with every rubric item passing and no
substantial rewrite required. Scoring curated references can never pass the live
release gate. The reviewer identity is an operator assertion; the script does not
authenticate who performed the review. A pass is an internal quality assessment,
not evidence of inbox placement or improved hiring rates.

An owner-specific evaluation set still requires verified personal facts and is
kept private. The reference set never becomes the owner's profile, resume or live
outreach content. Actual resume setup remains scheduled for Milestone 5.
