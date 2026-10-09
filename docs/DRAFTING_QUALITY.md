# Recruiter outreach drafting

The generator now aims to make a candidate's relevance easy to assess: a clear purpose,
one supported example of work, and one simple next-step question. It adapts to the target
role in candidate facts instead of assuming every sender is a student seeking an internship.

The approach follows the emphasis on clear purpose, personalization, concise writing and
proofreading in [Yale SOM's recruiter-email guidance](https://cdo.som.yale.edu/blog/2025/08/26/10-email-templates-for-every-situation-youll-face-with-a-recruiter/),
professional tone and avoiding demanding follow-ups in [MIT's recruiting guidelines](https://capd.mit.edu/recruiting-guidelines-for-students/),
and using one's own content while checking AI accuracy in [Berkeley's AI guidance](https://www.career.berkeley.edu/prepare-for-success/utilizing-generative-ai/).
The word ranges below are product defaults chosen for readability, not proven acceptance thresholds.
Recruiter response or selection still depends on fit, evidence, timing and the employer's process.

## Writing policy

| Aspect | Behavior |
| --- | --- |
| Initial length | Target 80-120 pitch words, usually 4-6 sentences in 2-3 short paragraphs; greeting/signature excluded |
| Follow-up length | Target 30-60 words in 1-2 paragraphs; shorter is acceptable when there is no useful new detail |
| Opening | State the purpose and relevant role/company connection; avoid a biography, generic praise or filler |
| Evidence | Choose one relevant project/achievement: action, demonstrated skill and an actual result or concrete feature |
| Truthfulness | Preserve personal-project/coursework/team qualifiers; never invent metrics, seniority, availability, referrals or prior contact |
| Keywords | Use up to 3 natural role terms supported by both candidate facts and job/company context; no minimum, skill inflation or ATS claims |
| Personalization | Prefer relevant official company/product/careers information; do not assume a listing remains open |
| Tone | Professional, warm, direct and confident at the candidate's actual level; avoid hype, excessive formality and desperation |
| Request | One easy-to-answer question; recruiter application/fit questions differ from manager/team relevance questions |
| Subject | Initial subject: descriptive target/area and useful context, at most 8 words and 65 characters; no fake Re:/Fwd: or clickbait. Follow-ups preserve the original subject rather than shortening it |
| Formatting | Plain-text paragraphs; the app owns the greeting and compact signature with at most two distinct profile links |
| Resume references | The AI must not claim a resume is attached or linked because the delivery asset can change during review |
| Review evidence | Notes should identify company sources/uncertainties, the supporting candidate fact, shared keywords and missing context |

Unknown recipient titles get neutral application-route/contact wording. Recipient title routing is
a writing hint, not proof that the person owns a vacancy. An unknown target role is not invented.
If research is inconclusive, the AI must disclose that in review notes and use only supported context.

## Quality pass and review

The generator checks output for missing content/placeholders, length, generic or inflated wording,
large paragraphs, long sentences, comma-heavy lists, multiple questions, missing requests,
markup, all caps, misleading subjects and pressure in follow-ups. A draft with issues receives
**at most one AI revision**, carrying the original facts and feedback into that request.
Research grounding from successful responses is retained for inspection.

A clean result uses one generation call. The shared limit is **three generation calls**:
the initial request, at most one revision and at most one transient-error retry. SDK HTTP retries
are disabled so they do not multiply that budget. Each request still has the configured provider
timeout; generation reservations cover the maximum call budget. Provider-side searches may incur
additional charges according to the model/account's billing.

If hard blockers remain, no draft is stored. If a valid revised draft still has writing suggestions,
it stays **pending review** with visible warnings. Short factual messages are preferable to padded
ones. These checks do not establish factual accuracy, grammar quality or recruiter approval;
the AI's source notes and candidate claims still require human review. Nothing is approved or sent
automatically, and existing saved drafts are not rewritten. Saving a manual edit recomputes the
writing suggestions using the current text.

## Give the AI useful facts

In **Settings**, save the target role/level, accurate background and the strongest relevant project
with concrete actions and outcomes. A list such as "Python, SQL, React" gives the generator less
credible evidence than "My personal Python dashboard validates CSV imports, queries SQLite and
produces weekly summaries." Add only measured results, current constraints and genuine proof URLs.
The revised `candidate_context.example.txt` explains what to supply without inventing a biography.
The generator does not extract facts from the uploaded resume PDF; candidate facts are its source
for candidate claims. Job descriptions are evidence of employer needs, not candidate skills.

For a follow-up, explicitly date a real new achievement if it happened after the original message.
Otherwise the generator should provide a brief reminder and retain one relevant proof point.

## Illustrative email

This is a fictional example, not a draft generated for the owner's actual background. Its source
facts are an entry-level backend target and a personal Python/SQLite dashboard with CSV validation
and weekly summaries. The fictional posting asks for Python, SQL and internal data tools.

**Subject: Backend engineering opportunities at Example**

~~~text
Hi Priya,

I'm exploring entry-level backend engineering opportunities at Example. The posting's
focus on Python and internal data tools connects with a personal dashboard project
I've built.

The dashboard validates CSV imports, queries SQLite, and produces weekly usage
summaries. Building it gave me practical experience with input validation and clear
error handling. I'd be interested in applying that foundation to the data workflows
described in the role and learning from the team maintaining them.

Could you advise on the appropriate application route for the backend role?

Best,
Maya
~~~

The exact wording should vary with the supplied evidence and recipient. Prefer a specific match
to a real role over generic enthusiasm, and a concrete feature over an invented percentage.

## Validation

Isolated tests exercise good/weak writing examples, source-preserving revisions, sparse evidence,
malformed output, persistent blockers, follow-up pressure, recipient-title routing, timeout/retry
budgets and persisted pending-review warnings. The existing browser and delivery suites exercise
the complete review/send workflow. These use fake providers and cannot measure real AI output or
recruiter response rates. No Gemini key was configured during this change; live qualitative
evaluation remains pending account configuration.

Application source **bed935e** passed **209 tests** locally and on Windows/Linux, plus source,
dependency, package and isolated runtime gates in [CI run 37945988485](https://github.com/sai161812/email-outreacher/actions/runs/37945988485).
Evidence is recorded in `audit/2026-10-09/drafting_verification.json`.
