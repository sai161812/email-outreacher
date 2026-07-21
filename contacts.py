"""
CRUD for companies and contacts. Deliberately simple — no ORM,
just SQL, because this doesn't need more than that.
"""
from db import get_connection


def add_company(name, domain=None, job_url=None, job_text=None, notes=None):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO companies (name, domain, job_url, job_text, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, domain, job_url, job_text, notes),
        )
        return cur.lastrowid


def add_contact(company_id, email, name=None, title=None, source=None):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO contacts (company_id, email, name, title, source) "
            "VALUES (?, ?, ?, ?, ?)",
            (company_id, email, name, title, source),
        )
        return cur.lastrowid


def get_company(company_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        return dict(row) if row else None


def get_contact(contact_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        return dict(row) if row else None


def list_companies():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT c.*, "
            "(SELECT COUNT(*) FROM contacts WHERE company_id = c.id) as contact_count "
            "FROM companies c ORDER BY c.created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def list_contacts(company_id=None):
    with get_connection() as conn:
        if company_id:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE company_id = ? ORDER BY created_at DESC",
                (company_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT contacts.*, companies.name as company_name "
                "FROM contacts JOIN companies ON contacts.company_id = companies.id "
                "ORDER BY contacts.created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def find_contact_without_email(company_id):
    """Contacts for a company that don't yet have a drafted/sent email."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE company_id = ? AND id NOT IN "
            "(SELECT contact_id FROM emails)",
            (company_id,),
        ).fetchall()
        return [dict(r) for r in rows]
