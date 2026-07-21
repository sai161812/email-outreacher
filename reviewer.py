"""
Nothing sends without passing through here. AI-researched hooks can be
wrong or stale, so every draft is a human checkpoint before it queues.
"""
from datetime import datetime, timezone
from db import get_connection


def list_pending():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.*, c.name as company_name, ct.email as contact_email, "
            "ct.name as contact_name "
            "FROM emails e "
            "JOIN companies c ON e.company_id = c.id "
            "JOIN contacts ct ON e.contact_id = ct.id "
            "WHERE e.status = 'pending_review' "
            "ORDER BY e.created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_email(email_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
        return dict(row) if row else None


def approve(email_id):
    _set_status(email_id, "approved")


def reject(email_id):
    _set_status(email_id, "rejected")


def edit(email_id, subject=None, body=None, hook=None):
    fields, values = [], []
    if subject is not None:
        fields.append("subject = ?"); values.append(subject)
    if body is not None:
        fields.append("body = ?"); values.append(body)
    if hook is not None:
        fields.append("hook = ?"); values.append(hook)
    if not fields:
        return
    fields.append("updated_at = ?"); values.append(datetime.now(timezone.utc).isoformat())
    values.append(email_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE emails SET {', '.join(fields)} WHERE id = ?", values)


def _set_status(email_id, status):
    with get_connection() as conn:
        conn.execute(
            "UPDATE emails SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(timezone.utc).isoformat(), email_id),
        )
