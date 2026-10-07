import sqlite3
import db
import config

def test_init_is_idempotent(temp_db):
    with db.get_connection() as conn:
        conn.execute("INSERT INTO companies(name) VALUES ('Keep me')")
    db.init_db()
    with db.get_connection() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0]==db.SCHEMA_VERSION
        assert conn.execute("SELECT name FROM companies").fetchone()[0]=="Keep me"
        assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall()==[]

def test_legacy_upgrade_backs_up_and_preserves(tmp_path,monkeypatch):
    target=tmp_path/"legacy.db"
    monkeypatch.setattr(config,"DB_PATH",target)
    with sqlite3.connect(target) as conn:
        conn.executescript(db.SCHEMA)
        conn.execute("INSERT INTO companies(id,name) VALUES (1,'Legacy')")
        conn.execute("INSERT INTO contacts(id,company_id,email) VALUES (1,1,'legacy@example.test')")
        conn.execute("INSERT INTO emails(company_id,contact_id,subject,body,status) VALUES (1,1,'S','B','approved')")
    db.init_db()
    assert list((tmp_path/"backups").glob("*.sqlite"))
    with db.get_connection() as conn:
        row=conn.execute("SELECT * FROM emails").fetchone()
        assert row["subject"]=="S" and row["status"]=="pending_review"
        assert conn.execute("PRAGMA foreign_key_check").fetchall()==[]

def test_relationship_guard(contact):
    from repository import CompanyRepository,EmailRepository
    from errors import Conflict
    import pytest
    _,person=contact
    other=CompanyRepository.create("Other")
    with pytest.raises(Conflict):
        EmailRepository.create(other,person,None,"H","S","B",None)
