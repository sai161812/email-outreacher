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
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id         INTEGER NOT NULL REFERENCES companies(id),
    contact_id         INTEGER NOT NULL REFERENCES contacts(id),
    resume_variant_id  INTEGER REFERENCES resume_variants(id),
    hook               TEXT,
    subject            TEXT,
    body               TEXT,
    status             TEXT NOT NULL DEFAULT 'pending_review',
        -- pending_review | approved | rejected | sent | replied | ghosted | bounced
    sent_at            TEXT,
    follow_up_due      TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now'))
);
"""


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)


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
