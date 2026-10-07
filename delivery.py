"""Atomic claims and conservative delivery recovery; no network inside transactions."""
import json
from datetime import timedelta, timezone
from email.utils import make_msgid
import config
import qc
import followups
from db import get_connection
from errors import Conflict
from repository import require_email, snapshot, timestamp, event, one

def _quota(conn, company_id, exclude=None):
    local = config.now().astimezone(config.TIMEZONE)
    start = local.replace(hour=0,minute=0,second=0,microsecond=0)
    end = start + timedelta(days=1)
    accepted_today = conn.execute("SELECT COUNT(*) FROM emails WHERE sent_at>=? AND sent_at<?",
        (start.astimezone(timezone.utc).isoformat(),end.astimezone(timezone.utc).isoformat())).fetchone()[0]
    accepted_company = conn.execute("SELECT COUNT(*) FROM emails WHERE company_id=? AND sent_at>?",
        (company_id,(config.now()-timedelta(days=7)).isoformat())).fetchone()[0]
    reserved = conn.execute("""SELECT a.company_id FROM send_attempts a JOIN emails e ON e.id=a.email_id
        WHERE a.state IN ('reserved','submitting','uncertain') AND e.sent_at IS NULL AND (? IS NULL OR a.id<>?)""",(exclude,exclude)).fetchall()
    if accepted_today + len(reserved) >= config.DAILY_SEND_CAP:
        raise Conflict("Daily send limit reached")
    if accepted_company + sum(r["company_id"]==company_id for r in reserved) >= config.MAX_PER_COMPANY_PER_WEEK:
        raise Conflict("Company weekly send limit reached")

def _validate(conn,row):
    if qc.blockers(row["subject"],row["body"]):
        raise Conflict("Draft fails content checks")
    current = snapshot(conn,row)
    if not row["approval_json"] or current != json.loads(row["approval_json"]):
        raise Conflict("Approved content or attachment changed; review again")
    if conn.execute("SELECT 1 FROM suppressions WHERE lower(trim(email))=?", (current["recipient"],)).fetchone():
        raise Conflict("Recipient is suppressed")
    followups.check(conn,row,for_existing=True)
    # A duplicated legacy row must not submit a second initial outreach.
    if not row["follow_up_to_email_id"] and conn.execute("""SELECT 1 FROM emails e JOIN contacts c ON c.id=e.contact_id
        WHERE lower(trim(c.email))=? AND e.id<>? AND
        (e.sent_at IS NOT NULL OR e.status IN ('sending','uncertain')) LIMIT 1""",(current["recipient"],row["id"])).fetchone():
        raise Conflict("Recipient already has a submitted outreach")
    return current

def claim(eid):
    with get_connection(immediate=True) as conn:
        row = require_email(conn,eid)
        if row["status"] != "approved":
            return None
        approved = _validate(conn,row)
        _quota(conn,row["company_id"])
        message_id = make_msgid(domain="outreach.local")
        now = timestamp()
        attempt_id = conn.execute("""INSERT INTO send_attempts(email_id,company_id,recipient,message_id,state,created_at,updated_at)
            VALUES (?,?,?,?,'reserved',?,?)""",(eid,row["company_id"],approved["recipient"],message_id,now,now)).lastrowid
        conn.execute("UPDATE emails SET status='sending',message_id=?,updated_at=? WHERE id=?", (message_id,now,eid))
        event(conn,eid,"send_reserved",{"attempt_id":attempt_id})
        return {"attempt_id":attempt_id,"email_id":eid,"message_id":message_id,"snapshot":approved}

def prepare(attempt_id):
    with get_connection(immediate=True) as conn:
        attempt = conn.execute("SELECT * FROM send_attempts WHERE id=?", (attempt_id,)).fetchone()
        if not attempt or attempt["state"]!="reserved":
            raise Conflict("Attempt is not reserved")
        row = require_email(conn,attempt["email_id"])
        if row["status"]!="sending":
            raise Conflict("Send claim is no longer valid")
        approved = _validate(conn,row)
        _quota(conn,row["company_id"],attempt_id)
        from sender import is_in_send_window
        if not is_in_send_window():
            raise Conflict("Outside send window")
        conn.execute("UPDATE send_attempts SET state='submitting',updated_at=? WHERE id=?", (timestamp(),attempt_id))
        event(conn,row["id"],"submission_started",{"attempt_id":attempt_id})
        return approved

def finish(attempt_id, state, error_code=None):
    if state not in {"accepted","failed","uncertain","canceled"}:
        raise ValueError("Invalid attempt result")
    with get_connection(immediate=True) as conn:
        attempt = conn.execute("SELECT * FROM send_attempts WHERE id=?", (attempt_id,)).fetchone()
        if not attempt:
            raise Conflict("Attempt not found")
        if attempt["state"]=="accepted":
            return
        if attempt["state"] not in {"reserved","submitting","uncertain"}:
            raise Conflict("Attempt is already completed")
        status={"accepted":"sent","failed":"failed","uncertain":"uncertain","canceled":"canceled"}[state]
        now=timestamp()
        conn.execute("UPDATE send_attempts SET state=?,updated_at=?,error_code=? WHERE id=?", (state,now,error_code,attempt_id))
        if state=="accepted":
            conn.execute("UPDATE emails SET status='sent',sent_at=COALESCE(sent_at,?),updated_at=? WHERE id=?",(now,now,attempt["email_id"]))
        else:
            conn.execute("UPDATE emails SET status=?,updated_at=? WHERE id=?",(status,now,attempt["email_id"]))
        event(conn,attempt["email_id"],f"send_{state}",{"attempt_id":attempt_id,"error_code":error_code})

def recover():
    """Called only after the single worker lock is held; never resend uncertain work."""
    with get_connection(immediate=True) as conn:
        active = conn.execute("SELECT * FROM send_attempts WHERE state IN ('reserved','submitting')").fetchall()
        for attempt in active:
            uncertain=attempt["state"]=="submitting"
            state="uncertain" if uncertain else "failed"
            conn.execute("UPDATE send_attempts SET state=?,updated_at=?,error_code='worker_restart' WHERE id=?",
                         (state,timestamp(),attempt["id"]))
            conn.execute("UPDATE emails SET status=?,updated_at=? WHERE id=?",(state,timestamp(),attempt["email_id"]))
            event(conn,attempt["email_id"],"recovered",{"attempt_id":attempt["id"],"state":state})

def reconcile(attempt_id, accepted):
    attempt=one("SELECT * FROM send_attempts WHERE id=?",(attempt_id,))
    if not attempt or attempt["state"]!="uncertain":
        raise Conflict("Only uncertain attempts can be reconciled")
    finish(attempt_id,"accepted" if accepted else "failed","operator_reconciliation")
