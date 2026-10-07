"""One eligibility policy used for listing, composition, approval and delivery."""
from datetime import datetime, timedelta, timezone
import config
from errors import Conflict
from repository import JOINED

CLOSED = {"replied","bounced","interview_scheduled","interview_completed","offer","no_offer"}

def parsed_time(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z","+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def resolve_root(conn,parent):
    seen=set()
    current=dict(parent)
    while True:
        if current["id"] in seen: raise Conflict("Thread has a cycle; review legacy data")
        seen.add(current["id"])
        if not current["follow_up_to_email_id"]: return current["id"]
        previous=conn.execute("SELECT * FROM emails WHERE id=?",(current["follow_up_to_email_id"],)).fetchone()
        if not previous or previous["company_id"]!=parent["company_id"] or previous["contact_id"]!=parent["contact_id"]:
            raise Conflict("Invalid legacy thread relationship")
        current=dict(previous)

def check(conn, row, for_existing=False):
    parent_id = row.get("follow_up_to_email_id")
    if not parent_id:
        return
    parent = conn.execute("SELECT * FROM emails WHERE id=?", (parent_id,)).fetchone()
    if not parent or not parent["sent_at"]:
        raise Conflict("Follow-ups require an actually sent email")
    if parent["company_id"]!=row["company_id"] or parent["contact_id"]!=row["contact_id"]:
        raise Conflict("Follow-up recipient does not match its parent")
    root = resolve_root(conn,parent)
    ct = conn.execute("SELECT email,archived FROM contacts WHERE id=?", (row["contact_id"],)).fetchone()
    if not ct or ct["archived"] or conn.execute("SELECT 1 FROM suppressions WHERE lower(trim(email))=?", (ct["email"].strip().lower(),)).fetchone():
        raise Conflict("Recipient is unavailable or suppressed")
    history = conn.execute("""SELECT e.* FROM emails e JOIN contacts c ON c.id=e.contact_id
        WHERE lower(trim(c.email))=?""",(ct["email"].strip().lower(),)).fetchall()
    thread = [dict(e) for e in history if e["id"]==root or e["thread_root_id"]==root]
    if any(e["status"] in CLOSED for e in history):
        raise Conflict("Recipient has replied or reached a closed outcome")
    sent = [e for e in thread if e["sent_at"]]
    if not sent or config.now()-max(parsed_time(e["sent_at"]) for e in sent) < timedelta(days=config.FOLLOW_UP_AFTER_DAYS):
        raise Conflict("Follow-up is not due yet")
    existing_id = row.get("id") if for_existing else None
    followups = [e for e in thread if e["follow_up_to_email_id"] and e["id"]!=existing_id and e["status"] not in {"rejected","failed","canceled"}]
    if len(followups) >= config.MAX_FOLLOW_UPS:
        raise Conflict("Follow-up limit reached")
    if any(e["status"] in {"pending_review","approved","sending","uncertain"} for e in followups):
        raise Conflict("A follow-up already exists")

def due(limit=100,offset=0):
    from db import get_connection
    with get_connection() as conn:
        result=[]
        cursor=0;eligible=0
        while len(result)<limit:
            candidates=[dict(r) for r in conn.execute(JOINED+"""WHERE e.sent_at IS NOT NULL
                AND e.status IN ('sent','ghosted') AND e.follow_up_to_email_id IS NULL
                AND ct.archived=0 AND c.archived=0 AND e.id>? ORDER BY e.id LIMIT 500""",(cursor,))]
            if not candidates: break
            for original in candidates:
                cursor=original["id"]
                proposed={**original,"follow_up_to_email_id":original["id"]}
                try: check(conn,proposed)
                except Conflict: continue
                if eligible>=offset: result.append(original)
                eligible+=1
                if len(result)>=limit: break
        return result
