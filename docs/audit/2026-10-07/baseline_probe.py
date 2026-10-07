"""Reproduce audit findings without using real mail, AI, or the user's database.

Run from the repository root: venv/Scripts/python.exe docs/audit/2026-10-07/baseline_probe.py
These are baseline observations, not a replacement for regression tests.
"""
import ast
import hashlib
import importlib.metadata
import io
import json
import logging
import socket
import sqlite3
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# Fail closed if a probe accidentally attempts real networking.
def no_network(*args, **kwargs):
    raise AssertionError("Network access is forbidden in audit probes")

socket.socket.connect = no_network
socket.create_connection = no_network

import config
import db
import contacts
import composer
import qc
import replies
import resume
import reviewer
import sender
import suppression
import tracker
from repository import CompanyRepository, ContactRepository, EmailRepository, ResumeRepository
from app import app

logging.disable(logging.CRITICAL)
results = []

def observe(name, function):
    try:
        result = function()
        results.append({"probe": name, "result": result})
    except Exception as exc:
        results.append({"probe": name, "exception": type(exc).__name__, "message": str(exc)})

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

original_db = config.DB_PATH
before_db = digest(original_db)

with tempfile.TemporaryDirectory(prefix="outreach-audit-") as temporary:
    config.DB_PATH = Path(temporary) / "isolated.db"
    app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)
    client = app.test_client()
    observe("fresh_flask_import_stats", lambda: {"status": client.get('/api/stats').status_code})
    db.init_db()
    db.init_db()
    observe("schema_init_twice", lambda: "completed")
    cid = CompanyRepository.create("Audit Company", "example.test", None, "Python", None)
    other_cid = CompanyRepository.create("Other Company", "other.test", None, None, None)
    ctid = ContactRepository.create(cid, "person@example.test", "Person", None, None)
    def email(status="pending_review", resume_id=None, parent=None, sent_at=None):
        eid = EmailRepository.create(cid, ctid, resume_id, "A hook", "A subject", "A body", None, parent)
        EmailRepository.update_status(eid, status, set_sent_at=bool(sent_at), sent_at_time=sent_at)
        return eid

    eid = email()
    reviewer.edit(eid, body="Edited body")
    observe("save_edits_status", lambda: EmailRepository.get_by_id(eid)["status"])
    eid = email("sent", sent_at=datetime.now(timezone.utc).isoformat())
    reviewer.approve(eid)
    observe("reapprove_sent_status", lambda: EmailRepository.get_by_id(eid)["status"])
    observe("unknown_review_action", lambda: {"status": (r := client.post(f'/api/review/{eid}', json={"action":"typo"})).status_code, "body": r.get_json()})
    observe("missing_review_target", lambda: {"status": (r := client.post('/api/review/99999', json={"action":"approve"})).status_code, "body": r.get_json()})
    eid = email()
    tracker.mark_offer(eid)
    observe("unsent_marked_offer", lambda: {"status": EmailRepository.get_by_id(eid)["status"], "sent_at": EmailRepository.get_by_id(eid)["sent_at"]})
    observe("missing_company_name", lambda: {"status": client.post('/api/companies', json={}).status_code})
    observe("blank_company_name", lambda: {"status": client.post('/api/companies', json={"name":""}).status_code})
    observe("invalid_contact_email", lambda: {"status": client.post('/api/contacts', json={"company_id":cid,"email":"bad"}).status_code})
    observe("null_review_json", lambda: {"status": client.post(f'/api/review/{eid}', json=None, data='null', content_type='application/json').status_code})
    observe("invalid_tracking_action", lambda: {"status": (r := client.post(f'/api/tracking/{eid}/mark', json={"status":"typo"})).status_code, "body":r.get_json()})

    for row in EmailRepository.get_by_contact_id(ctid):
        EmailRepository.update_status(row["id"], "rejected")
    eid = email("sent", sent_at=datetime.now(timezone.utc).isoformat())
    counts_before = (sender.count_sends_today(), sender.count_company_sends_this_week(cid))
    tracker.mark_replied(eid)
    observe("limits_after_reply", lambda: {"before":counts_before, "after":(sender.count_sends_today(),sender.count_company_sends_this_week(cid))})
    observe("suppression_case_variants", lambda: (suppression.add("Person@Example.Test", "audit"), suppression.is_suppressed("person@example.test"))[1])
    observe("whitespace_contact_storage", lambda: {"email": contacts.get_contact(contacts.add_contact(cid,"  spaced@example.test  "))["email"]})
    first = contacts.add_contact(cid, "duplicate@example.test")
    second = contacts.add_contact(cid, "duplicate@example.test")
    observe("duplicate_contacts", lambda: {"first":first,"second":second})
    observe("email_syntax_dot_errors", lambda: {address:contacts.validate.is_valid_syntax(address) for address in ['.person@example.test','person..name@example.test','person.@example.test']})
    csv_path = Path(temporary) / "contacts.csv"
    csv_path.write_text('company_name,contact_email\nImported,new@example.test\n',encoding='utf8')
    contacts.import_csv(csv_path)
    observe("reimport_same_csv", lambda: contacts.import_csv(csv_path))
    csv_path.write_text('',encoding='utf8')
    observe("empty_csv", lambda: contacts.import_csv(csv_path))

    draft = {"hook":"Hook", "subject":"Subject", "body":"Draft pitch", "research_notes":"Source: https://example.test/source"}
    with patch.object(composer, "compose_email", return_value=draft):
        mismatched = composer.compose_and_store(other_cid,ctid,"Audited context")
        observe("mismatched_company_contact", lambda: {"email_company":EmailRepository.get_by_id(mismatched)["company_id"],"contact_company":contacts.get_contact(ctid)["company_id"]})
        observe("research_notes_persisted", lambda: "research_notes" in EmailRepository.get_by_id(mismatched).keys())
        resume_id = ResumeRepository.create("Audit Resume", "python", str(Path(temporary)/"missing.pdf"))
        observe("compose_assigned_resume", lambda: composer.compose_and_store(cid,ctid,"Audited context",resume_id))
    observe("missing_resume_lookup", lambda: hasattr(resume,"get_variant"))
    observe("null_job_text", lambda: resume.pick_best_variant(None))
    observe("qc_empty_content", lambda: {"subject":qc.check_subject(''),"body":qc.check_body('')})
    observe("qc_followup_length", lambda: qc.check_body('Following up on my note. Open to a brief chat this week?'))
    fake_ai = Mock()
    fake_ai.models.generate_content.return_value = SimpleNamespace(parsed=None,text='invalid provider output')
    with patch.object(config,"require_gemini_key"), patch.object(composer.genai,"Client",return_value=fake_ai):
        broken_draft = composer.compose_and_store(cid,ctid,"Audited context")
        reviewer.approve(broken_draft)
        observe("parse_failure_can_be_approved", lambda: {"status":EmailRepository.get_by_id(broken_draft)["status"],"hook":EmailRepository.get_by_id(broken_draft)["hook"]})
    EmailRepository.update_status(broken_draft,"rejected")
    with patch.object(composer,"compose_email",return_value=draft):
        blank_name_contact = contacts.add_contact(cid,"blank@example.test","   ")
        observe("whitespace_contact_name_composition", lambda: composer.compose_and_store(cid,blank_name_contact,"Audited context"))

    # A suppression consumes the company quota before filtering at send time.
    fake_queue = [{"id":100+i,"company_id":cid,"contact_email":f'person{i}@example.test',"subject":"Subject","body":"Body"} for i in range(3)]
    with patch.object(sender,"get_approved_queue",return_value=fake_queue), patch.object(sender,"count_sends_today",return_value=0), patch.object(EmailRepository,"count_company_sends_since",return_value=0), patch.object(config,"MAX_PER_COMPANY_PER_WEEK",2), patch.object(sender.SuppressionRepository,"is_suppressed",side_effect=lambda address:address=='person0@example.test'):
        observe("suppressed_queue_consumes_company_quota", lambda: sender.run_send_batch(dry_run=True))

    for row in EmailRepository.get_by_contact_id(ctid):
        EmailRepository.update_status(row["id"], "rejected")
    eid = email("approved",resume_id)
    smtp = Mock()
    with patch.object(sender.smtplib,"SMTP",return_value=smtp), patch.object(sender.time,"sleep"):
        observe("send_assigned_resume", lambda: sender.run_send_batch())
    eid = email("approved")
    with patch.object(sender, "is_in_send_window", return_value=False):
        observe("send_window_default", lambda: sender.run_send_batch(dry_run=True))
    observe("atomic_claim_available", lambda: hasattr(EmailRepository,"claim_for_sending"))
    observe("approved_queue_company_name", lambda: "company_name" in sender.get_approved_queue()[0])
    smtp = Mock()
    sender._send_one(smtp, "person@example.test", "Subject", "Body", resume_path=str(Path(temporary)/"missing.pdf"))
    observe("missing_attachment_still_sends", lambda: smtp.sendmail.call_count)
    # SMTP accepts a message; subsequent DB failure triggers the generic retry.
    for row in EmailRepository.get_by_contact_id(ctid):
        EmailRepository.update_status(row["id"], "rejected")
    eid = email("approved")
    smtp = Mock()
    with patch.object(sender.smtplib,"SMTP",return_value=smtp), patch.object(sender.time,"sleep"), patch.object(EmailRepository,"update_sent",side_effect=sqlite3.OperationalError("simulated DB failure")):
        outcome = sender.run_send_batch()
        observe("smtp_success_db_failure_retry", lambda: {"sendmail_calls":smtp.sendmail.call_count,"status":EmailRepository.get_by_id(eid)["status"],"summary":outcome})

    eid = email("approved")
    barrier = Barrier(2, timeout=5)
    smtp = Mock()
    smtp.sendmail.side_effect = lambda *args: barrier.wait()
    with patch.object(sender.smtplib,"SMTP",return_value=smtp), patch.object(sender.time,"sleep"):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(sender.run_send_batch) for _ in range(2)]
            outcomes = [future.result() for future in futures]
        observe("concurrent_batches_duplicate_send", lambda: {"sendmail_calls":smtp.sendmail.call_count,"outcomes":outcomes})

    eid = email("approved")
    smtp = Mock()
    smtp.login.side_effect = RuntimeError("simulated SMTP login failure")
    with patch.object(sender.smtplib,"SMTP",return_value=smtp):
        try:
            sender.run_send_batch()
        except RuntimeError:
            pass
    observe("smtp_cleanup_after_login_failure", lambda: smtp.quit.call_count)
    EmailRepository.update_status(eid,"rejected")

    eid = email("sent",sent_at=datetime.now(timezone.utc).isoformat())
    with patch.object(composer,"compose_follow_up",return_value={"hook":"Hook","subject":"Re: Subject","body":"A follow-up"}):
        child = composer.compose_follow_up_and_store(eid)
        observe("followup_before_due", lambda: {"created":child})
        other_child = composer.compose_follow_up_and_store(eid)
        observe("duplicate_followup_service", lambda: {"created":other_child})
        tracker.mark_replied(eid)
        replied_child = composer.compose_follow_up_and_store(eid)
        observe("followup_after_reply", lambda: {"created":replied_child})
        reviewer.approve(child)
        with patch.object(sender.smtplib,"SMTP",return_value=Mock()), patch.object(sender.time,"sleep"), patch.object(sender,"_send_one",return_value='<audit@example.test>') as delivery:
            sender.run_send_batch()
            observe("queued_followup_after_parent_reply", lambda: delivery.call_count)
    old = (datetime.now(timezone.utc)-timedelta(days=10)).isoformat()
    eid = email("sent",sent_at=old)
    child = email("rejected",parent=eid)
    observe("rejected_followup_blocks_replacement", lambda: eid not in {row['id'] for row in tracker.due_for_follow_up()})
    suppression.add("person@example.test","audit")
    eid = email("sent",sent_at=old)
    observe("suppressed_contact_still_due", lambda: eid in {row['id'] for row in tracker.due_for_follow_up()})
    observe("tracking_includes_unsent", lambda: sorted({row['status'] for row in EmailRepository.get_all_tracked_emails() if row['sent_at'] is None}))

    mailbox = Mock()
    mailbox.search.return_value = ('OK',[b'1'])
    candidate = {"id":999,"message_id":None,"contact_email":"old@example.test"}
    with patch.object(config,"require_gmail_creds"), patch.object(replies.imaplib,"IMAP4_SSL",return_value=mailbox), patch.object(EmailRepository,"get_sent_candidates_for_replies",return_value=[candidate]):
        observe("reply_without_message_id_or_date", lambda: replies.check_replies(dry_run=True))
    mailbox = Mock()
    mailbox.search.side_effect=RuntimeError("simulated search failure")
    with patch.object(config,"require_gmail_creds"), patch.object(replies.imaplib,"IMAP4_SSL",return_value=mailbox), patch.object(EmailRepository,"get_sent_candidates_for_replies",return_value=[candidate]):
        observe("imap_search_failures_reported", lambda: replies.check_replies(dry_run=True))
    mailbox = Mock()
    mailbox.login.side_effect=RuntimeError("simulated login failure")
    with patch.object(config,"require_gmail_creds"), patch.object(replies.imaplib,"IMAP4_SSL",return_value=mailbox):
        try:
            replies.check_replies(dry_run=True)
        except ValueError:
            pass
    observe("imap_cleanup_after_login_failure", lambda: mailbox.logout.call_count)
    with patch.object(sender,"run_send_batch",return_value=[]):
        observe("cross_origin_send_request", lambda: {"status":client.post('/api/send',json={},headers={"Origin":"https://untrusted.example"}).status_code})
    observe("empty_upload_filename_after_sanitizing", lambda: {"status":client.post('/api/contacts/import',data={"file":(io.BytesIO(b'company_name,contact_email\n'),'???')},content_type='multipart/form-data').status_code})
    with db.get_connection() as connection:
        observe("fresh_db_integrity", lambda: connection.execute('PRAGMA integrity_check').fetchone()[0])
        observe("fresh_db_foreign_keys", lambda: [tuple(row) for row in connection.execute('PRAGMA foreign_key_check')])
        observe("fresh_db_indexes", lambda: [tuple(row) for row in connection.execute("SELECT name,tbl_name FROM sqlite_master WHERE type='index'")])

config.DB_PATH = original_db
observe("original_database_unchanged", lambda: before_db == digest(original_db))
observe("stdlib_cprofile_import", lambda: __import__('cProfile').__name__)
observe("python_syntax", lambda: [str(path.relative_to(ROOT)) for path in ROOT.glob('*.py') if ast.parse(path.read_text(encoding='utf-8-sig'))])
observe("installed_dependencies", lambda: {name:importlib.metadata.version(name) for name in ['Flask','pydantic','google-genai','python-dotenv','dnspython','Werkzeug','pytest']})
def inspect_release():
    archive = ROOT / 'release' / 'email_outreacher_clean.zip'
    with zipfile.ZipFile(archive) as release:
        names = release.namelist()
        return {"entries":len(names),"has_tests":any('/tests/' in '/'+name for name in names),"has_env_file":any(Path(name).name=='.env' for name in names),"has_database":any(name.endswith('.db') for name in names)}
observe("ignored_local_release_inventory", inspect_release)
report = {"baseline":"ad87f08667997683a876ad19c112a191f83f96ac","python":sys.version,"network":"blocked by probe","results":results}
destination = Path(__file__).with_name('baseline_results.json')
destination.write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
