from email.message import EmailMessage
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
    return {"id":1,"message_id":"<sent@test>","contact_email":"person@example.test","sent_at":(config.now()-timedelta(days=1)).isoformat()}

@pytest.mark.parametrize("kwargs",[{"reference":"<sent@test.extra>"},{"sender":"other@example.test"},{"old":True},{"auto":True}])
def test_false_replies_rejected(kwargs):
    assert replies.matched_candidates(message(**kwargs),[candidate()])==[]

def test_exact_reply_matches():
    assert replies.matched_candidates(message(),[candidate()])[0]["id"]==1

def test_no_id_has_no_address_fallback():
    c=candidate();c["message_id"]=None
    assert replies.matched_candidates(message(),[c])==[]

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
