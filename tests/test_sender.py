import json
import smtplib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock
import pytest
import config
import delivery
import reviewer
import sender
from db import get_connection
from errors import Conflict
from repository import EmailRepository, ContactRepository, SuppressionRepository

@pytest.fixture
def draft(contact):
    company,person=contact
    return EmailRepository.create(company,person,None,"Hook","Subject","A reviewed pitch",None)

@pytest.fixture
def mail(monkeypatch):
    smtp=Mock()
    monkeypatch.setattr(config,"GMAIL_ADDRESS","owner@example.test")
    monkeypatch.setattr(config,"GMAIL_APP_PASSWORD","test-secret")
    monkeypatch.setattr(sender.smtplib,"SMTP",Mock(return_value=smtp))
    monkeypatch.setattr(sender,"is_in_send_window",lambda *a:True)
    monkeypatch.setattr(sender.time,"sleep",lambda *a:None)
    return smtp

def test_edit_requires_explicit_approval(draft):
    reviewer.edit(draft,body="New body",expected_revision=1)
    row=EmailRepository.get_by_id(draft)
    assert row["status"]=="pending_review"
    assert row["revision"]==2
    assert row["approval_json"] is None

def test_stale_review_rejected(draft):
    reviewer.edit(draft,body="Changed")
    with pytest.raises(Conflict):
        reviewer.approve(draft,1)
    reviewer.approve(draft,2)
    reviewer.edit(draft,body="Another change",expected_revision=2)
    assert EmailRepository.get_by_id(draft)["status"]=="pending_review"

def test_empty_draft_cannot_be_approved(draft):
    reviewer.edit(draft,body="")
    with pytest.raises(ValueError,match="Body"):
        reviewer.approve(draft)

def test_atomic_claim_prevents_duplicate_send(draft):
    reviewer.approve(draft)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:delivery.claim(draft),range(2)))
    assert sum(bool(r) for r in results)==1
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM send_attempts").fetchone()[0]==1

def test_concurrent_batches_submit_once(draft,mail,monkeypatch):
    reviewer.approve(draft)
    queue=sender.get_approved_queue()
    barrier=Barrier(2,timeout=5)
    def get_queue():
        barrier.wait()
        return queue
    monkeypatch.setattr(sender,"get_approved_queue",get_queue)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:sender.run_send_batch(),range(2)))
    assert mail.sendmail.call_count==1
    assert sum(r["status"]=="sent" for batch in results for r in batch)==1

def test_success_then_db_failure_does_not_resend(draft,mail,monkeypatch):
    reviewer.approve(draft)
    monkeypatch.setattr(EmailRepository,"update_sent",Mock(side_effect=RuntimeError("DB failure")))
    result=sender.run_send_batch()
    assert mail.sendmail.call_count==1
    assert result[0]["status"]=="uncertain"
    assert EmailRepository.get_by_id(draft)["status"]=="uncertain"
    assert sender.run_send_batch()==[]

def test_unknown_smtp_result_never_retries(draft,mail):
    reviewer.approve(draft)
    mail.sendmail.side_effect=TimeoutError("uncertain")
    assert sender.run_send_batch()[0]["status"]=="uncertain"
    assert mail.sendmail.call_count==1

def test_login_failure_closes_connection(draft,mail):
    reviewer.approve(draft)
    mail.login.side_effect=smtplib.SMTPAuthenticationError(535,b"invalid")
    assert sender.run_send_batch()[0]["status"]=="failed"
    mail.quit.assert_called_once()
    assert mail.sendmail.call_count==0

def test_outcomes_do_not_free_quota(draft,mail,monkeypatch):
    reviewer.approve(draft)
    sender.run_send_batch()
    before=(sender.count_sends_today(),sender.count_company_sends_this_week(EmailRepository.get_by_id(draft)["company_id"]))
    EmailRepository.update_status(draft,"replied")
    assert before==(sender.count_sends_today(),sender.count_company_sends_this_week(EmailRepository.get_by_id(draft)["company_id"]))
    with pytest.raises(Conflict):
        reviewer.approve(draft)

def test_reservations_enforce_company_cap(contact,draft,monkeypatch):
    reviewer.approve(draft)
    company,_=contact
    person=ContactRepository.create(company,"second@example.test")
    other=EmailRepository.create(company,person,None,"Hook","Subject","Body",None)
    reviewer.approve(other)
    monkeypatch.setattr(config,"MAX_PER_COMPANY_PER_WEEK",1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(delivery.claim,eid) for eid in (draft,other)]
        results=[]
        for future in futures:
            try: results.append(future.result())
            except Conflict: results.append(None)
    assert sum(bool(r) for r in results)==1

def test_window_enforced(draft,mail,monkeypatch):
    reviewer.approve(draft)
    monkeypatch.setattr(sender,"is_in_send_window",lambda *a:False)
    assert sender.run_send_batch()[0]["status"]=="deferred"
    assert mail.sendmail.call_count==0

def test_suppression_cancels_approved(draft):
    reviewer.approve(draft)
    SuppressionRepository.add(" PERSON@EXAMPLE.TEST ","manual")
    assert EmailRepository.get_by_id(draft)["status"]=="canceled"
    assert SuppressionRepository.is_suppressed("Person@Example.Test")

def test_recovery_never_resubmits(draft):
    reviewer.approve(draft)
    claim=delivery.claim(draft)
    with get_connection() as conn:
        conn.execute("UPDATE send_attempts SET state='submitting' WHERE id=?",(claim["attempt_id"],))
    delivery.recover()
    assert EmailRepository.get_by_id(draft)["status"]=="uncertain"
    delivery.reconcile(claim["attempt_id"],True)
    assert EmailRepository.get_by_id(draft)["status"]=="sent"

def test_message_headers_and_attachment(contact,mail,tmp_path,monkeypatch):
    import resume
    pdf=config.RESUME_DIR/"cv.pdf"
    pdf.write_bytes(b"%PDF-1.4\nsynthetic test")
    rid=resume.add_resume_variant("CV","python",str(pdf))
    company,person=contact
    eid=EmailRepository.create(company,person,rid,"Hook","Subject","Body",None)
    reviewer.approve(eid)
    sender.run_send_batch()
    from email import message_from_bytes
    message=message_from_bytes(mail.sendmail.call_args.args[2])
    assert message["Date"] and message["Message-ID"]
    assert any(p.get_filename()=="Resume_Example.pdf" for p in message.walk())

def test_changed_attachment_blocks_submission(contact,mail):
    import resume
    pdf=config.RESUME_DIR/"cv.pdf"
    pdf.write_bytes(b"%PDF-1.4\noriginal")
    rid=resume.add_resume_variant("CV","python",str(pdf))
    company,person=contact
    eid=EmailRepository.create(company,person,rid,"Hook","Subject","Body",None)
    reviewer.approve(eid)
    pdf.write_bytes(b"%PDF-1.4\nchanged")
    assert sender.run_send_batch()[0]["status"]=="deferred"
    assert mail.sendmail.call_count==0
