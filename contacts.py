"""
CRUD for companies and contacts. Deliberately simple — no ORM,
just SQL, because this doesn't need more than that.
"""
import csv

from db import get_connection
import validate

CSV_REQUIRED_COLUMNS = ["company_name", "contact_email"]
CSV_OPTIONAL_COLUMNS = [
    "domain", "job_url", "notes",
    "contact_name", "contact_title", "contact_source",
]


def add_company(name, domain=None, job_url=None, job_text=None, notes=None):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO companies (name, domain, job_url, job_text, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, domain, job_url, job_text, notes),
        )
        return cur.lastrowid


def add_contact(company_id, email, name=None, title=None, source=None):
    if not validate.is_valid_syntax(email):
        raise ValueError(f"Invalid email address: {email}")

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO contacts (company_id, email, name, title, source) "
            "VALUES (?, ?, ?, ?, ?)",
            (company_id, email.strip(), name, title, source),
        )
        return cur.lastrowid


import re

def normalize_company_name(name):
    if not name:
        return ""
    n = re.sub(r'\s+', ' ', name.strip())
    return n.rstrip('.')

def find_company_by_name(name, domain=None):
    """Used by CSV import to avoid creating duplicate company rows when
    the same company appears on multiple CSV rows (multiple contacts)."""
    with get_connection() as conn:
        if domain:
            row = conn.execute(
                "SELECT * FROM companies WHERE domain = ? COLLATE NOCASE", (domain.strip(),)
            ).fetchone()
            if row:
                return dict(row)

        norm_name = normalize_company_name(name)
        rows = conn.execute("SELECT * FROM companies").fetchall()
        for r in rows:
            if normalize_company_name(r["name"]).lower() == norm_name.lower():
                return dict(r)

        return None


def import_csv(file_path):
    """
    Bulk-add companies + contacts from a CSV file. You still have to
    source each contact yourself — this only removes the one-command-
    per-field typing, not the research step.

    Required columns: company_name, contact_email
    Optional columns: domain, job_url, notes, contact_name, contact_title,
    contact_source

    One row per contact. If the same company_name appears on multiple
    rows, only one company record is created and each row adds another
    contact under it.

    Returns a summary dict: {"companies_created": int, "contacts_created": int,
    "errors": [list of (row_number, reason)]}
    """
    summary = {"companies_created": 0, "contacts_created": 0, "errors": []}
    company_cache = {}  # name.lower() -> company_id, scoped to this import run

    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        missing = [c for c in CSV_REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"CSV is missing required column(s): {', '.join(missing)}. "
                f"Required: {', '.join(CSV_REQUIRED_COLUMNS)}"
            )

        for i, row in enumerate(reader, start=2):  # row 1 is the header
            name = (row.get("company_name") or "").strip()
            email = (row.get("contact_email") or "").strip()

            if not name or not email:
                summary["errors"].append((i, "missing company_name or contact_email"))
                continue

            if not validate.is_valid_syntax(email):
                summary["errors"].append((i, f"Invalid email format: {email}"))
                continue

            domain = (row.get("domain") or "").strip()
            cache_key = (normalize_company_name(name).lower(), domain.lower() if domain else "")
            if cache_key in company_cache:
                company_id = company_cache[cache_key]
            else:
                existing = find_company_by_name(name, domain)
                if existing:
                    company_id = existing["id"]
                else:
                    company_id = add_company(
                        name=normalize_company_name(name),
                        domain=domain or None,
                        job_url=(row.get("job_url") or "").strip() or None,
                        notes=(row.get("notes") or "").strip() or None,
                    )
                    summary["companies_created"] += 1
                company_cache[cache_key] = company_id

            add_contact(
                company_id,
                email,
                name=(row.get("contact_name") or "").strip() or None,
                title=(row.get("contact_title") or "").strip() or None,
                source=(row.get("contact_source") or "").strip() or None,
            )
            summary["contacts_created"] += 1

    return summary


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

def get_emails_for_contact(contact_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM emails WHERE contact_id = ? ORDER BY created_at DESC",
            (contact_id,),
        ).fetchall()
        return [dict(r) for r in rows]