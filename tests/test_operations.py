import sqlite3
from pathlib import Path
import importlib.util
import config
import contacts
import db
from manage import check_database

def test_database_check_and_live_wal_backup(contact,tmp_path):
    with db.get_connection() as conn:
        conn.execute("INSERT INTO companies(name) VALUES ('Committed WAL')")
    assert check_database()["integrity"]==["ok"]
    backup=db.backup_database(tmp_path/"safe.sqlite")
    with sqlite3.connect(backup) as conn:
        assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]==2
        assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"

def test_example_csv_imports_cleanly(temp_db):
    with (config.BASE_DIR/"companies_template.csv").open(encoding="utf8",newline="") as file:
        report=contacts.import_stream(file)
    assert report["contacts_created"]==3
    assert report["errors"]==[]

def test_release_path_policy():
    path=Path(__file__).resolve().parents[1]/"scripts"/"release.py"
    spec=importlib.util.spec_from_file_location("source_release",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for name in [".env",".env.production","outreach.db-wal","resumes/private.pdf","context.txt","rewrite.py"]:
        assert module.prohibited(name)
    for name in [".env.example","candidate_context.example.txt","tests/test_sender.py","static/app.js"]:
        assert not module.prohibited(name)

def test_large_contact_page_uses_one_join_and_company_index(contact,monkeypatch):
    from contextlib import contextmanager
    import repository
    company,_=contact
    with db.get_connection() as conn:
        conn.executemany("INSERT INTO contacts(company_id,email) VALUES (?,?)",[(company,f"bulk{i:04d}@example.test") for i in range(1000)])
    statements=[]
    original=repository.get_connection
    @contextmanager
    def traced(*args,**kwargs):
        with original(*args,**kwargs) as conn:
            conn.set_trace_callback(statements.append)
            yield conn
    monkeypatch.setattr(repository,"get_connection",traced)
    page=contacts.list_contacts(company,limit=25,offset=100)
    assert len(page)==25 and page[0]["email"]=="bulk0100@example.test"
    queries=[query for query in statements if query.startswith("SELECT")]
    assert len(queries)==1
    with db.get_connection() as conn:
        plan=" ".join(str(tuple(row)) for row in conn.execute("EXPLAIN QUERY PLAN "+queries[0]))
    assert "contacts_company_idx" in plan
