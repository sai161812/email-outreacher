"""
You said you'll read replies yourself — this module just gives you a
place to record what happened, and surfaces what's due for follow-up.
"""
from datetime import datetime, timedelta, date
import config
from db import get_connection


def mark_replied(email_id):
    _set_status(email_id, "replied")


def mark_ghosted(email_id):
    _set_status(email_id, "ghosted")


def mark_bounced(email_id):
    _set_status(email_id, "bounced")


def _set_status(email_id, status):
    with get_connection() as conn:
        conn.execute(
            "UPDATE emails SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), email_id),
        )


def due_for_follow_up():
    """Sent emails with no reply after FOLLOW_UP_AFTER_DAYS."""
    cutoff = (date.today() - timedelta(days=config.FOLLOW_UP_AFTER_DAYS)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.*, c.name as company_name, ct.email as contact_email "
            "FROM emails e "
            "JOIN companies c ON e.company_id = c.id "
            "JOIN contacts ct ON e.contact_id = ct.id "
            "WHERE e.status = 'sent' AND date(e.sent_at) <= ?",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def pipeline_summary():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as n FROM emails GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}
