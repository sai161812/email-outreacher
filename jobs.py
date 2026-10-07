"""Durable operation queue. The CLI worker owns provider calls."""
import json
import logging
import uuid
from db import get_connection
from errors import Conflict,NotFound,AppError
from repository import timestamp

KINDS={"compose","followup","send","replies"}

def public(row):
    item=dict(row)
    item["payload"]=json.loads(item["payload"])
    item["result"]=json.loads(item["result"]) if item["result"] else None
    return item

def enqueue(kind,payload,request_key=None):
    if kind not in KINDS: raise ValueError("Unknown job kind")
    key=request_key or uuid.uuid4().hex
    body=json.dumps(payload,sort_keys=True)
    with get_connection(immediate=True) as conn:
        existing=conn.execute("SELECT * FROM jobs WHERE request_key=?",(key,)).fetchone()
        if existing:
            if existing["kind"]!=kind or existing["payload"]!=body:
                raise Conflict("Idempotency key was used with different inputs")
            return public(existing)
        if kind in {"send","replies"}:
            existing=conn.execute("SELECT * FROM jobs WHERE kind=? AND status IN ('pending','running')",(kind,)).fetchone()
            if existing: return public(existing)
        now=timestamp()
        jid=conn.execute("INSERT INTO jobs(kind,payload,request_key,created_at,updated_at) VALUES (?,?,?,?,?)",(kind,body,key,now,now)).lastrowid
        return public(conn.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone())

def get(jid):
    with get_connection() as conn:
        row=conn.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone()
        if not row: raise NotFound("Job not found")
        return public(row)

def list_jobs():
    with get_connection() as conn:
        return [public(r) for r in conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 100")]

def _dispatch(kind,payload,progress):
    if kind=="send":
        import sender
        result=sender.run_send_batch(progress=progress,**payload)
        return {"summary":result,"counts":{name:sum(r["status"]==name for r in result) for name in ("sent","failed","uncertain","skipped","deferred","dry_run")}}
    if kind=="replies":
        import replies
        return {"matches":replies.check_replies()}
    import composer
    if kind=="compose":
        return {"id":composer.compose_and_store(candidate_context=composer.candidate_context(),**payload)}
    return {"id":composer.compose_follow_up_and_store(payload["email_id"])}

def process_next():
    with get_connection(immediate=True) as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('worker_heartbeat',?)",(timestamp(),))
        row=conn.execute("SELECT * FROM jobs WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
        if not row: return False
        job=public(row)
        conn.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?",(timestamp(),job["id"]))
    def progress(result):
        with get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('worker_heartbeat',?)",(timestamp(),))
            conn.execute("UPDATE jobs SET result=?,updated_at=? WHERE id=?",(json.dumps({"summary":result}),timestamp(),job["id"]))
    try:
        result=_dispatch(job["kind"],job["payload"],progress)
        with get_connection() as conn:
            conn.execute("UPDATE jobs SET status='complete',result=?,updated_at=? WHERE id=?",(json.dumps(result),timestamp(),job["id"]))
    except Exception as exc:
        message=str(exc) if isinstance(exc,(AppError,ValueError)) else "Operation failed; check worker diagnostics"
        logging.error("job_failed job_id=%s kind=%s error_type=%s",job["id"],job["kind"],type(exc).__name__)
        with get_connection() as conn:
            conn.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=?",(message,timestamp(),job["id"]))
    return True

def recover():
    import delivery
    delivery.recover()
    with get_connection() as conn:
        conn.execute("UPDATE jobs SET status='failed',error='Worker interrupted; review delivery attempts before retrying',updated_at=? WHERE status='running'",(timestamp(),))
