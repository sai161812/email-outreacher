# Account-specific live acceptance

R16's software is available; live acceptance is **pending**. This checkout has
no configured Gmail/Gemini credentials, no saved verified candidate facts and no
valid active resume asset. The two registered assets remain unusable placeholders.
The owner has not designated a test recipient or reviewed/authorized a test message.
No test email or paid generation request was made to fill these gaps.

**Prepare the real inputs**

Stop the server/worker before changing configuration. Follow the README's locked
installation and run `manage.py diagnose` and `manage.py check`. Configure the
original account for this database; another account needs a separate database.
In Settings, preview legacy facts, review them and save accurate current facts.
Register and open the actual resume, or deliberately choose **No resume**. The
synthetic evaluation fixtures and 30-byte PDF are not personal outreach content.

The selected model remains configurable. Google's [deprecation table](https://ai.google.dev/gemini-api/docs/deprecations)
listed no announced shutdown for `gemini-3.1-pro-preview` when checked on
12 November 2026. That does not establish account access, quota or future availability.
Check the notice again before changing models or after a provider failure.

**Run explicit diagnostics**

~~~powershell
.\.venv\Scripts\python.exe manage.py check-accounts
~~~

Alternatively use Settings → **Check mail connections (no sending)** and inspect
the durable result in Jobs. SMTP uses TLS/login/NOOP; IMAP logs in and selects the
configured mailbox read-only. There is no sendmail, STORE, DELETE or EXPUNGE call.
The checks do not advance reply cursors, count a reply scan as complete or certify
receipt. Results retain only safe status categories and the configuration scope.
They are observations at the displayed time; repeat after credential changes.

Gmail app passwords depend on account settings and administrator policy; Google's
[app-password guidance](https://support.google.com/accounts/answer/185833?hl=en)
describes the 2-Step Verification prerequisite and common restrictions. If this
account cannot use the existing authentication method, record that actual blocker
before scoping OAuth work. Do not substitute the normal account password.

The separately invoked model check may incur **up to three generation calls plus
search charges** under the existing bounded budget:

~~~powershell
.\.venv\Scripts\python.exe manage.py check-model
~~~

It uses synthetic facts, tests the selected model/search/structured-output
combination, prints the resulting draft and diagnostics, and never saves a draft,
approves it or sends mail. Missing credentials return not_configured with zero
calls. A successful request is not a human quality rating. R11's separate live
12-case/human rubric acceptance stays pending in Milestone 3.

**Perform the controlled send only when the owner is ready**

Copy [the acceptance template](live_acceptance_template.json) into protected local
storage such as `backups/live-acceptance-<new-date>.json`. Record account-specific
observations; do not commit real addresses, headers or correspondence.

1. The owner designates a recipient mailbox they control or have permission to
   use for this test. Choose the actual resume or explicitly No resume.
2. Create one truthful draft. Inspect sender, recipient, subject, full content,
   links and attachment with **Preview final email**. Save, verify evidence where
   applicable, and approve that exact revision.
3. Inspect batch confirmation so only the designated message is included. The
   owner explicitly authorizes the real test send. Use the existing approved-batch
   path; there is no diagnostic bypass around approval, quotas or send windows.
4. Record the durable Message-ID/attempt result. Confirm the same ID and sending
   identity in Sent Mail and actual receipt in the recipient mailbox. If ambiguous,
   reconcile that exact attempt; do not automatically resend.
5. At the receiving mailbox inspect receiver-added Authentication-Results, From
   alignment, Message-ID/thread headers, final text/links and the actual PDF's
   readability. A supplied or forged authentication header is not independent proof.
6. Send a real human reply from the designated recipient. Run **Check replies**
   through the configured mailbox until caught up. Verify exact-thread matching
   and cancellation of pending follow-ups. Account login alone cannot pass this step.

For a custom sending domain, check the relevant SPF/DKIM/DMARC setup and received
alignment. A personal Gmail user does not administer Google's sending-domain DNS;
inspect its actual received authentication results instead. Google's [sender
guidelines](https://support.google.com/mail/answer/81126?hl=en) distinguish ordinary
requirements from additional bulk-sender requirements. This personal tool does
not need an indiscriminate bulk-mail subsystem. Honest identity/content, TLS,
relevance, suppression and restrained frequency remain the operating policy.

Keep one reviewed follow-up after seven days by default; stop on a reply, opt-out
or closed outcome. Caps and random delays are safeguards, not spam-filter evasion.
Document receipt and authentication as observations for this account/message;
neither passing tests nor one received email proves future recruiter inbox placement.

Do not mark R16 fully accepted until the real-input, receipt, asset, identity,
authentication, threading and human-reply observations have been recorded. If
something remains unverified, retain an explicit pending/failed state and reason.
