from threading import Event,Thread
import time
import jobs
from app import create_app
from test_api import post

def test_recover_completed_job_by_key_without_redispatch(temp_db,monkeypatch):
    key='recover-request-123'
    job=jobs.enqueue('replies',{},key)
    monkeypatch.setattr(jobs,'_dispatch',lambda *a:{'matches':[]})
    jobs.process_next()
    client=create_app({'TESTING':True}).test_client()
    found=client.get('/api/jobs/by-key/'+key)
    assert found.get_json()['id']==job['id'] and found.get_json()['status']=='complete'
    assert jobs.enqueue('replies',{},key)['id']==job['id']
    assert len(jobs.list_jobs())==1

def test_heartbeat_advances_during_blocked_provider(temp_db,monkeypatch):
    from db import get_connection
    release=Event();entered=Event()
    def provider(*args):
        entered.set();release.wait(10);return {'matches':[]}
    monkeypatch.setattr(jobs,'_dispatch',provider)
    job=jobs.enqueue('replies',{})
    thread=Thread(target=jobs.process_next);thread.start()
    try:
        assert entered.wait(3)
        before=jobs.health()['last_seen']
        time.sleep(2.2)
        current=jobs.health()
        assert current['state']=='busy' and current['last_seen']!=before
        assert current['active_job']['id']==job['id']
        assert current['last_progress']==jobs.get(job['id'])['updated_at']
    finally: release.set();thread.join(5)
