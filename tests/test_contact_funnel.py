import tracker
from repository import EmailRepository
from db import get_connection
from test_followups import sent

def test_followups_count_as_messages_not_people_and_rejection_is_not_positive(contact):
    parent=sent(contact)
    original=EmailRepository.get_by_id(parent)
    child=EmailRepository.create(*contact,None,'H','Re: S','Body',None,parent)
    with get_connection() as conn:
        conn.execute("UPDATE emails SET status='sent',sent_at=?,message_id='<followup@test>' WHERE id=?",(original['sent_at'],child))
    tracker.mark_replied(child)
    funnel=tracker.contact_funnel()
    assert funnel['sent_messages']==2 and funnel['contacted']==funnel['initial_contacts']==funnel['conversations']==1
    assert funnel['human_responses']==1 and funnel['positive_interest_or_referral']==0
    tracker.categorize(child,'rejection')
    assert tracker.contact_funnel()['positive_interest_or_referral']==0
    tracker.categorize(child,'referral')
    assert tracker.contact_funnel()['positive_interest_or_referral']==1
    assert tracker.contact_funnel()['interviews']==0

def test_terminal_outcome_does_not_invent_response_or_interview(contact):
    eid=sent(contact);tracker.mark_no_offer(eid)
    funnel=tracker.contact_funnel()
    assert funnel['human_responses']==funnel['interviews']==funnel['positive_interest_or_referral']==0
    assert funnel['cohorts'][0]['contacted']==1

def test_category_closes_due_followup_without_automatic_sending(contact):
    parent=sent(contact)
    child=EmailRepository.create(*contact,None,'H','Re: S','Body',None,parent)
    tracker.categorize(parent,'positive_interest')
    assert EmailRepository.get_by_id(child)['status']=='canceled'
    assert tracker.due_for_follow_up()==[]
