from repository import EmailRepository

def list_pending(limit=100, offset=0):
    return EmailRepository.get_pending_review(limit, offset)

def approve(email_id, expected_revision=None):
    return EmailRepository.approve(email_id, expected_revision)

def reject(email_id, expected_revision=None):
    from db import get_connection
    from repository import require_email, check_revision, timestamp, event
    from errors import Conflict
    with get_connection(immediate=True) as conn:
        row = require_email(conn,email_id)
        check_revision(row,expected_revision)
        if row["status"] not in {"pending_review","approved"} or row["sent_at"]:
            raise Conflict("Only an unsent review draft can be rejected")
        conn.execute("UPDATE emails SET status='rejected',approval_json=NULL,updated_at=? WHERE id=?", (timestamp(),email_id))
        event(conn,email_id,"rejected")

def edit(email_id, subject=None, body=None, hook=None, expected_revision=None, **kwargs):
    return EmailRepository.update_content(email_id,subject,body,hook,expected_revision,**kwargs)
