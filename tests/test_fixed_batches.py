import jobs,sender,reviewer,config
from repository import EmailRepository,ContactRepository
from db import get_connection
from test_sender import draft,mail

def another(contact):
    company,_=contact
    cid=ContactRepository.create(company,'second@example.test')
    eid=EmailRepository.create(company,cid,None,'Hook','Subject','Body',None)
    reviewer.approve(eid)
    return eid

def test_queued_batch_excludes_later_approvals_and_idempotency_survives(contact,draft,mail):
    reviewer.approve(draft)
    job=jobs.enqueue('send',{},'fixed-key')
    later=another(contact)
    assert jobs.enqueue('send',{'dry_run':False},'fixed-key')['id']==job['id']
    assert jobs.process_next()
    assert EmailRepository.get_by_id(draft)['status']=='sent'
    assert EmailRepository.get_by_id(later)['status']=='approved'
    assert mail.sendmail.call_count==1

def test_changed_revision_is_skipped_even_if_reapproved(draft,mail):
    reviewer.approve(draft)
    job=jobs.enqueue('send',{})
    reviewer.edit(draft,body='New body');reviewer.approve(draft)
    jobs.process_next()
    assert jobs.get(job['id'])['result']['counts']['skipped']==1
    mail.sendmail.assert_not_called()

def test_pending_cancel_makes_no_claim(draft,mail):
    reviewer.approve(draft)
    job=jobs.enqueue('send',{})
    jobs.stop(job['id'])
    assert not jobs.process_next()
    assert EmailRepository.get_by_id(draft)['status']=='approved'
    mail.sendmail.assert_not_called()

def test_stop_during_delay_keeps_remaining_approved(contact,draft,mail,monkeypatch):
    reviewer.approve(draft);later=another(contact)
    job=jobs.enqueue('send',{})
    monkeypatch.setattr(config,'MIN_DELAY_SECONDS',2)
    monkeypatch.setattr(config,'MAX_DELAY_SECONDS',2)
    monkeypatch.setattr(sender.time,'sleep',lambda seconds:jobs.stop(job['id']))
    jobs.process_next()
    result=jobs.get(job['id'])
    assert result['status']=='canceled'
    assert result['result']['counts']['sent']==1
    assert result['result']['counts']['canceled']==1
    assert EmailRepository.get_by_id(later)['status']=='approved'
    assert mail.sendmail.call_count==1

def test_preview_members_never_reserve_or_send(draft,mail):
    reviewer.approve(draft)
    job=jobs.enqueue('send',{'dry_run':True})
    jobs.process_next()
    assert jobs.get(job['id'])['result']['counts']['dry_run']==1
    with get_connection() as conn: assert conn.execute('SELECT count(*) FROM send_attempts').fetchone()[0]==0
    mail.sendmail.assert_not_called()
