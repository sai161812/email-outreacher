from unittest.mock import Mock
import pytest
import config,replies,sender,reviewer
from errors import ProviderError
from repository import EmailRepository
from db import get_connection
from test_sender import mail
from test_followups import sent
from test_replies import message


def test_backlog_hides_no_reply_and_next_scan_closes_thread(contact,mail,monkeypatch):
    parent=sent(contact)
    original=EmailRepository.get_by_id(parent)
    mailbox=Mock();mailbox.login.return_value=('OK',[]);mailbox.select.return_value=('OK',[])
    mailbox.response.return_value=('UIDVALIDITY',[b'100'])
    def uid(op,*args):
        if op=='search':
            start=int(args[-1].split(':')[0])
            return 'OK',[' '.join(str(i) for i in range(start,502)).encode()]
        number=int(args[0])
        msg=message(reference=original['message_id'] if number==501 else '<unrelated@test>')
        return 'OK',[(b'1 (RFC822.SIZE 200)',msg.as_bytes()),b')']
    mailbox.uid.side_effect=uid
    monkeypatch.setattr(replies.imaplib,'IMAP4_SSL',Mock(return_value=mailbox))
    first=replies.check_replies(detailed=True)
    assert first['scanned']==500 and first['remaining']==1 and not first['complete']
    assert first['matches']==[]
    second=replies.check_replies(detailed=True)
    assert second['complete'] and second['scanned']==1
    assert second['last_successful_at']
    assert EmailRepository.get_by_id(parent)['status']=='replied'
    monkeypatch.setattr(config,'IMAP_MAILBOX','Archive')
    replies.check_replies(detailed=True)
    mailbox.select.assert_called_with('"Archive"',readonly=True)


@pytest.mark.parametrize('result',[{'complete':False},ProviderError('Mailbox unavailable')])
def test_followup_deferred_if_current_scan_incomplete_or_fails(contact,mail,monkeypatch,result):
    parent=sent(contact)
    original=EmailRepository.get_by_id(parent)
    child=EmailRepository.create(original['company_id'],original['contact_id'],None,'H','Re: S','Body',None,parent)
    reviewer.approve(child)
    scan=Mock(side_effect=result) if isinstance(result,Exception) else Mock(return_value=result)
    monkeypatch.setattr(replies,'check_replies',scan)
    summary=sender.run_send_batch()
    assert summary[0]['status']=='deferred'
    assert EmailRepository.get_by_id(child)['status']=='approved'
    mail.sendmail.assert_not_called()


def test_unreviewed_oversized_report_keeps_followups_blocked(contact,mail,monkeypatch):
    from test_replies import delivery_report
    from app import create_app
    sent(contact)
    mailbox=Mock();mailbox.login.return_value=('OK',[]);mailbox.select.return_value=('OK',[])
    mailbox.response.return_value=('UIDVALIDITY',[b'100'])
    raw=delivery_report().as_bytes()
    mailbox.uid.side_effect=lambda op,*args:('OK',[b'1']) if op=='search' else ('OK',[(f'1 (RFC822.SIZE {config.MAX_UPLOAD_BYTES+1})'.encode(),raw),b')'])
    monkeypatch.setattr(replies.imaplib,'IMAP4_SSL',Mock(return_value=mailbox))
    assert not replies.check_replies(detailed=True)['complete']
    second=replies.check_replies(detailed=True)
    assert not second['complete'] and second['unreviewed_reports']==1
    client=create_app({'TESTING':True}).test_client()
    token=client.get('/api/session').get_json()['csrf']
    reports=client.get('/api/settings').get_json()['skipped_reply_reports']
    response=client.post('/api/reply-reports/review',json={'key':reports[0]['key']},headers={'X-CSRF-Token':token})
    assert response.status_code==200
    assert replies.check_replies(detailed=True)['complete']
