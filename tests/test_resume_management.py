from email import message_from_bytes
import pytest
import config,resume,reviewer,sender
from db import get_connection
from repository import EmailRepository
from app import create_app
from test_api import post
from test_sender import mail
from conftest import pdf_bytes

def test_replacement_preserves_sent_asset_and_revokes_approval(contact,mail):
    company,person=contact
    path=config.RESUME_DIR/'original.pdf';path.write_bytes(pdf_bytes('original'))
    rid=resume.add_resume_variant('Original','python',str(path))
    eid=EmailRepository.create(company,person,rid,'H','S','Body',None);reviewer.approve(eid)
    replacement=config.RESUME_DIR/'new.pdf';replacement.write_bytes(pdf_bytes('new'))
    new=resume.revise(rid,{'name':'New version'},str(replacement))
    row=EmailRepository.get_by_id(eid)
    assert row['resume_variant_id']==new and row['status']=='pending_review' and row['approval_json'] is None
    assert path.read_bytes()==pdf_bytes('original')
    reviewer.approve(eid);sender.run_send_batch()
    resume.revise(new,{},archive=True)
    assert EmailRepository.get_by_id(eid)['resume_variant_id']==new
    client=create_app({'TESTING':True}).test_client()
    assert client.get(f'/api/resumes/{rid}/pdf').status_code==200
    assert client.get(f'/api/resumes/{new}/pdf').status_code==200

def test_archive_requires_explicit_new_selection_and_auto_skips_unusable(contact):
    path=config.RESUME_DIR/'cv.pdf';path.write_bytes(pdf_bytes())
    rid=resume.add_resume_variant('CV','python',str(path))
    eid=EmailRepository.create(*contact,rid,'H','S','Body',None);reviewer.approve(eid)
    resume.revise(rid,{},archive=True)
    assert EmailRepository.get_by_id(eid)['resume_variant_id']==rid
    with pytest.raises(ValueError): reviewer.approve(eid)
    assert resume.pick_best_variant('python') is None

def test_auto_does_not_silently_drop_unusable_registered_resumes(contact):
    from repository import ResumeRepository
    ResumeRepository.create('Missing','python',str(config.RESUME_DIR/'missing.pdf'))
    client=create_app({'TESTING':True}).test_client()
    response=post(client,'/api/compose',{'company_id':contact[0],'contact_id':contact[1]})
    assert response.status_code==400 and 'No resume explicitly' in response.get_json()['error']
    response=post(client,'/api/compose',{'company_id':contact[0],'contact_id':contact[1],'resume_variant_id':None})
    assert response.status_code==202

@pytest.mark.parametrize('mode',['link','attach'])
def test_preview_matches_mime_without_sending(contact,mail,monkeypatch,mode):
    monkeypatch.setattr(config,'RESUME_ATTACH_MODE',mode)
    path=config.RESUME_DIR/'cv.pdf';path.write_bytes(pdf_bytes())
    rid=resume.add_resume_variant('CV','python',str(path),'https://example.test/cv.pdf')
    eid=EmailRepository.create(*contact,rid,'H','Subject','Reviewed body',None)
    client=create_app({'TESTING':True}).test_client()
    preview=client.get(f'/api/review/{eid}/preview').get_json()
    mail.sendmail.assert_not_called()
    reviewer.approve(eid);sender.run_send_batch()
    from email import policy
    message=message_from_bytes(mail.sendmail.call_args.args[2],policy=policy.default)
    assert preview['sender']==message['From'] and preview['recipient']==message['To']
    assert preview['subject']==message['Subject']
    assert preview['body']==message.get_body(preferencelist=('plain',)).get_content()
    assert preview['attachments']==[p.get_filename() for p in message.iter_attachments()]
