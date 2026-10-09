from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from unittest.mock import Mock
import pytest
import config
import delivery
import sender
import reviewer
from db import get_connection
from repository import ContactRepository,EmailRepository,SuppressionRepository
from test_sender import mail,draft

def second(contact):
    company,_=contact
    person=ContactRepository.create(company,"second@example.test")
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    reviewer.approve(eid)
    return eid

def test_preview_reserves_projected_batch_capacity(contact,draft,monkeypatch):
    reviewer.approve(draft);second(contact)
    monkeypatch.setattr(sender,"is_in_send_window",lambda:True)
    monkeypatch.setattr(config,"DAILY_SEND_CAP",1)
    result=sender.run_send_batch(dry_run=True)
    assert [r["status"] for r in result]==["dry_run","deferred"]
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM send_attempts").fetchone()[0]==0
    assert EmailRepository.get_by_id(draft)["status"]=="approved"

def test_preview_skips_a_message_sent_after_the_queue_was_loaded(draft,mail,monkeypatch):
    reviewer.approve(draft)
    stale_queue=sender.get_approved_queue()
    assert sender.run_send_batch()[0]["status"]=="sent"
    monkeypatch.setattr(sender,"get_approved_queue",lambda:stale_queue)
    assert sender.run_send_batch(dry_run=True)[0]["status"]=="skipped"
    assert mail.sendmail.call_count==1

def test_all_candidates_reported_when_transport_fails(contact,draft,mail):
    reviewer.approve(draft);second(contact)
    mail.starttls.side_effect=ConnectionError("private")
    result=sender.run_send_batch()
    assert [r["status"] for r in result]==["failed","deferred"]
    mail.quit.assert_called_once()
    assert mail.sendmail.call_count==0

def test_ambiguous_connection_closed(draft,mail):
    reviewer.approve(draft)
    mail.sendmail.side_effect=TimeoutError()
    sender.run_send_batch()
    mail.quit.assert_called_once()

def test_cleanup_failure_does_not_hide_success(draft,mail):
    reviewer.approve(draft)
    mail.quit.side_effect=OSError()
    mail.close.side_effect=OSError()
    assert sender.run_send_batch()[0]["status"]=="sent"

def test_window_closes_during_batch(contact,draft,mail,monkeypatch):
    reviewer.approve(draft);other=second(contact)
    monkeypatch.setattr(sender,"is_in_send_window",lambda:mail.sendmail.call_count==0)
    result=sender.run_send_batch()
    assert [r["status"] for r in result]==["sent","deferred"]
    assert EmailRepository.get_by_id(other)["status"]=="approved"

def test_suppressed_candidate_does_not_consume_capacity(contact,draft,mail,monkeypatch):
    reviewer.approve(draft);second(contact)
    queue=sender.get_approved_queue()
    SuppressionRepository.add("person@example.test","manual")
    monkeypatch.setattr(sender,"get_approved_queue",lambda:queue)
    monkeypatch.setattr(config,"MAX_PER_COMPANY_PER_WEEK",1)
    assert [r["status"] for r in sender.run_send_batch()]==["skipped","sent"]
    assert mail.sendmail.call_count==1

@pytest.mark.parametrize("zone,instant,stamps",[
    ("Asia/Kolkata","2026-10-07T19:00:00+00:00",["2026-10-07T18:29:59+00:00","2026-10-07T18:30:00+00:00","2026-10-08T18:29:59+00:00","2026-10-08T18:30:00+00:00"]),
    ("America/New_York","2026-11-01T12:00:00+00:00",["2026-11-01T03:59:59+00:00","2026-11-01T04:00:00+00:00","2026-11-02T04:59:59+00:00","2026-11-02T05:00:00+00:00"]),
])
def test_local_midnight_and_dst_counts(contact,monkeypatch,zone,instant,stamps):
    monkeypatch.setattr(config,"TIMEZONE",ZoneInfo(zone))
    monkeypatch.setattr(config,"now",lambda:datetime.fromisoformat(instant))
    company,_=contact
    for index,stamp in enumerate(stamps):
        person=ContactRepository.create(company,f"time{index}@example.test")
        eid=EmailRepository.create(company,person,None,"H","S","B",None)
        with get_connection() as conn:
            conn.execute("UPDATE emails SET sent_at=?,status='replied' WHERE id=?",(stamp,eid))
    assert EmailRepository.count_sends_today()==2
    monkeypatch.setattr(config,"DAILY_SEND_CAP",2)
    with get_connection() as conn,pytest.raises(ValueError,match="Daily"):
        delivery._quota(conn,company)

def test_sqlite_legacy_timestamp_counts(contact,monkeypatch):
    monkeypatch.setattr(config,"TIMEZONE",timezone.utc)
    monkeypatch.setattr(config,"now",lambda:datetime(2026,10,7,12,tzinfo=timezone.utc))
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    with get_connection() as conn:
        conn.execute("UPDATE emails SET sent_at='2026-10-07 09:00:00',status='sent' WHERE id=?",(eid,))
    assert EmailRepository.count_sends_today()==1
