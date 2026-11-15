import hashlib,json,sqlite3
from contextlib import closing
import pytest
import config
from conftest import pdf_bytes
from operations import backup_bundle,restore_bundle
import resume

@pytest.mark.parametrize('damage',['omitted','unknown','duplicate','checksum','database','foreign_key'])
def test_restore_rejects_incomplete_bundle_before_outputs(contact,tmp_path,damage):
    path=config.RESUME_DIR/'cv.pdf';path.write_bytes(pdf_bytes())
    resume.add_resume_variant('CV','python',str(path))
    bundle=backup_bundle(tmp_path/'bundle')
    manifest=json.loads((bundle/'manifest.json').read_text())
    if damage=='omitted': manifest['assets']=[]
    elif damage=='unknown':
        manifest['assets'][0].update(id=999,file='resume-999.pdf')
        (bundle/'resume-999.pdf').write_bytes(path.read_bytes())
    elif damage=='duplicate': manifest['assets']*=2
    elif damage=='checksum': manifest['assets'][0]['sha256']='bad'
    elif damage=='database':
        (bundle/'database.sqlite').write_bytes(b'invalid')
        manifest['database_sha256']=hashlib.sha256(b'invalid').hexdigest()
    else:
        with closing(sqlite3.connect(bundle/'database.sqlite')) as conn,conn: conn.execute("INSERT INTO contacts(company_id,email) VALUES (999,'fake@example.test')")
        manifest['database_sha256']=hashlib.sha256((bundle/'database.sqlite').read_bytes()).hexdigest()
    (bundle/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError): restore_bundle(bundle,tmp_path/'restored.db',tmp_path/'assets')
    assert not (tmp_path/'restored.db').exists() and not (tmp_path/'assets').exists()

