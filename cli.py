#!/usr/bin/env python3
"""
Outreach — internship cold-email tool.

Typical workflow:
    python cli.py init
    python cli.py add-resume --name backend --keywords "backend,api,sql" --file resumes/backend.pdf
    python cli.py add-company --name "Acme Corp" --domain acme.com --job-url https://...
    python cli.py add-contact --company 1 --email jane@acme.com --name "Jane Doe" --title "Eng Manager"
    python cli.py compose --company 1 --contact 1 --context path/to/context.txt
    python cli.py review
    python cli.py approve --email 3
    python cli.py send                 (add --dry-run to preview without sending)
    python cli.py status
    python cli.py follow-ups
"""
import argparse
from pathlib import Path

import db
import contacts
import resume
import composer
import reviewer
import sender
import tracker
import profile


def cmd_set_profile(args):
    profile.set_profile(args.name, args.email, args.phone, args.linkedin_url, args.github_url, args.portfolio_url)
    print("Profile updated.")


def cmd_show_profile(args):
    p = profile.get_profile()
    if not p:
        print("No profile set yet.")
        return
    for k, v in p.items():
        if k != "id" and v:
            print(f"{k}: {v}")

def cmd_init(args):
    db.init_db()
    print(f"Database ready at {db.config.DB_PATH}")


def cmd_add_resume(args):
    rid = resume.add_resume_variant(args.name, args.keywords, args.file, args.url)
    print(f"Added resume variant #{rid}: {args.name}")


def cmd_add_company(args):
    job_text = None
    if args.job_text_file:
        job_text = Path(args.job_text_file).read_text()
    cid = contacts.add_company(args.name, args.domain, args.job_url, job_text, args.notes)
    print(f"Added company #{cid}: {args.name}")


def cmd_add_contact(args):
    cid = contacts.add_contact(args.company, args.email, args.name, args.title, args.source)
    print(f"Added contact #{cid}: {args.email}")


def cmd_list_companies(args):
    for c in contacts.list_companies():
        print(f"[{c['id']}] {c['name']} ({c['domain'] or 'no domain'}) — {c['contact_count']} contact(s)")


def cmd_list_contacts(args):
    for c in contacts.list_contacts(args.company):
        label = c.get("company_name", "")
        print(f"[{c['id']}] {c['email']} — {c.get('name') or 'no name'} {label}")


def cmd_compose(args):
    if not args.force:
        existing_emails = contacts.get_emails_for_contact(args.contact)
        for e in existing_emails:
            if e["status"] != "rejected" and not e.get("follow_up_to_email_id"):
                print(f"Contact #{args.contact} already has a pending/sent email (#{e['id']}, status: {e['status']}) — use --force to draft another.")
                return

    candidate_context = Path(args.context).read_text() if args.context else ""
    company = contacts.get_company(args.company)
    variant = resume.pick_best_variant(company.get("job_text") or "")
    variant_id = variant["id"] if variant else None

    eid = composer.compose_and_store(args.company, args.contact, candidate_context, variant_id)
    print(f"Drafted email #{eid} — run 'review' to check it before sending.")


def cmd_import_csv(args):
    try:
        summary = contacts.import_csv(args.file)
    except FileNotFoundError:
        print(f"Import failed: no file found at '{args.file}'")
        return
    except ValueError as e:
        print(f"Import failed: {e}")
        return
    print(f"Companies created: {summary['companies_created']}")
    print(f"Contacts created: {summary['contacts_created']}")
    if summary["errors"]:
        print(f"Skipped {len(summary['errors'])} row(s):")
        for row_num, reason in summary["errors"]:
            print(f"  row {row_num}: {reason}")


def cmd_follow_up(args):
    try:
        eid = composer.compose_follow_up_and_store(args.email)
    except ValueError as e:
        print(f"Could not draft follow-up: {e}")
        return
    print(f"Drafted follow-up email #{eid} (for original #{args.email}) — run 'review' to check it.")


def cmd_review(args):
    pending = reviewer.list_pending()
    if not pending:
        print("Nothing pending review.")
        return
    for e in pending:
        print("=" * 60)
        if e.get("qc_warnings"):
            print(f"⚠ QC WARNING: {e['qc_warnings']}")
        print(f"[{e['id']}] {e['company_name']} -> {e['contact_email']}")
        print(f"Hook: {e['hook']}")
        print(f"Subject: {e['subject']}")
        print(f"\n{e['body']}\n")


def cmd_approve(args):
    reviewer.approve(args.email)
    print(f"Approved #{args.email}")


def cmd_reject(args):
    reviewer.reject(args.email)
    print(f"Rejected #{args.email}")


def cmd_edit(args):
    reviewer.edit(args.email, subject=args.subject, body=args.body_file and Path(args.body_file).read_text())
    print(f"Updated #{args.email}")


def cmd_send(args):
    sender.run_send_batch(dry_run=args.dry_run, force=args.force)


def cmd_status(args):
    summary = tracker.pipeline_summary()
    for status, n in summary.items():
        print(f"{status}: {n}")


def cmd_mark(args):
    if args.result == "replied":
        tracker.mark_replied(args.email)
    elif args.result == "ghosted":
        tracker.mark_ghosted(args.email)
    elif args.result == "bounced":
        tracker.mark_bounced(args.email)
    print(f"Marked #{args.email} as {args.result}")


def cmd_follow_ups(args):
    due = tracker.due_for_follow_up()
    if not due:
        print("Nothing due for follow-up.")
        return
    for e in due:
        print(f"[{e['id']}] {e['company_name']} — {e['contact_email']} (sent {e['sent_at']})")


def build_parser():
    p = argparse.ArgumentParser(description="Internship outreach tool")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)

    a = sub.add_parser("set-profile")
    a.add_argument("--name", required=True)
    a.add_argument("--email")
    a.add_argument("--phone")
    a.add_argument("--linkedin-url")
    a.add_argument("--github-url")
    a.add_argument("--portfolio-url")
    a.set_defaults(func=cmd_set_profile)

    sub.add_parser("show-profile").set_defaults(func=cmd_show_profile)

    a = sub.add_parser("add-resume")
    a.add_argument("--name", required=True)
    a.add_argument("--keywords", required=True, help="comma separated")
    a.add_argument("--file", required=True)
    a.add_argument("--url", help="optional public link to view resume online")
    a.set_defaults(func=cmd_add_resume)

    a = sub.add_parser("add-company")
    a.add_argument("--name", required=True)
    a.add_argument("--domain")
    a.add_argument("--job-url")
    a.add_argument("--job-text-file", help="path to a text file with the job posting")
    a.add_argument("--notes")
    a.set_defaults(func=cmd_add_company)

    a = sub.add_parser("add-contact")
    a.add_argument("--company", type=int, required=True)
    a.add_argument("--email", required=True)
    a.add_argument("--name")
    a.add_argument("--title")
    a.add_argument("--source")
    a.set_defaults(func=cmd_add_contact)

    a = sub.add_parser("import-csv")
    a.add_argument("--file", required=True, help="path to CSV file (see companies_template.csv)")
    a.set_defaults(func=cmd_import_csv)

    sub.add_parser("list-companies").set_defaults(func=cmd_list_companies)

    a = sub.add_parser("list-contacts")
    a.add_argument("--company", type=int)
    a.set_defaults(func=cmd_list_contacts)

    a = sub.add_parser("compose")
    a.add_argument("--company", type=int, required=True)
    a.add_argument("--contact", type=int, required=True)
    a.add_argument("--context", help="path to a text file describing your relevant background")
    a.add_argument("--force", action="store_true", help="force composing even if an email already exists")
    a.set_defaults(func=cmd_compose)

    sub.add_parser("review").set_defaults(func=cmd_review)

    a = sub.add_parser("approve")
    a.add_argument("--email", type=int, required=True)
    a.set_defaults(func=cmd_approve)

    a = sub.add_parser("reject")
    a.add_argument("--email", type=int, required=True)
    a.set_defaults(func=cmd_reject)

    a = sub.add_parser("edit")
    a.add_argument("--email", type=int, required=True)
    a.add_argument("--subject")
    a.add_argument("--body-file")
    a.set_defaults(func=cmd_edit)

    a = sub.add_parser("send")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--force", action="store_true", help="force sending outside the send-time window")
    a.set_defaults(func=cmd_send)

    sub.add_parser("status").set_defaults(func=cmd_status)

    a = sub.add_parser("mark")
    a.add_argument("--email", type=int, required=True)
    a.add_argument("--result", choices=["replied", "ghosted", "bounced"], required=True)
    a.set_defaults(func=cmd_mark)

    sub.add_parser("follow-ups").set_defaults(func=cmd_follow_ups)

    a = sub.add_parser("follow-up")
    a.add_argument("--email", type=int, required=True, help="ID of the original SENT email to follow up on")
    a.set_defaults(func=cmd_follow_up)

    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)