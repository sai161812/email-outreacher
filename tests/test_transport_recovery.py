from unittest.mock import Mock
import pytest
import delivery
import sender
import reviewer
from repository import EmailRepository
from db import get_connection
from test_sender import draft,mail


@pytest.mark.parametrize('failure',[TimeoutError,ValueError])
def test_failure_to_record_unknown_submission_never_marks_failed(draft,mail,monkeypatch,failure):
    reviewer.approve(draft)
    mail.sendmail.side_effect=failure('unknown outcome')
    finish=delivery.finish
    states=[]
    def flaky(aid,state,*args,**kwargs):
        states.append(state)
        if len(states)==1: raise RuntimeError('database unavailable')
        return finish(aid,state,*args,**kwargs)
    monkeypatch.setattr(delivery,'finish',flaky)
    assert sender.run_send_batch()[0]['status']=='uncertain'
    assert 'failed' not in states and 'canceled' not in states
    assert EmailRepository.get_by_id(draft)['status'] in {'sending','uncertain'}
    delivery.recover()
    assert EmailRepository.get_by_id(draft)['status']=='uncertain'
    assert sender.run_send_batch()==[]
    assert mail.sendmail.call_count==1


def test_acceptance_and_all_result_writes_fail_recover_uncertain(draft,mail,monkeypatch):
    reviewer.approve(draft)
    monkeypatch.setattr(EmailRepository,'update_sent',Mock(side_effect=RuntimeError()))
    monkeypatch.setattr(delivery,'finish',Mock(side_effect=RuntimeError()))
    assert sender.run_send_batch()[0]['status']=='uncertain'
    with get_connection() as conn:
        assert conn.execute('SELECT state FROM send_attempts').fetchone()[0]=='submitting'
    delivery.recover()
    assert EmailRepository.get_by_id(draft)['status']=='uncertain'
    assert mail.sendmail.call_count==1
