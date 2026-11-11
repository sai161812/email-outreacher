import json
from pathlib import Path
import sqlite3
import pytest
import config
import db
import resume
from conftest import pdf_bytes
from operations import diagnostics,backup_bundle,restore_bundle

@pytest.mark.parametrize("data",[b"%PDF-1.4\nnot a document",pdf_bytes(pages=0),pdf_bytes(encrypted=True)])
def test_unusable_pdfs_rejected(temp_db,data):
    with pytest.raises(ValueError): resume.validate_pdf(data)

def test_real_pdf_and_bundle_restore(contact,tmp_path,monkeypatch):
    import candidate_profile
    from repository import EmailRepository
    import reviewer
    path=config.RESUME_DIR/'cv.pdf';path.write_bytes(pdf_bytes())
    rid=resume.add_resume_variant('CV','python',str(path))
    candidate_profile.save_settings({'full_name':'Candidate'},'Verified facts')
    eid=EmailRepository.create(*contact,rid,'H','S','Body',None)
    reviewer.approve(eid)
    bundle=backup_bundle(tmp_path/'bundle')
    restored=restore_bundle(bundle,tmp_path/'restored.db',tmp_path/'restored-resumes')
    monkeypatch.setattr(config,'DB_PATH',restored)
    monkeypatch.setattr(config,'RESUME_DIR',tmp_path/'restored-resumes')
    assert resume.delivery_asset(rid)['sha256']
    assert candidate_profile.get_settings()['candidate_context']=='Verified facts'
    assert EmailRepository.get_by_id(eid)['status']=='pending_review'
    with pytest.raises(ValueError): restore_bundle(bundle,restored,tmp_path/'other')
    (bundle/'resume-1.pdf').write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum'): restore_bundle(bundle,tmp_path/'bad.db',tmp_path/'bad-assets')
    assert not (tmp_path/'bad.db').exists()

def test_diagnostics_never_initializes_legacy_database(tmp_path,monkeypatch):
    target=tmp_path/'legacy.db';monkeypatch.setattr(config,'DB_PATH',target)
    with sqlite3.connect(target) as conn: conn.execute('CREATE TABLE preserved(value TEXT)')
    monkeypatch.setattr(config,'GEMINI_API_KEY','secret-key')
    report=diagnostics()
    assert report['schema']==0
    assert report['configuration']['gemini_configured']
    assert 'secret-key' not in json.dumps(report)
    with sqlite3.connect(target) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==0

def test_observed_legacy_tables_and_duplicate_history_survive(tmp_path,monkeypatch):
    target=tmp_path/'legacy.db';monkeypatch.setattr(config,'DB_PATH',target)
    with sqlite3.connect(target) as conn:
        conn.executescript((Path(__file__).parent/"fixtures"/"observed_legacy_schema.sql").read_text(encoding="utf8"))
        for name in ('unknown_extension',):
            conn.execute(f'CREATE TABLE {name}(id INTEGER PRIMARY KEY, evidence TEXT)')
            conn.execute(f"INSERT INTO {name} VALUES (1,'preserve')")
        conn.execute("INSERT INTO companies(id,name) VALUES (1,'Example')")
        conn.executemany("INSERT INTO contacts(id,company_id,email) VALUES (?,1,'same@example.test')",[(1,),(2,)])
        conn.execute("INSERT INTO emails(company_id,contact_id,status,sent_at) VALUES (1,1,'replied','2026-01-01T00:00:00+00:00')")
    db.init_db()
    with db.get_connection() as conn:
        for name in ('unknown_extension',):
            assert conn.execute(f'SELECT evidence FROM {name}').fetchone()[0]=='preserve'
        assert conn.execute('SELECT count(*) FROM contacts').fetchone()[0]==2
        assert conn.execute('SELECT status FROM emails').fetchone()[0]=='replied'
        for name in ('email_research','email_status_events','suppression_events','user_profile'):
            assert conn.execute("SELECT 1 FROM sqlite_master WHERE name=?",(name,)).fetchone()

def test_legacy_preview_does_not_import_or_save(temp_db,tmp_path,monkeypatch):
    from app import create_app
    import candidate_profile
    monkeypatch.setattr(config,'BASE_DIR',tmp_path)
    (tmp_path/'context.txt').write_text('Facts to review',encoding='utf8')
    candidate_profile.save_settings({'full_name':'Candidate'},'Existing saved facts')
    client=create_app({'TESTING':True}).test_client()
    assert client.get('/api/settings/legacy-context').get_json()['candidate_context']=='Facts to review'
    assert candidate_profile.get_settings()['candidate_context']=='Existing saved facts'

def test_malformed_upload_does_not_leave_an_asset(temp_db):
    import io
    from app import create_app
    client=create_app({'TESTING':True}).test_client()
    token=client.get('/api/session').get_json()['csrf']
    response=client.post('/api/resumes',data={'name':'CV','file':(io.BytesIO(b'%PDF-1.4\nnot a pdf'),'cv.pdf')},headers={'X-CSRF-Token':token})
    assert response.status_code==400
    assert list(config.RESUME_DIR.iterdir())==[]
