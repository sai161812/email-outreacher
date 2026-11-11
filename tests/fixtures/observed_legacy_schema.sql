CREATE TABLE companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    domain      TEXT,
    job_url     TEXT,
    job_text    TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE contacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    name        TEXT,
    email       TEXT NOT NULL,
    title       TEXT,
    source      TEXT,          -- where you found this contact
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE resume_variants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    keywords    TEXT NOT NULL,  -- comma separated, used for matching
    file_path   TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
, resume_url TEXT);
CREATE TABLE emails (
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
, qc_warnings TEXT, message_id TEXT);
CREATE TABLE profile (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    full_name     TEXT NOT NULL,
    email         TEXT,
    phone         TEXT,
    linkedin_url  TEXT,
    github_url    TEXT,
    portfolio_url TEXT,
    updated_at    TEXT DEFAULT (datetime('now'))
    );
CREATE TABLE suppressions (
        email TEXT PRIMARY KEY,
        reason TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
CREATE TABLE email_research (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id    INTEGER NOT NULL UNIQUE,
    notes       TEXT,
    sources_json TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);
CREATE TABLE email_status_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id    INTEGER NOT NULL,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    note        TEXT,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);
CREATE TABLE suppression_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL,
    action      TEXT NOT NULL,
    reason      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE user_profile (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    full_name       TEXT NOT NULL,
    email           TEXT NOT NULL,
    title           TEXT,
    bio             TEXT,
    linkedin_url    TEXT,
    github_url      TEXT,
    portfolio_url   TEXT,
    custom_signature TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
