"""Durable operation queue. The CLI worker owns provider calls."""
import json
import logging
import uuid
import threading
from contextlib import contextmanager
from db import get_connection
from errors import Conflict,NotFound,AppError
from repository import timestamp,JOINED

KINDS={"compose","followup","regenerate","send","replies","diagnostics"}

def public(row):
    item=dict(row)
    item["payload"]=json.loads(item["payload"])
    item["result"]=json.loads(item["result"]) if item["result"] else None
    return item

def enqueue(kind,payload,request_key=None):
    if kind not in KINDS: raise ValueError("Unknown job kind")
    key=request_key or uuid.uuid4().hex
    payload=dict(payload)
    if kind=='send': payload['dry_run']=payload.get('dry_run',False)
    def same(existing):
        saved=json.loads(existing['payload'])
        if kind=='send':
            if 'members' not in payload: saved.pop('members',None)
            if 'batch_sender' not in payload: saved.pop('batch_sender',None)
        return saved==payload
    with get_connection(immediate=True) as conn:
        existing=conn.execute("SELECT * FROM jobs WHERE request_key=?",(key,)).fetchone()
        if existing:
            if existing["kind"]!=kind or not same(existing):
                raise Conflict("Idempotency key was used with different inputs")
            return public(existing)
        if kind in {"send","replies"}:
            existing=conn.execute("SELECT * FROM jobs WHERE kind=? AND status IN ('pending','running')",(kind,)).fetchone()
            if existing:
                if not same(existing):
                    raise Conflict("Another operation of this kind is pending with different inputs; wait for its result")
                return public(existing)
        if kind=='send':
            import config
            payload.setdefault('members',[{'id':r['id'],'revision':r['revision']} for r in conn.execute("SELECT id,revision FROM emails WHERE status='approved' ORDER BY created_at,id")])
            payload.setdefault('batch_sender',config.GMAIL_ADDRESS.strip().lower())
        body=json.dumps(payload,sort_keys=True)
        now=timestamp()
        jid=conn.execute("INSERT INTO jobs(kind,payload,request_key,created_at,updated_at) VALUES (?,?,?,?,?)",(kind,body,key,now,now)).lastrowid
        return public(conn.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone())

def get(jid):
    with get_connection() as conn:
        row=conn.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone()
        if not row: raise NotFound("Job not found")
        return public(row)

def by_key(key):
    with get_connection() as conn:
        row=conn.execute('SELECT * FROM jobs WHERE request_key=?',(key,)).fetchone()
        if not row: raise NotFound('No job is recorded for this request yet; retry with the same request key')
        return public(row)

@contextmanager
def heartbeat(jid):
    stopped=threading.Event()
    def beat():
        while not stopped.wait(2):
            try:
                with get_connection() as conn:
                    conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('worker_heartbeat',?)",(timestamp(),))
            except Exception:
                logging.error('heartbeat_failed job_id=%s',jid)
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try: yield
    finally: stopped.set();thread.join(timeout=5)

def health():
    import config
    from followups import parsed_time
    from filelock import FileLock,Timeout
    with get_connection() as conn:
        beat=conn.execute("SELECT value FROM settings WHERE key='worker_heartbeat'").fetchone()
        active=conn.execute("SELECT id,kind,updated_at,created_at FROM jobs WHERE status='running' ORDER BY id LIMIT 1").fetchone()
    stage={'compose':'Generating draft','regenerate':'Regenerating draft','followup':'Generating follow-up','replies':'Scanning mailbox','send':'Processing send batch'}
    state='not_started'
    if beat:
        age=max(0,(config.now()-parsed_time(beat['value'])).total_seconds())
        state='busy' if active else 'idle'
        if age>15:
            try:
                with FileLock(str(config.DB_PATH)+'.worker.lock',timeout=0): state='stopped'
            except Timeout: state='suspected_stalled'
    return {'state':state,'last_seen':beat['value'] if beat else None,'active_job':dict(active) if active else None,
        'stage':stage.get(active['kind']) if active else 'Waiting for work','last_progress':active['updated_at'] if active else None}

def list_jobs():
    with get_connection() as conn:
        return [public(r) for r in conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 100")]


def stop(jid):
    with get_connection(immediate=True) as conn:
        row=conn.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row: raise NotFound('Job not found')
        if row['kind']!='send': raise Conflict('Only send batches support stopping')
        if row['status']=='pending':
            conn.execute("UPDATE jobs SET status='canceled',updated_at=? WHERE id=?",(timestamp(),jid))
        elif row['status']=='running':
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",(f'stop_job:{jid}','1'))
        else: raise Conflict('This batch is already finished')


def send_plan():
    import config
    import sender
    with get_connection() as conn:
        members=[dict(r) for r in conn.execute(JOINED+"WHERE e.status='approved' ORDER BY e.created_at,e.id")]
    account=config.GMAIL_ADDRESS.strip().lower()
    preflight=sender.run_send_batch(dry_run=True,members=[{'id':r['id'],'revision':r['revision']} for r in members],batch_sender=account)
    return {'sender':account,'members':members,'preflight':preflight,
        'projected_eligible':sum(r['status']=='dry_run' for r in preflight)}

def _dispatch(kind,payload,progress):
    if kind=='diagnostics':
        from account_checks import check_and_save
        return check_and_save()
    if kind=="send":
        import sender
        if 'members' not in payload: raise Conflict('Legacy batch has no fixed recipients; queue a new reviewed batch')
        result=sender.run_send_batch(progress=progress,stop_requested=getattr(progress,'stop_requested',lambda:False),**payload)
        return {"summary":result,"counts":{name:sum(r["status"]==name for r in result) for name in ("sent","failed","uncertain","skipped","deferred","dry_run","canceled")}}
    if kind=="replies":
        import replies
        return replies.check_replies(detailed=True)
    import composer
    if kind=="compose":
        return {"id":composer.compose_and_store(**payload)}
    if kind=='regenerate': return {'id':composer.regenerate(**payload)}
    return {"id":composer.compose_follow_up_and_store(payload["email_id"],**{k:v for k,v in payload.items() if k!='email_id'})}

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
    def stop_requested():
        with get_connection() as conn:
            return bool(conn.execute('SELECT 1 FROM settings WHERE key=?',(f"stop_job:{job['id']}",)).fetchone())
    progress.stop_requested=stop_requested
    try:
        logging.info('job_started job_id=%s kind=%s',job['id'],job['kind'])
        with heartbeat(job['id']): result=_dispatch(job["kind"],job["payload"],progress)
        with get_connection() as conn:
            conn.execute("UPDATE jobs SET status=?,result=?,updated_at=? WHERE id=?",('canceled' if stop_requested() else 'complete',json.dumps(result),timestamp(),job["id"]))
        logging.info('job_finished job_id=%s kind=%s',job['id'],job['kind'])
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
