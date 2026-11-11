from datetime import timedelta
from unittest.mock import Mock
import pytest
import config,delivery,replies,reviewer,sender
from db import get_connection
from repository import EmailRepository
from test_sender import draft,mail
from test_replies import message,delivery_report


@pytest.mark.parametrize('kind,accepted,expected',[('human',True,'replied'),('bounced',True,'bounced'),('human',False,'failed')])
def test_scan_before_reconciliation_retains_thread_evidence(draft,mail,monkeypatch,kind,accepted,expected):
    reviewer.approve(draft)
    attempt=delivery.claim(draft)
    delivery.prepare(attempt['attempt_id'])
    delivery.finish(attempt['attempt_id'],'uncertain')
    msg=message(reference=attempt['message_id']) if kind=='human' else delivery_report()
    if kind=='bounced':
        original=msg.get_payload()[2].get_payload()[0]
        original.replace_header('Message-ID',attempt['message_id'])
    mailbox=Mock()
    mailbox.login.return_value=('OK',[]);mailbox.select.return_value=('OK',[])
    mailbox.response.return_value=('UIDVALIDITY',[b'100'])
    raw=msg.as_bytes()
    mailbox.uid.side_effect=lambda op,*args:('OK',[b'1']) if op=='search' else ('OK',[(f'1 (RFC822.SIZE {len(raw)})'.encode(),raw),b')'])
    monkeypatch.setattr(replies.imaplib,'IMAP4_SSL',Mock(return_value=mailbox))
    assert replies.check_replies()==[]
    with get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM reply_evidence').fetchone()[0]==1
        assert conn.execute("SELECT value FROM settings WHERE key LIKE 'imap_cursor:%'").fetchone()[0]=='1'
    delivery.reconcile(attempt['attempt_id'],accepted)
    replies.replay_evidence()
    assert EmailRepository.get_by_id(draft)['status']==expected
    with get_connection() as conn:
        assert conn.execute('SELECT processed FROM reply_evidence').fetchone()[0]==1


def test_replay_failure_does_not_hide_committed_reconciliation(draft,mail,monkeypatch):
    reviewer.approve(draft)
    attempt=delivery.claim(draft);delivery.prepare(attempt['attempt_id'])
    delivery.finish(attempt['attempt_id'],'uncertain')
    monkeypatch.setattr(replies,'replay_evidence',Mock(side_effect=RuntimeError('storage unavailable')))
    assert delivery.reconcile(attempt['attempt_id'],True)['reply_replay_pending']
    assert EmailRepository.get_by_id(draft)['status']=='sent'
