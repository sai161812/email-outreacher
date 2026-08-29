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

CREATE TABLE IF NOT EXISTS profile (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT,
    email         TEXT,
    phone         TEXT,
    linkedin_url  TEXT,
    github_url    TEXT,
    portfolio_url TEXT
);
"""

# Columns added after the original release. Applied with ALTER TABLE so
# existing databases (created before this column existed) get upgraded
# in place instead of breaking.
MIGRATIONS = [
    "ALTER TABLE emails ADD COLUMN follow_up_to_email_id INTEGER REFERENCES emails(id)",
]


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        for migration in MIGRATIONS:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError as e:
                # "duplicate column name" means this migration already ran
                # on this DB (e.g. it was created fresh with the column
                # already in SCHEMA) — safe to ignore.
                if "duplicate column" not in str(e):
                    raise


@contextmanager
def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()