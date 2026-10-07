from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import jobs
import pytest
from errors import Conflict

def test_idempotent_enqueue_and_inputs(temp_db):
    a=jobs.enqueue("send",{},"same-key")
    assert jobs.enqueue("send",{},"same-key")["id"]==a["id"]
    with pytest.raises(Conflict):
        jobs.enqueue("send",{"dry_run":True},"same-key")

def test_concurrent_workers_claim_once(temp_db,monkeypatch):
    job=jobs.enqueue("send",{})
    dispatch=Mock(return_value={"summary":[]})
    monkeypatch.setattr(jobs,"_dispatch",dispatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _:jobs.process_next(),range(2)))
    assert dispatch.call_count==1
    assert jobs.get(job["id"])["status"]=="complete"

def test_failed_jobs_are_visible(temp_db,monkeypatch):
    job=jobs.enqueue("replies",{})
    monkeypatch.setattr(jobs,"_dispatch",Mock(side_effect=RuntimeError("private-secret")))
    jobs.process_next()
    result=jobs.get(job["id"])
    assert result["status"]=="failed"
    assert "private-secret" not in result["error"]

def test_preview_and_live_send_are_not_coalesced(temp_db):
    jobs.enqueue("send",{"dry_run":True},"preview-123")
    with pytest.raises(Conflict,match="different inputs"):
        jobs.enqueue("send",{},"live-send-123")

def test_restart_fails_running_job_without_redispatch(temp_db,monkeypatch):
    from db import get_connection
    job=jobs.enqueue("send",{})
    with get_connection() as conn:
        conn.execute("UPDATE jobs SET status='running' WHERE id=?",(job["id"],))
    dispatch=Mock()
    monkeypatch.setattr(jobs,"_dispatch",dispatch)
    jobs.recover()
    assert jobs.get(job["id"])["status"]=="failed"
    assert not jobs.process_next()
    dispatch.assert_not_called()
