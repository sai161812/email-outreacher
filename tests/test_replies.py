from email.message import EmailMessage
from email import message_from_bytes
from email.utils import format_datetime
from datetime import timedelta
from unittest.mock import Mock
import pytest
import config
import replies
from errors import ProviderError
from repository import EmailRepository
from db import get_connection

def message(reference="<sent@test>",sender="person@example.test",old=False,auto=False):
    msg=EmailMessage()
    msg["From"]=sender
    msg["Date"]=format_datetime(config.now()-timedelta(days=20) if old else config.now())
    msg["In-Reply-To"]=reference
    if auto: msg["Auto-Submitted"]="auto-replied"
    return msg

def candidate():
    return {"id":1,"message_id":"<sent@test>","contact_email":"person@example.test","status":"sent","sent_at":(config.now()-timedelta(days=1)).isoformat()}

@pytest.mark.parametrize("kwargs",[{"reference":"<sent@test.extra>"},{"sender":"other@example.test"},{"old":True},{"auto":True}])
def test_false_replies_rejected(kwargs):
    assert replies.matched_candidates(message(**kwargs),[candidate()])==[]

def test_exact_reply_matches():
    assert replies.matched_candidates(message(),[candidate()])[0]["id"]==1

def test_reply_date_uses_email_header_second_precision():
    c=candidate()
    c["sent_at"]=config.now().replace(microsecond=999999).isoformat()
    msg=message()
    assert replies.matched_candidates(msg,[c])==[c]

def test_no_id_has_no_address_fallback():
    c=candidate();c["message_id"]=None
    assert replies.matched_candidates(message(),[c])==[]

def delivery_report(original_type="message/rfc822",recipient="person@example.test",action="failed",status="5.1.1"):
    return message_from_bytes((
        "From: Mail Delivery System <mailer-daemon@example.test>\r\n"
        f"Date: {format_datetime(config.now())}\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/report; report-type=delivery-status; boundary=report\r\n\r\n"
        "--report\r\nContent-Type: text/plain\r\n\r\nDelivery report\r\n"
        "--report\r\nContent-Type: message/delivery-status\r\n\r\n"
        "Reporting-MTA: dns; example.test\r\n\r\n"
        f"Final-Recipient: rfc822; {recipient}\r\nAction: {action}\r\nStatus: {status}\r\n\r\n"
        f"--report\r\nContent-Type: {original_type}\r\n\r\n"
        "Message-ID: <sent@test>\r\nTo: person@example.test\r\nSubject: Original\r\n\r\n"
        "--report--\r\n"
    ).encode())

@pytest.mark.parametrize("original_type",["message/rfc822","text/rfc822-headers"])
def test_bounce_matches_returned_original_headers(original_type):
    report=delivery_report(original_type)
    assert replies.classify(report)=="bounced"
    assert replies.matched_candidates(report,[candidate()])[0]["id"]==1

@pytest.mark.parametrize("kwargs",[{"recipient":"another@example.test"},{"action":"delayed","status":"4.2.0"},{"action":"delivered","status":"2.0.0"}])
def test_delivery_report_must_fail_the_matching_recipient(kwargs):
    report=delivery_report(**kwargs)
    report["References"]="<sent@test>"
    assert replies.matched_candidates(report,[candidate()])==[]

def test_malformed_delivery_status_is_ignored():
    report=delivery_report()
    report.get_payload()[1].set_payload("malformed")
    assert replies.classify(report)=="automatic"

def test_report_prefers_returned_message_over_ancestor_references():
    report=delivery_report()
    report["References"]="<ancestor@test>"
    original=candidate()
    ancestor={**candidate(),"id":2,"message_id":"<ancestor@test>"}
    assert replies.matched_candidates(report,[ancestor,original])==[original]

def test_report_does_not_downgrade_recorded_reply():
    assert replies.matched_candidates(delivery_report(),[{**candidate(),"status":"replied"}])==[]

def test_delivery_report_scan_suppresses_only_failed_recipient(contact,monkeypatch):
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    with get_connection() as conn:
        conn.execute("UPDATE emails SET status='sent',sent_at=?,message_id='<sent@test>' WHERE id=?",((config.now()-timedelta(days=1)).isoformat(),eid))
    mailbox=Mock()
    mailbox.login.return_value=("OK",[])
    mailbox.select.return_value=("OK",[])
    mailbox.response.return_value=("UIDVALIDITY",[b"100"])
    raw=delivery_report().as_bytes()
    def uid(operation,*args):
        if operation=="search": return "OK",[b"1"]
        return "OK",[(f"1 (RFC822.SIZE {len(raw)})".encode(),raw),b")"]
    mailbox.uid.side_effect=uid
    monkeypatch.setattr(config,"GMAIL_ADDRESS","owner@example.test")
    monkeypatch.setattr(config,"GMAIL_APP_PASSWORD","synthetic")
    monkeypatch.setattr(replies.imaplib,"IMAP4_SSL",Mock(return_value=mailbox))
    assert replies.check_replies()[0]["kind"]=="bounced"
    assert EmailRepository.get_by_id(eid)["status"]=="bounced"
    from repository import SuppressionRepository
    assert SuppressionRepository.is_suppressed("person@example.test")
    assert not SuppressionRepository.is_suppressed("mailer-daemon@example.test")

def test_oversized_report_does_not_block_later_replies(contact,monkeypatch):
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    with get_connection() as conn:
        conn.execute("UPDATE emails SET status='sent',sent_at=?,message_id='<sent@test>' WHERE id=?",((config.now()-timedelta(days=1)).isoformat(),eid))
    mailbox=Mock()
    mailbox.login.return_value=("OK",[])
    mailbox.select.return_value=("OK",[])
    mailbox.response.return_value=("UIDVALIDITY",[b"100"])
    def uid(operation,*args):
        if operation=="search": return "OK",[b"1 2"]
        number,query=args
        assert query=="(BODY.PEEK[HEADER] RFC822.SIZE)"  # Never download the oversized report.
        raw=delivery_report().as_bytes() if number=="1" else message().as_bytes()
        size=config.MAX_UPLOAD_BYTES+1 if number=="1" else len(raw)
        return "OK",[(f"{number} (RFC822.SIZE {size})".encode(),raw),b")"]
    mailbox.uid.side_effect=uid
    monkeypatch.setattr(config,"GMAIL_ADDRESS","owner@example.test")
    monkeypatch.setattr(config,"GMAIL_APP_PASSWORD","synthetic")
    monkeypatch.setattr(replies.imaplib,"IMAP4_SSL",Mock(return_value=mailbox))
    result=replies.check_replies()
    assert result[0]["kind"]=="skipped_report"
    assert result[1]["kind"]=="human"
    assert EmailRepository.get_by_id(eid)["status"]=="replied"
    with get_connection() as conn:
        assert conn.execute("SELECT value FROM settings WHERE key LIKE 'imap_cursor:%'").fetchone()[0]=="2"

def test_login_failure_cleans_up(contact,monkeypatch):
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    with get_connection() as conn:
        conn.execute("UPDATE emails SET status='sent',sent_at=? WHERE id=?",(config.now().isoformat(),eid))
    mailbox=Mock()
    mailbox.login.side_effect=RuntimeError("login")
    monkeypatch.setattr(config,"GMAIL_ADDRESS","owner@example.test")
    monkeypatch.setattr(config,"GMAIL_APP_PASSWORD","test")
    monkeypatch.setattr(replies.imaplib,"IMAP4_SSL",Mock(return_value=mailbox))
    with pytest.raises(ProviderError):
        replies.check_replies()
    mailbox.logout.assert_called_once()

def test_incremental_scan_and_uidvalidity_reset(contact,monkeypatch):
    from datetime import timedelta
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    with get_connection() as conn:
        conn.execute("UPDATE emails SET status='ghosted',sent_at=?,message_id='<sent@test>' WHERE id=?",((config.now()-timedelta(days=1)).isoformat(),eid))
    mailbox=Mock()
    mailbox.login.return_value=("OK",[])
    mailbox.select.return_value=("OK",[])
    mailbox.response.return_value=("UIDVALIDITY",[b"100"])
    raw=message().as_bytes()
    def uid(operation,*args):
        if operation=="search": return "OK",[b"1"]
        return "OK",[(b"1 (RFC822.SIZE 100)",raw),b")"]
    mailbox.uid.side_effect=uid
    monkeypatch.setattr(config,"GMAIL_ADDRESS","owner@example.test")
    monkeypatch.setattr(config,"GMAIL_APP_PASSWORD","synthetic")
    monkeypatch.setattr(replies.imaplib,"IMAP4_SSL",Mock(return_value=mailbox))
    assert len(replies.check_replies())==1
    assert EmailRepository.get_by_id(eid)["status"]=="replied"
    assert replies.check_replies()==[]
    assert mailbox.uid.call_args_list[-1].args==("search",None,"UID","2:*")
    mailbox.response.return_value=("UIDVALIDITY",[b"200"])
    assert len(replies.check_replies())==1
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reply_messages").fetchone()[0]==2
        assert conn.execute("SELECT COUNT(*) FROM events WHERE kind='replied'").fetchone()[0]==1
    mailbox.select.assert_called_with("INBOX",readonly=True)
    assert mailbox.logout.call_count==3

@pytest.mark.parametrize("stage",["select","search","fetch"])
def test_imap_failures_visible_and_cursor_not_advanced(contact,monkeypatch,stage):
    from datetime import timedelta
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    with get_connection() as conn:
        conn.execute("UPDATE emails SET status='sent',sent_at=?,message_id='<sent@test>' WHERE id=?",((config.now()-timedelta(days=1)).isoformat(),eid))
    mailbox=Mock()
    mailbox.login.return_value=("OK",[])
    mailbox.select.return_value=("NO",[]) if stage=="select" else ("OK",[])
    mailbox.response.return_value=("UIDVALIDITY",[b"100"])
    mailbox.uid.side_effect=lambda op,*args:("NO",[]) if op==stage else ("OK",[b"1"])
    monkeypatch.setattr(config,"GMAIL_ADDRESS","owner@example.test")
    monkeypatch.setattr(config,"GMAIL_APP_PASSWORD","synthetic")
    monkeypatch.setattr(replies.imaplib,"IMAP4_SSL",Mock(return_value=mailbox))
    with pytest.raises(ProviderError): replies.check_replies()
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM settings WHERE key LIKE 'imap_cursor:%'").fetchone()[0]==0
    mailbox.logout.assert_called_once()
