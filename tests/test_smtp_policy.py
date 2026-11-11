import smtplib
from unittest.mock import Mock
import pytest
import sender,reviewer,replies,config
from repository import SuppressionRepository,EmailRepository
from db import get_connection
from test_sender import draft,mail
from test_fixed_batches import another
from test_followups import sent
from test_replies import delivery_report


@pytest.mark.parametrize('code,text,suppressed,paused',[(550,b'5.1.1 no such mailbox',True,False),(550,b'5.7.1 policy refusal',False,True),(450,b'4.7.0 rate limit',False,True),(550,b'mail refused',False,True)])
def test_recipient_rejection_classification_and_batch_pause(contact,draft,mail,code,text,suppressed,paused):
    reviewer.approve(draft);second=another(contact)
    mail.sendmail.side_effect=[smtplib.SMTPRecipientsRefused({'person@example.test':(code,text)}),{}]
    result=sender.run_send_batch()
    assert result[0]['status']=='failed' and result[0]['smtp_code']==code
    assert SuppressionRepository.is_suppressed('person@example.test')==suppressed
    assert result[1]['status']==('deferred' if paused else 'sent')
    assert mail.sendmail.call_count==(1 if paused else 2)
    with get_connection() as conn:
        assert conn.execute('SELECT error_code FROM send_attempts WHERE email_id=?',(draft,)).fetchone()[0].startswith('smtp:recipient:')


@pytest.mark.parametrize('error',[smtplib.SMTPDataError(554,b'5.7.1 private-provider-text'),smtplib.SMTPAuthenticationError(535,b'5.7.8 private-provider-text')])
def test_account_rejection_pauses_and_redacts(contact,draft,mail,error):
    reviewer.approve(draft);another(contact)
    mail.sendmail.side_effect=error
    result=sender.run_send_batch()
    assert [r['status'] for r in result]==['failed','deferred']
    assert 'private-provider-text' not in str(result)
    assert not SuppressionRepository.is_suppressed('person@example.test')


def test_suppression_preserves_creation_and_removal_history(draft):
    SuppressionRepository.add('person@example.test','first reason')
    with get_connection() as conn:
        conn.execute("UPDATE suppressions SET created_at='2000-01-01'")
    SuppressionRepository.add(' PERSON@EXAMPLE.TEST ','updated reason')
    with get_connection() as conn:
        assert conn.execute('SELECT created_at FROM suppressions').fetchone()[0]=='2000-01-01'
    SuppressionRepository.remove('person@example.test')
    with get_connection() as conn:
        assert [r[0] for r in conn.execute('SELECT action FROM suppression_events ORDER BY id')]==['added','added','removed']
    assert EmailRepository.get_by_id(draft)['status']=='canceled'


def test_policy_delivery_report_closes_thread_without_suppressing_address(contact,mail,monkeypatch):
    parent=sent(contact)
    report=delivery_report(status='5.7.1')
    report.get_payload()[2].get_payload()[0].replace_header('Message-ID',f'<{parent}@test>')
    raw=report.as_bytes()
    mailbox=Mock();mailbox.login.return_value=('OK',[]);mailbox.select.return_value=('OK',[])
    mailbox.response.return_value=('UIDVALIDITY',[b'100'])
    mailbox.uid.side_effect=lambda op,*args:('OK',[b'1']) if op=='search' else ('OK',[(f'1 (RFC822.SIZE {len(raw)})'.encode(),raw),b')'])
    monkeypatch.setattr(replies.imaplib,'IMAP4_SSL',Mock(return_value=mailbox))
    assert replies.check_replies()[0]['kind']=='bounced'
    assert EmailRepository.get_by_id(parent)['status']=='bounced'
    assert not SuppressionRepository.is_suppressed('person@example.test')
