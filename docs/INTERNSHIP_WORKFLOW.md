# Internship workflow and readiness — 17 November 2026

The tool primarily supports internship outreach. New target briefs default to
Internship; existing briefs and explicit alternative levels remain unchanged.
Generation uses the chosen target first, then candidate facts, and otherwise
asks about internships in the supported field without inventing an open role.
Internship interest never establishes student status, graduation date, eligibility,
availability or work authorization. The prompt preserves those distinctions.

1. In Settings, save accurate candidate facts and two or three projects you can
   explain and substantiate. Coursework and personal projects are valid evidence;
   identify your own contribution and do not invent measured results.
2. In Targets, add the actual internship title, official role URL, requirements,
   application status and selected project. Record timing and eligibility only
   when known. Company search now reaches beyond the first 500 companies.
3. Select that role and the relevant contact in Contacts. Create a draft using
   Gemini or Write manually. The manual path works without Gemini credentials.
4. Review one concrete connection between the role and your work, truthful claims,
   an honest subject and one easy next step. Verify sources and the application
   status before approving the exact saved revision. Outreach does not submit an
   employer's application form.
5. Preview the final message and exact recipient batch before sending. Respect
   suppression, quota and send-window checks. Reconcile uncertain delivery before
   considering another attempt. Check replies before a reviewed follow-up.
6. Record responses, positive interest, interviews and offers in Tracking. Use the
   unique-contact funnel to assess actual conversations, rather than send volume.

The personal resume update remains deferred. An intentional No resume selection
is supported; never use the existing placeholder as an attachment. No personal
facts or resume decisions were supplied automatically during this update.

**Current checks and limits**

The prior release passed 325 tests and Windows/Linux CI. This update adds a real
browser regression for selecting and editing a role at company 505, plus the
internship default. JavaScript syntax and whitespace checks pass locally.

On 17 November, Windows Application Control blocks this checkout's `.venv`
Python executable even for `--version`, including outside the sandbox. No policy
was disabled or executable renamed to bypass the restriction. Local startup and
Python tests cannot be certified until an administrator permits a trusted Python
3.12 installation and the environment is recreated using the README's hashed
installation commands. This is a current local-use blocker, independent of source
correctness and remote CI.

R11's actual Gemini output/human review and R16's account-specific controlled
delivery/reply acceptance remain pending. Updated prompt wording is an intended
quality improvement, not measured evidence of improved hiring probability.
See [live acceptance](LIVE_ACCEPTANCE.md) before real outreach.
