from unittest.mock import Mock
import pytest
import composer,config,reviewer,sender,candidate_profile
from repository import EmailRepository,SuppressionRepository
from errors import Conflict,ProviderError
from test_composer import ready
from test_sender import mail

def test_manual_without_gemini_sends_only_after_approval(contact,mail,monkeypatch):
    candidate_profile.set_profile('Candidate')
    monkeypatch.setattr(config,'GEMINI_API_KEY','')
    eid=composer.manual_draft(*contact,'Backend role','Built a Python dashboard. Could you advise on the application route?')
    assert sender.run_send_batch()==[]
    reviewer.edit(eid,body='Reviewed truthful pitch. Could you advise?')
    reviewer.approve(eid)
    assert sender.run_send_batch()[0]['status']=='sent'
    assert mail.sendmail.call_count==1
    with pytest.raises(Conflict): composer.manual_draft(*contact,'S','Another pitch')

def test_regeneration_failure_preserves_manual_edits_and_success_revokes_approval(ready,monkeypatch):
    eid=composer.manual_draft(*ready,'Original','Manually edited pitch. Could you advise?')
    reviewer.approve(eid)
    old=EmailRepository.get_by_id(eid)
    generate=composer.compose_email
    monkeypatch.setattr(composer,'compose_email',Mock(side_effect=ProviderError('provider unavailable')))
    with pytest.raises(ProviderError): composer.regenerate(eid,old['revision'])
    assert EmailRepository.get_by_id(eid)==old
    monkeypatch.setattr(composer,'compose_email',generate)
    composer.regenerate(eid,old['revision'])
    new=EmailRepository.get_by_id(eid)
    assert new['revision']==old['revision']+1 and new['status']=='pending_review' and new['approval_json'] is None

def test_regeneration_does_not_overwrite_concurrent_edit(ready,monkeypatch):
    eid=composer.manual_draft(*ready,'S','A truthful pitch')
    def generate(*args):
        reviewer.edit(eid,body='Newer owner edit')
        return {'subject':'S','body':'Generated pitch','hook':'H','research_notes':'Notes'}
    monkeypatch.setattr(composer,'compose_email',generate)
    with pytest.raises(Conflict): composer.regenerate(eid,1)
    assert EmailRepository.get_by_id(eid)['body']=='Newer owner edit'

def test_suppressed_manual_is_blocked(ready):
    SuppressionRepository.add('person@example.test','Do not contact')
    with pytest.raises(Conflict): composer.manual_draft(*ready,'S','Pitch')
