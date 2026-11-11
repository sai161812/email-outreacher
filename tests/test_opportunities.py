import json
import pytest
import composer,opportunities,reviewer,resume,config,db
from errors import Conflict
from repository import EmailRepository,ContactRepository
from test_composer import ready
from test_followups import sent
from conftest import pdf_bytes

def test_two_roles_use_distinct_sources_and_duplicate_guard(ready,monkeypatch):
    company,person=ready
    projects=opportunities.save_projects([{'name':'CSV dashboard','action':'Built a personal Python CSV dashboard','proof_url':'https://example.test/proof'}])
    a=opportunities.save(company,{'role':'Backend engineer','job_text':'Python SQL','project_id':projects[0]['id']})
    b=opportunities.save(company,{'role':'Frontend engineer','job_text':'React UI'})
    seen=[]
    def generate(co,ct,facts):
        seen.append((co,facts))
        return {'subject':co['target_brief']['role'],'body':'Built a personal dashboard. Could you advise?','hook':'Relevant work','research_notes':'Owner evidence only'}
    monkeypatch.setattr(composer,'compose_email',generate)
    first=composer.compose_and_store(company,person,opportunity_id=a)
    other=ContactRepository.create(company,'another@example.test')
    second=composer.compose_and_store(company,other,opportunity_id=b)
    assert seen[0][0]['job_text']=='Python SQL' and seen[1][0]['job_text']=='React UI'
    assert 'CSV dashboard' in seen[0][1]
    with pytest.raises(Conflict): composer.compose_and_store(company,person,opportunity_id=b)
    row=EmailRepository.get_by_id(first);snapshot=row['input_snapshot_json']
    with pytest.raises(Conflict,match='Verify'): reviewer.approve(first)
    opportunities.acknowledge(first,row['revision']);reviewer.approve(first)
    opportunities.save(company,{'role':'Backend engineer updated','job_text':'New description'},a)
    changed=EmailRepository.get_by_id(first)
    assert changed['status']=='pending_review' and changed['evidence_verified_at'] is None
    assert changed['input_snapshot_json']==snapshot
    assert EmailRepository.get_by_id(second)['subject']=='Frontend engineer'

def test_mid_generation_role_change_is_visible(ready,monkeypatch):
    company,person=ready
    oid=opportunities.save(company,{'role':'Backend','job_text':'Python'})
    def generate(*args):
        opportunities.save(company,{'role':'Changed role'},oid)
        return {'subject':'Backend','body':'Built a Python dashboard. Could you advise?','hook':'H','research_notes':'Notes'}
    monkeypatch.setattr(composer,'compose_email',generate)
    eid=composer.compose_and_store(company,person,opportunity_id=oid)
    assert 'changed during generation' in EmailRepository.get_by_id(eid)['qc_warnings']

def test_followup_can_explicitly_drop_missing_original_resume(ready,monkeypatch):
    parent=sent(ready)
    pdf=config.RESUME_DIR/'old.pdf';pdf.write_bytes(pdf_bytes())
    rid=resume.add_resume_variant('Old CV','python',str(pdf))
    with db.get_connection() as conn: conn.execute('UPDATE emails SET resume_variant_id=? WHERE id=?',(rid,parent))
    pdf.unlink()
    monkeypatch.setattr(composer,'compose_follow_up',lambda *a:{'subject':'ignored','body':'Following up on my personal dashboard. Could you advise?'})
    child=composer.compose_follow_up_and_store(parent,resume_variant_id=None)
    assert EmailRepository.get_by_id(child)['resume_variant_id'] is None

def test_project_edit_clears_verified_acknowledgment(ready):
    company,person=ready
    oid=opportunities.save(company,{'role':'Backend'})
    eid=composer.manual_draft(company,person,'Backend','Built a personal dashboard.',opportunity_id=oid)
    opportunities.acknowledge(eid,1)
    opportunities.save_projects([{'name':'New facts','action':'Built a new dashboard'}])
    assert EmailRepository.get_by_id(eid)['evidence_verified_at'] is None

def test_migration_backfills_company_job_and_preserves_old_drafts(contact):
    company,person=contact
    eid=EmailRepository.create(company,person,None,'H','S','Body',None)
    with db.get_connection() as conn:
        conn.execute("UPDATE companies SET job_url='https://example.test/job',job_text='Python role' WHERE id=?",(company,))
        conn.execute('PRAGMA user_version=5')
    db.init_db();db.init_db()
    defaults=opportunities.list_all(company)
    assert len(defaults)==1 and defaults[0]['job_text']=='Python role'
    assert EmailRepository.get_by_id(eid)['body']=='Body'


def test_api_auto_resume_uses_selected_role_description(ready,monkeypatch):
    from app import create_app
    from test_api import post
    monkeypatch.setattr(config,'RESUME_ATTACH_MODE','link')
    python=resume.add_resume_variant('Python','python',resume_url='https://example.test/python.pdf')
    react=resume.add_resume_variant('React','react',resume_url='https://example.test/react.pdf')
    company,person=ready
    oid=opportunities.save(company,{'role':'Frontend','job_text':'React UI'})
    client=create_app({'TESTING':True}).test_client()
    response=post(client,'/api/compose',{'company_id':company,'contact_id':person,'opportunity_id':oid})
    assert response.status_code==202 and response.get_json()['payload']['resume_variant_id']==react
    assert post(client,'/api/opportunities',{'company_id':company,'role':'Role','application_status':'applied','application_date':'not-a-date'}).status_code==400
    assert post(client,'/api/projects',{'projects':[{'name':'Invented','action':'A','unknown':'B'}]}).status_code==400
