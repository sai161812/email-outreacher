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

def test_interrupted_migration_rolls_back_and_backup_restores(tmp_path,monkeypatch):
    import pytest
    target=tmp_path/"legacy.db"
    monkeypatch.setattr(config,"DB_PATH",target)
    with sqlite3.connect(target) as conn:
        conn.executescript(db.SCHEMA)
        conn.execute("INSERT INTO companies(name) VALUES ('Preserved')")
    original=db._execute_script
    calls=0
    def broken(conn,script):
        nonlocal calls
        calls+=1
        original(conn,script)
        if calls==2: raise RuntimeError("Simulated interruption")
    monkeypatch.setattr(db,"_execute_script",broken)
    with pytest.raises(RuntimeError): db.init_db()
    with sqlite3.connect(target) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0]==0
        assert "revision" not in [r[1] for r in conn.execute("PRAGMA table_info(emails)")]
    backup=next((tmp_path/"backups").glob("*.sqlite"))
    with sqlite3.connect(backup) as source,sqlite3.connect(tmp_path/"restored.db") as restored:
        source.backup(restored)
        assert restored.execute("SELECT name FROM companies").fetchone()[0]=="Preserved"
        assert restored.execute("PRAGMA integrity_check").fetchone()[0]=="ok"

def test_upgrade_preserves_reviewed_v1_approval(contact):
    import reviewer
    from repository import EmailRepository
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    reviewer.approve(eid)
    with db.get_connection() as conn: conn.execute("PRAGMA user_version=1")
    db.init_db()
    assert EmailRepository.get_by_id(eid)["approval_json"]
    assert EmailRepository.get_by_id(eid)["status"]=="approved"

def test_legacy_thread_roots_backfilled(tmp_path,monkeypatch):
    target=tmp_path/"legacy.db"
    monkeypatch.setattr(config,"DB_PATH",target)
    with sqlite3.connect(target) as conn:
        conn.executescript(db.SCHEMA)
        conn.execute("INSERT INTO companies(id,name) VALUES (1,'Legacy')")
        conn.execute("INSERT INTO contacts(id,company_id,email) VALUES (1,1,'legacy@example.test')")
        for eid,parent in [(1,None),(2,1),(3,2)]:
            conn.execute("INSERT INTO emails(id,company_id,contact_id,follow_up_to_email_id,status,sent_at) VALUES (?,1,1,?,'sent','2026-01-01T00:00:00+00:00')",(eid,parent))
    db.init_db()
    with db.get_connection() as conn:
        assert [r[0] for r in conn.execute("SELECT thread_root_id FROM emails WHERE id>1 ORDER BY id")]==[1,1]
        assert conn.execute("PRAGMA foreign_key_check").fetchall()==[]

def test_direct_duplicate_drafts_rejected(contact):
    import pytest
    from errors import Conflict
    from repository import EmailRepository
    company,person=contact
    EmailRepository.create(company,person,None,"H","S","B",None)
    with pytest.raises(Conflict):
        EmailRepository.create(company,person,None,"H","S","B",None)

def test_backup_refuses_overwrite(temp_db):
    import pytest
    with pytest.raises(ValueError,match="new file"): db.backup_database(temp_db)

def test_legacy_mismatch_can_be_rejected_without_losing_history(tmp_path,monkeypatch):
    from repository import EmailRepository
    target=tmp_path/"legacy.db"
    monkeypatch.setattr(config,"DB_PATH",target)
    with sqlite3.connect(target) as conn:
        conn.executescript(db.SCHEMA)
        conn.executemany("INSERT INTO companies(id,name) VALUES (?,?)",[(1,"First"),(2,"Second")])
        conn.execute("INSERT INTO contacts(id,company_id,email) VALUES (1,1,'legacy@example.test')")
        conn.execute("INSERT INTO emails(id,company_id,contact_id,subject,body) VALUES (1,2,1,'S','Preserved body')")
    db.init_db()
    EmailRepository.update_status(1,"rejected")
    assert EmailRepository.get_by_id(1)["body"]=="Preserved body"
