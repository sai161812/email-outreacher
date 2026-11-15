import json
import pytest
import composer,opportunities,db
from repository import EmailRepository
from test_composer import ready
from test_followups import sent

@pytest.mark.parametrize('regeneration',[False,True])
def test_followup_stores_actual_request_and_warns_when_role_changes(ready,monkeypatch,regeneration):
    company,person=ready
    oid=opportunities.save(company,{'role':'Backend','job_text':'Python'})
    parent=sent(ready)
    with db.get_connection() as conn: conn.execute('UPDATE emails SET opportunity_id=? WHERE id=?',(oid,parent))
    seen=[]
    def generate(request,*args):
        seen.append(request)
        if not regeneration: opportunities.save(company,{'role':'Changed role'},oid)
        return {'subject':'Re: S','body':'Following up on my Python dashboard. Could you advise?','generation':{'calls':1}}
    monkeypatch.setattr(composer,'_generate',generate)
    child=composer.compose_follow_up_and_store(parent,resume_variant_id=None)
    if regeneration: composer.regenerate(child,EmailRepository.get_by_id(child)['revision'])
    row=EmailRepository.get_by_id(child);snapshot=json.loads(row['input_snapshot_json'])
    assert snapshot['request']==seen[-1]
    assert json.loads(seen[-1])['original_body']==EmailRepository.get_by_id(parent)['body']
    assert snapshot['generation']['calls']==1
    if not regeneration: assert 'changed during generation' in row['qc_warnings']

def test_failed_followup_regeneration_keeps_draft(ready,monkeypatch):
    parent=sent(ready)
    monkeypatch.setattr(composer,'_generate',lambda *a:{'subject':'Re: S','body':'Following up on my Python dashboard. Could you advise?'})
    child=composer.compose_follow_up_and_store(parent,resume_variant_id=None)
    before=EmailRepository.get_by_id(child)
    def fail(*a): raise RuntimeError('synthetic failure')
    monkeypatch.setattr(composer,'_generate',fail)
    with pytest.raises(RuntimeError): composer.regenerate(child,before['revision'])
    assert EmailRepository.get_by_id(child)==before
