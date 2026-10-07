"""
Single SQLite file is the source of truth for the whole tool.
Every module reads/writes through here — that's what keeps this
mergeable into a bigger app later without a rewrite.
"""
import sqlite3
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    domain      TEXT,
    job_url     TEXT,
    job_text    TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    name        TEXT,
    email       TEXT NOT NULL,
    title       TEXT,
    source      TEXT,          -- where you found this contact
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resume_variants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    keywords    TEXT NOT NULL,  -- comma separated, used for matching
    file_path   TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS emails (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id            INTEGER NOT NULL REFERENCES companies(id),
    contact_id            INTEGER NOT NULL REFERENCES contacts(id),
    resume_variant_id     INTEGER REFERENCES resume_variants(id),
    follow_up_to_email_id INTEGER REFERENCES emails(id),
        -- set when this row is a follow-up to an earlier email, NULL otherwise
    hook                  TEXT,
    subject               TEXT,
    body                  TEXT,
    status                TEXT NOT NULL DEFAULT 'pending_review',
        -- pending_review | approved | rejected | sent | replied | ghosted | bounced
    sent_at               TEXT,
    follow_up_due         TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS suppressions (
    email TEXT PRIMARY KEY,
    reason TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


SCHEMA_VERSION = 1
STATUSES = ("pending_review", "approved", "sending", "sent", "replied", "ghosted",
            "bounced", "interview_scheduled", "interview_completed", "offer", "no_offer",
            "rejected", "failed", "uncertain", "canceled")

def _execute_script(conn, script):
    statement = ""
    for line in script.splitlines():
        statement += line + "\n"
        if sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        conn.execute(statement)

def backup_database(destination=None):
    from pathlib import Path
    import uuid
    target = Path(destination) if destination else config.DB_PATH.parent / "backups" / f"outreach-{uuid.uuid4().hex}.sqlite"
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.DB_PATH) as source, sqlite3.connect(target) as copy:
        source.backup(copy)
    return target

def init_db():
    """Upgrade legacy data without dropping rows; preserve a pre-upgrade backup."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.DB_PATH, timeout=30) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError("Database is newer than this application")
        if version == SCHEMA_VERSION:
            return
        if "emails" in tables:
            backup_database()
        try:
            conn.execute("BEGIN IMMEDIATE")
            _execute_script(conn, SCHEMA)
            conn.execute("""CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK(id=1), full_name TEXT NOT NULL,
                email TEXT, phone TEXT, linkedin_url TEXT, github_url TEXT,
                portfolio_url TEXT, updated_at TEXT DEFAULT (datetime('now')))""")
            additions = {
                "companies": {"archived": "INTEGER NOT NULL DEFAULT 0"},
                "contacts": {"archived": "INTEGER NOT NULL DEFAULT 0"},
                "resume_variants": {"resume_url": "TEXT", "archived": "INTEGER NOT NULL DEFAULT 0"},
                "emails": {
                    "follow_up_to_email_id": "INTEGER REFERENCES emails(id)",
                    "qc_warnings": "TEXT", "message_id": "TEXT",
                    "revision": "INTEGER NOT NULL DEFAULT 1",
                    "approval_json": "TEXT", "research_notes": "TEXT",
                    "grounding_json": "TEXT", "generation_error": "TEXT",
                    "thread_root_id": "INTEGER REFERENCES emails(id)"
                }
            }
            for table, columns in additions.items():
                existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                for name, definition in columns.items():
                    if name not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
            _execute_script(conn, """
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, email_id INTEGER REFERENCES emails(id), kind TEXT NOT NULL,
 detail TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS send_attempts (
 id INTEGER PRIMARY KEY, email_id INTEGER NOT NULL REFERENCES emails(id),
 company_id INTEGER NOT NULL REFERENCES companies(id), recipient TEXT NOT NULL,
 message_id TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error_code TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
 request_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'pending',
 result TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reply_messages (
 uidvalidity TEXT NOT NULL, uid TEXT NOT NULL, message_id TEXT, processed_at TEXT NOT NULL,
 PRIMARY KEY(uidvalidity,uid)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS migration_reports (kind TEXT NOT NULL, count INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS contacts_company_idx ON contacts(company_id);
CREATE INDEX IF NOT EXISTS contacts_email_idx ON contacts(lower(trim(email)));
CREATE INDEX IF NOT EXISTS company_identity_idx ON companies(lower(trim(name)),lower(trim(domain)));
CREATE INDEX IF NOT EXISTS emails_status_idx ON emails(status,created_at);
CREATE INDEX IF NOT EXISTS emails_contact_idx ON emails(contact_id);
CREATE INDEX IF NOT EXISTS emails_thread_idx ON emails(thread_root_id);
CREATE INDEX IF NOT EXISTS emails_parent_idx ON emails(follow_up_to_email_id);
CREATE INDEX IF NOT EXISTS emails_sent_idx ON emails(sent_at);
CREATE INDEX IF NOT EXISTS attempts_quota_idx ON send_attempts(state,created_at,company_id);
CREATE INDEX IF NOT EXISTS events_email_idx ON events(email_id,kind);
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status,created_at);
""")
            duplicates = conn.execute("""SELECT COUNT(*) FROM (
                SELECT company_id,lower(trim(email)) FROM contacts
                GROUP BY company_id,lower(trim(email)) HAVING COUNT(*)>1)""").fetchone()[0]
            mismatches = conn.execute("""SELECT COUNT(*) FROM emails e JOIN contacts c
                ON e.contact_id=c.id WHERE e.company_id<>c.company_id""").fetchone()[0]
            conn.executemany("INSERT INTO migration_reports VALUES (?,?)",
                             [("legacy_duplicate_contact_groups", duplicates),("legacy_relationship_mismatches",mismatches)])
            # Old approvals carry no review snapshot and cannot authorize new delivery.
            conn.execute("UPDATE emails SET status=CASE WHEN sent_at IS NULL THEN 'pending_review' ELSE 'sent' END WHERE status='approved'")
            for table in ("contacts", "companies"):
                condition = ("c.company_id=NEW.company_id AND lower(trim(c.email))=lower(trim(NEW.email))"
                             if table == "contacts" else
                             "lower(trim(c.name))=lower(trim(NEW.name)) OR (coalesce(trim(NEW.domain),'')<>'' AND lower(trim(c.domain))=lower(trim(NEW.domain)))")
                for operation in ("INSERT", "UPDATE"):
                    exclude = "AND c.id<>NEW.id" if operation == "UPDATE" else ""
                    conn.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_identity_{operation.lower()}
                        BEFORE {operation} ON {table}
                        WHEN NEW.archived=0 AND EXISTS(SELECT 1 FROM {table} c WHERE c.archived=0 AND ({condition}) {exclude})
                        BEGIN SELECT RAISE(ABORT,'Duplicate identity'); END""")
            valid = ",".join(f"'{s}'" for s in STATUSES)
            for operation in ("INSERT", "UPDATE"):
                conn.execute(f"""CREATE TRIGGER IF NOT EXISTS emails_valid_{operation.lower()}
                    BEFORE {operation} ON emails
                    WHEN NEW.status NOT IN ({valid}) OR NOT EXISTS (
                    SELECT 1 FROM contacts WHERE id=NEW.contact_id AND company_id=NEW.company_id)
                    BEGIN SELECT RAISE(ABORT,'Invalid email relationship or status'); END""")
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

@contextmanager
def get_connection(immediate=False):
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
