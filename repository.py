from datetime import datetime, timezone
from db import get_connection

class CompanyRepository:
    @staticmethod
    def get_all():
        with get_connection() as conn:
            return conn.execute("""
                SELECT c.*, 
                       (SELECT COUNT(*) FROM contacts ct WHERE ct.company_id = c.id) as contact_count
                FROM companies c 
                ORDER BY c.name
            """).fetchall()

    @staticmethod
    def get_by_id(company_id):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()

    @staticmethod
    def get_by_name(name):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM companies WHERE name = ?", (name,)).fetchone()

    @staticmethod
    def create(name, domain, job_url, job_text, notes):
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO companies (name, domain, job_url, job_text, notes) VALUES (?, ?, ?, ?, ?)",
                (name, domain, job_url, job_text, notes)
            )
            return cursor.lastrowid

class ContactRepository:
    @staticmethod
    def get_all_by_company(company_id=None):
        query = """
            SELECT ct.*, c.name as company_name 
            FROM contacts ct 
            JOIN companies c ON ct.company_id = c.id
        """
        params = []
        if company_id:
            query += " WHERE ct.company_id = ?"
            params.append(company_id)
        query += " ORDER BY c.name, ct.email"
        
        with get_connection() as conn:
            return conn.execute(query, params).fetchall()

    @staticmethod
    def get_by_id(contact_id):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()

    @staticmethod
    def get_by_email_and_company(email, company_id):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM contacts WHERE email = ? AND company_id = ?",
                (email, company_id)
            ).fetchone()

    @staticmethod
    def create(company_id, email, name, title, source):
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO contacts (company_id, email, name, title, source) VALUES (?, ?, ?, ?, ?)",
                (company_id, email, name, title, source)
            )
            return cursor.lastrowid

class ResumeRepository:
    @staticmethod
    def get_all():
        with get_connection() as conn:
            return conn.execute("SELECT * FROM resume_variants ORDER BY id").fetchall()

    @staticmethod
    def create(name, keywords, file_path, resume_url=None):
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO resume_variants (name, keywords, file_path, resume_url) VALUES (?, ?, ?, ?)",
                (name, keywords, file_path, resume_url)
            )
            return cursor.lastrowid

class SuppressionRepository:
    @staticmethod
    def get_all():
        with get_connection() as conn:
            return conn.execute("SELECT * FROM suppressions ORDER BY created_at DESC").fetchall()

    @staticmethod
    def is_suppressed(email):
        with get_connection() as conn:
            row = conn.execute("SELECT 1 FROM suppressions WHERE email = ?", (email,)).fetchone()
            return bool(row)

    @staticmethod
    def add(email, reason):
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO suppressions (email, reason) VALUES (?, ?)",
                (email, reason)
            )

    @staticmethod
    def remove(email):
        with get_connection() as conn:
            conn.execute("DELETE FROM suppressions WHERE email = ?", (email,))

class EmailRepository:
    @staticmethod
    def get_by_id(email_id):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()

    @staticmethod
    def get_by_contact_id(contact_id):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM emails WHERE contact_id = ?", (contact_id,)).fetchall()

    @staticmethod
    def create(company_id, contact_id, resume_variant_id, hook, subject, body, qc_warnings, follow_up_to_email_id=None):
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO emails 
                   (company_id, contact_id, resume_variant_id, follow_up_to_email_id, hook, subject, body, qc_warnings) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (company_id, contact_id, resume_variant_id, follow_up_to_email_id, hook, subject, body, qc_warnings)
            )
            return cursor.lastrowid

    @staticmethod
    def update_sent(email_id, msg_id, subject):
        with get_connection() as conn:
            conn.execute(
                "UPDATE emails SET status = 'sent', sent_at = ?, updated_at = ?, message_id = ?, subject = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), msg_id, subject, email_id),
            )
            
    @staticmethod
    def update_status(email_id, status, set_updated_at=False, set_sent_at=False, sent_at_time=None):
        query = "UPDATE emails SET status = ?"
        params = [status]
        
        if set_updated_at:
            query += ", updated_at = ?"
            params.append(datetime.now(timezone.utc).isoformat())
            
        if set_sent_at:
            query += ", sent_at = ?"
            params.append(sent_at_time or datetime.now(timezone.utc).isoformat())
            
        query += " WHERE id = ?"
        params.append(email_id)
        
        with get_connection() as conn:
            conn.execute(query, params)
            
    @staticmethod
    def update_content(email_id, subject=None, body=None, hook=None):
        updates = []
        params = []
        if subject is not None:
            updates.append("subject = ?")
            params.append(subject)
        if body is not None:
            updates.append("body = ?")
            params.append(body)
        if hook is not None:
            updates.append("hook = ?")
            params.append(hook)
            
        if not updates:
            return
            
        updates.append("status = 'approved'")
        query = f"UPDATE emails SET {', '.join(updates)} WHERE id = ?"
        params.append(email_id)
        
        with get_connection() as conn:
            conn.execute(query, params)

    @staticmethod
    def get_pending_review():
        with get_connection() as conn:
            return conn.execute(
                """SELECT e.*, c.name as company_name, ct.email as contact_email 
                   FROM emails e 
                   JOIN companies c ON e.company_id = c.id 
                   JOIN contacts ct ON e.contact_id = ct.id 
                   WHERE e.status = 'pending_review' 
                   ORDER BY e.created_at ASC"""
            ).fetchall()

    @staticmethod
    def get_approved_queue():
        with get_connection() as conn:
            return conn.execute(
                """SELECT e.*, ct.email as contact_email, c.domain as company_domain, ct.source as contact_source
                   FROM emails e 
                   JOIN contacts ct ON e.contact_id = ct.id 
                   JOIN companies c ON e.company_id = c.id
                   WHERE e.status = 'approved' 
                   ORDER BY ct.source = 'referral' DESC, e.created_at ASC"""
            ).fetchall()

    @staticmethod
    def get_due_for_follow_up(cutoff_date_iso):
        with get_connection() as conn:
            return conn.execute(
                """SELECT e.*, c.name as company_name, ct.email as contact_email 
                   FROM emails e 
                   JOIN companies c ON e.company_id = c.id 
                   JOIN contacts ct ON e.contact_id = ct.id 
                   WHERE e.status = 'sent' AND date(e.sent_at) <= ? 
                   AND e.id NOT IN (SELECT follow_up_to_email_id FROM emails WHERE follow_up_to_email_id IS NOT NULL)""",
                (cutoff_date_iso,)
            ).fetchall()

    @staticmethod
    def get_sent_candidates_for_replies():
        with get_connection() as conn:
            return conn.execute(
                """SELECT e.id, e.message_id, c.email as contact_email 
                   FROM emails e 
                   JOIN contacts c ON e.contact_id = c.id 
                   WHERE e.status = 'sent'"""
            ).fetchall()

    @staticmethod
    def count_company_sends_since(company_id, since_iso):
        with get_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM emails WHERE company_id = ? AND status = 'sent' AND sent_at > ?",
                (company_id, since_iso)
            ).fetchone()[0]

    @staticmethod
    def count_sends_today():
        with get_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM emails WHERE status = 'sent' AND date(sent_at) = date('now')"
            ).fetchone()[0]

    @staticmethod
    def get_pipeline_summary():
        with get_connection() as conn:
            return conn.execute(
                "SELECT status, COUNT(*) as n FROM emails GROUP BY status"
            ).fetchall()

    @staticmethod
    def get_stats_data():
        with get_connection() as conn:
            variants = conn.execute("SELECT id, name FROM resume_variants ORDER BY id").fetchall()
            emails = conn.execute(
                """SELECT e.id, e.status, e.sent_at, e.resume_variant_id, rv.name as variant_name
                   FROM emails e
                   LEFT JOIN resume_variants rv ON e.resume_variant_id = rv.id
                   WHERE e.status IN ('sent','replied','ghosted','bounced','interview_scheduled','interview_completed','offer','no_offer')
                      OR (e.sent_at IS NOT NULL AND e.status NOT IN ('pending_review', 'approved', 'rejected'))"""
            ).fetchall()
            return variants, emails
            
    @staticmethod
    def get_all_tracked_emails():
        with get_connection() as conn:
            return conn.execute(
                """SELECT e.*, c.name as company_name, ct.email as contact_email 
                   FROM emails e 
                   JOIN companies c ON e.company_id = c.id 
                   JOIN contacts ct ON e.contact_id = ct.id 
                   WHERE e.status NOT IN ('pending_review') 
                   ORDER BY e.updated_at DESC"""
            ).fetchall()

class ProfileRepository:
    @staticmethod
    def get_profile():
        with get_connection() as conn:
            return conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
            
    @staticmethod
    def upsert_profile(full_name, email, phone, linkedin_url, github_url, portfolio_url):
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO profile (id, full_name, email, phone, linkedin_url, github_url, portfolio_url)
                   VALUES (1, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                   full_name=excluded.full_name,
                   email=excluded.email,
                   phone=excluded.phone,
                   linkedin_url=excluded.linkedin_url,
                   github_url=excluded.github_url,
                   portfolio_url=excluded.portfolio_url,
                   updated_at=datetime('now')""",
                (full_name, email, phone, linkedin_url, github_url, portfolio_url)
            )
