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
