from datetime import timedelta
import pytest
import config
import delivery
import followups
import reviewer
import sender
import tracker
from db import get_connection
from repository import EmailRepository
from errors import Conflict

def sent(contact,days=10):
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    # Synthetic historical state, never delivery to real mail.
    with get_connection() as conn:
        conn.execute("UPDATE emails SET status='sent',sent_at=?,message_id=? WHERE id=?",((config.now()-timedelta(days=days)).isoformat(),f"<{eid}@test>",eid))
    return eid

def test_due_replacement_and_limit(contact):
    parent=sent(contact)
    assert [r["id"] for r in followups.due()]==[parent]
    original=EmailRepository.get_by_id(parent)
    child=EmailRepository.create(original["company_id"],original["contact_id"],None,"H","Re: S","B",None,parent)
    assert followups.due()==[]
    reviewer.reject(child)
    assert followups.due()[0]["id"]==parent

def test_early_followup_blocked(contact):
    parent=sent(contact,0)
    original=EmailRepository.get_by_id(parent)
    with get_connection() as conn,pytest.raises(Conflict,match="not due"):
        followups.check(conn,{**original,"follow_up_to_email_id":parent})

def test_reply_cancels_queued_followup(contact):
    parent=sent(contact)
    original=EmailRepository.get_by_id(parent)
    child=EmailRepository.create(original["company_id"],original["contact_id"],None,"H","Re: S","B",None,parent)
    reviewer.approve(child)
    tracker.mark_replied(parent)
    assert EmailRepository.get_by_id(child)["status"]=="canceled"
    assert sender.get_approved_queue()==[]
    assert followups.due()==[]

def test_sent_outcomes_are_cumulative(contact):
    parent=sent(contact)
    tracker.mark_replied(parent)
    tracker.mark_interview_scheduled(parent)
    tracker.mark_offer(parent)
    summary=tracker.pipeline_summary()
    assert summary["sent"]==summary["replied"]==1
    entry=tracker.stats()["by_variant"][0]
    assert entry["sent"]==entry["replied"]==entry["interviews"]==entry["offers"]==1
