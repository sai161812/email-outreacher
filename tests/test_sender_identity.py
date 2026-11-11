import json
import pytest
import config,db,delivery,reviewer,replies
from repository import EmailRepository
from errors import Conflict
from test_sender import draft,mail


def test_account_change_blocks_send_but_password_change_does_not(draft,mail,monkeypatch):
    reviewer.approve(draft)
    monkeypatch.setattr(config,'GMAIL_ADDRESS','another@example.test')
    with pytest.raises(Conflict): delivery.claim(draft)
    monkeypatch.setattr(config,'GMAIL_ADDRESS','owner@example.test')
    monkeypatch.setattr(config,'GMAIL_APP_PASSWORD','replacement-secret')
    claim=delivery.claim(draft)
    with db.get_connection() as conn:
        assert conn.execute('SELECT sender FROM send_attempts').fetchone()[0]=='owner@example.test'
    monkeypatch.setattr(config,'GMAIL_ADDRESS','another@example.test')
    with pytest.raises(Conflict): replies.check_replies()
    assert claim


def test_schema2_approval_without_sender_requires_review(draft):
    reviewer.approve(draft)
    with db.get_connection() as conn:
        approval=json.loads(conn.execute('SELECT approval_json FROM emails').fetchone()[0])
        approval.pop('sender')
        conn.execute('UPDATE emails SET approval_json=?',(json.dumps(approval),))
        conn.execute('PRAGMA user_version=2')
    db.init_db()
    row=EmailRepository.get_by_id(draft)
    assert row['status']=='pending_review' and row['approval_json'] is None
