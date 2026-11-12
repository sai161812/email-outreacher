import pytest
import tracker
from repository import EmailRepository,SuppressionRepository,rows
from test_followups import sent
from errors import Conflict

def test_manual_interview_correction_preserves_delivery_and_audit(contact):
    eid=sent(contact)
    before=EmailRepository.get_by_id(eid)
    tracker.mark_interview_scheduled(eid,source='manual')
    item=tracker.tracking_page()[0]
    assert item['correctable_event_id']
    tracker.correct_outcome(eid,item['correctable_event_id'],'Selected the wrong row')
    after=EmailRepository.get_by_id(eid)
    assert after['status']=='sent' and after['sent_at']==before['sent_at']
    assert tracker.stats()['by_variant'][0]['interviews']==0
    assert rows("SELECT * FROM events WHERE kind='outcome_corrected'")
    with pytest.raises(Conflict): tracker.correct_outcome(eid,item['correctable_event_id'],'Repeated correction')

def test_system_outcome_cannot_be_corrected_and_bounce_suppression_is_retained(contact):
    eid=sent(contact)
    tracker.mark_replied(eid)
    assert tracker.tracking_page()[0]['correctable_event_id'] is None
    event=rows("SELECT id FROM events WHERE kind='replied'")[0]['id']
    with pytest.raises(Conflict): tracker.correct_outcome(eid,event,'Not manual')
    tracker.mark_no_offer(eid,source='manual')
    item=tracker.tracking_page()[0]
    SuppressionRepository.add('person@example.test','Do not contact')
    tracker.correct_outcome(eid,item['correctable_event_id'],'Wrong outcome')
    assert SuppressionRepository.is_suppressed('person@example.test')

def test_tracking_exposes_only_valid_choices(contact):
    eid=sent(contact)
    tracker.mark_offer(eid)
    assert tracker.tracking_page()[0]['allowed_outcomes']==[]
