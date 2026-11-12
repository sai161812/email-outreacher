"""Cumulative per-message funnel, grouped by resume ID and local send day."""
from datetime import datetime,timezone
import config
import followups
from errors import Conflict,NotFound
from repository import EmailRepository,ResumeRepository,rows

def _set_status(eid,status,source='system',operation_id=None):
    return EmailRepository.update_status(eid,status,source=source,operation_id=operation_id)

def mark_replied(eid,source='system'):
    import uuid
    operation_id=uuid.uuid4().hex if source=='manual' else None
    original=EmailRepository.get_by_id(eid)
    if not original:
        raise NotFound("Email not found")
    if not original["sent_at"]:
        raise Conflict("Only actually sent emails can have replies")
    root=original["thread_root_id"] or original["id"]
    for item in rows("SELECT * FROM emails WHERE id=? OR thread_root_id=?",(root,root)):
        if item["sent_at"] and item["status"] in {"sent","ghosted"}:
            try:
                _set_status(item["id"],"replied",source,operation_id)
            except Conflict:
                pass  # A concurrent interview/offer must not be downgraded.

def mark_ghosted(eid,source='system'): return _set_status(eid,"ghosted",source)
def mark_bounced(eid,suppress=True,source='system'): return EmailRepository.update_status(eid,"bounced",suppress_bounce=suppress,source=source)
def mark_interview_scheduled(eid,source='system'): return _set_status(eid,"interview_scheduled",source)
def mark_interview_completed(eid,source='system'): return _set_status(eid,"interview_completed",source)
def mark_offer(eid,source='system'): return _set_status(eid,"offer",source)
def mark_no_offer(eid,source='system'): return _set_status(eid,"no_offer",source)

OUTCOMES={'replied','ghosted','bounced','interview_scheduled','interview_completed','offer','no_offer'}
CATEGORIES={'unknown','positive_interest','referral','rejection','not_hiring','other'}

def categorize(eid,category):
    from db import get_connection
    from repository import require_email,event,timestamp
    if not isinstance(category,str) or category not in CATEGORIES: raise ValueError('Choose a valid response category')
    with get_connection(immediate=True) as conn:
        row=require_email(conn,eid)
        if not row['sent_at']: raise Conflict('Only submitted messages can have response categories')
        conn.execute('UPDATE emails SET response_category=?,updated_at=? WHERE id=?',(category,timestamp(),eid))
        event(conn,eid,'response_categorized',{'source':'manual','previous_category':row['response_category'],'category':category})
        if category!='unknown':
            import uuid
            operation=uuid.uuid4().hex;root=row['thread_root_id'] or row['id']
            thread=conn.execute("SELECT * FROM emails WHERE (id=? OR thread_root_id=?) AND sent_at IS NOT NULL AND status IN ('sent','ghosted')",(root,root)).fetchall()
            for original in thread:
                conn.execute("UPDATE emails SET status='replied',updated_at=? WHERE id=?",(timestamp(),original['id']))
                event(conn,original['id'],'replied',{'source':'manual','previous_status':original['status'],'operation_id':operation})
            conn.execute("UPDATE emails SET status='canceled',approval_json=NULL,revision=revision+1,updated_at=? WHERE status IN ('pending_review','approved') AND contact_id IN (SELECT id FROM contacts WHERE lower(trim(email))=(SELECT lower(trim(email)) FROM contacts WHERE id=?))",(timestamp(),row['contact_id']))

def contact_funnel():
    import json
    sent=rows("""SELECT e.*,lower(trim(ct.email)) recipient FROM emails e JOIN contacts ct ON ct.id=e.contact_id
        WHERE e.sent_at IS NOT NULL""")
    evidence=rows("SELECT id,email_id,kind,detail FROM events WHERE kind IN ('replied','interview_scheduled','interview_completed','outcome_corrected')")
    reverted={value for event in evidence if event['kind']=='outcome_corrected' for value in json.loads(event['detail']).get('reverted_event_ids',[])}
    replied={event['email_id'] for event in evidence if event['kind']=='replied' and event['id'] not in reverted}
    interviewed={event['email_id'] for event in evidence if event['kind'] in {'interview_scheduled','interview_completed'} and event['id'] not in reverted}
    people={};cohorts={}
    for row in sent: people.setdefault(row['recipient'],[]).append(row)
    def counts(groups):
        total=len(groups);response=positive=interviews=offers=0
        for thread in groups.values():
            response+=any(r['id'] in replied or r['status']=='replied' or r['response_category']!='unknown' for r in thread)
            positive+=any(r['response_category'] in {'positive_interest','referral'} for r in thread)
            interviews+=any(r['id'] in interviewed or r['status'] in {'interview_scheduled','interview_completed'} for r in thread)
            offers+=any(r['status']=='offer' for r in thread)
        return {'contacted':total,'human_responses':response,'positive_interest_or_referral':positive,'interviews':interviews,'offers':offers,
            'response_rate':round(response/total*100,1) if total else 0,'positive_rate':round(positive/total*100,1) if total else 0}
    for person,thread in people.items():
        first=min(thread,key=lambda r:r['sent_at'])
        snapshot=(json.loads(first['input_snapshot_json']) if first['input_snapshot_json'] else {}) or {}
        target=snapshot.get('opportunity') or {};proof=snapshot.get('project') or {}
        stamp=datetime.fromisoformat(first['sent_at'].replace('Z','+00:00'))
        if not stamp.tzinfo: stamp=stamp.replace(tzinfo=timezone.utc)
        key=(target.get('role','Unspecified'),proof.get('name','Unspecified'),target.get('approach') or 'Unspecified',stamp.astimezone(config.TIMEZONE).strftime('%Y-%m'))
        cohorts.setdefault(key,{})[person]=thread
    return {**counts(people),'sent_messages':len(sent),'initial_contacts':len({r['recipient'] for r in sent if not r['follow_up_to_email_id']}),
        'conversations':len({r['thread_root_id'] or r['id'] for r in sent}),
        'denominator':'Unique recipient addresses contacted; follow-ups do not add people. Unknown categories do not establish positive interest.',
        'response_basis':'Recorded human reply or explicit owner response category. Terminal outcomes alone do not establish a human reply.',
        'cohorts':[dict(zip(('role','proof','approach','month'),key),**counts(group)) for key,group in sorted(cohorts.items())],
        'interpretation':'Descriptive small-sample counts; no causal claims about writing, timing or hiring uplift.'}

def tracking_page(limit=100,offset=0):
    import json
    from services.state_machine import TRANSITIONS
    items=EmailRepository.get_all_tracked_emails(limit,offset)
    ids=[item['id'] for item in items]
    latest=rows("SELECT * FROM events WHERE id IN (SELECT MAX(id) FROM events WHERE email_id IN ("+','.join('?' for _ in ids)+") AND kind IN ('replied','ghosted','bounced','interview_scheduled','interview_completed','offer','no_offer','outcome_corrected') GROUP BY email_id)",ids) if ids else []
    by_id={entry['email_id']:entry for entry in latest}
    for item in items:
        last=[by_id[item['id']]] if item['id'] in by_id else []
        detail=json.loads(last[0]['detail']) if last else {}
        item['allowed_outcomes']=sorted(OUTCOMES & TRANSITIONS.get(item['status'],set())) if item['sent_at'] else []
        item['correctable_event_id']=last[0]['id'] if last and last[0]['kind']==item['status'] and detail.get('source')=='manual' else None
    return items

def correct_outcome(eid,event_id,reason):
    import json
    from db import get_connection
    from repository import require_email,event,timestamp
    with get_connection(immediate=True) as conn:
        selected=conn.execute('SELECT * FROM events WHERE id=? AND email_id=?',(event_id,eid)).fetchone()
        if not selected or selected['kind'] not in OUTCOMES: raise Conflict('This outcome cannot be corrected')
        detail=json.loads(selected['detail'])
        if detail.get('source')!='manual': raise Conflict('Only recorded manual outcomes can be corrected')
        group=conn.execute("SELECT * FROM events WHERE json_extract(detail,'$.operation_id')=?",(detail['operation_id'],)).fetchall() if detail.get('operation_id') else [selected]
        for entry in group:
            row=require_email(conn,entry['email_id'])
            latest=conn.execute("SELECT id FROM events WHERE email_id=? AND kind IN ('replied','ghosted','bounced','interview_scheduled','interview_completed','offer','no_offer','outcome_corrected') ORDER BY id DESC LIMIT 1",(row['id'],)).fetchone()
            if not row['sent_at'] or row['status']!=entry['kind'] or latest['id']!=entry['id']: raise Conflict('Outcome changed; reload before correcting')
        reverted=[e['id'] for e in group]
        for entry in group:
            previous=json.loads(entry['detail'])['previous_status']
            conn.execute('UPDATE emails SET status=?,updated_at=? WHERE id=?',(previous,timestamp(),entry['email_id']))
            event(conn,entry['email_id'],'outcome_corrected',{'source':'manual','reason':reason,'previous_status':entry['kind'],'restored_status':previous,'reverted_event_ids':reverted})
def due_for_follow_up(limit=100,offset=0): return followups.due(limit,offset)

def pipeline_summary():
    result={r["status"]:r["n"] for r in rows("SELECT status,COUNT(*) n FROM emails GROUP BY status")}
    sent=rows("SELECT * FROM emails WHERE sent_at IS NOT NULL")
    result["sent"]=len(sent)
    result["replied"]=sum(e["status"] in {"replied","interview_scheduled","interview_completed","offer","no_offer"} for e in sent)
    return result

def stats():
    variants={r["id"]:r["name"] for r in rows('SELECT id,name FROM resume_variants')}
    metrics={}
    weekdays={d:{"sent":0,"replied":0,"interviews":0,"offers":0} for d in ("Mon","Tue","Wed","Thu","Fri","Sat","Sun")}
    for row in rows("""SELECT e.*,EXISTS(SELECT 1 FROM events v WHERE v.email_id=e.id
        AND v.kind IN ('interview_scheduled','interview_completed') AND NOT EXISTS (SELECT 1 FROM events c,json_each(c.detail,'$.reverted_event_ids') r WHERE c.kind='outcome_corrected' AND r.value=v.id)) recorded_interview
        FROM emails e WHERE e.sent_at IS NOT NULL"""):
        key=row["resume_variant_id"]
        entry=metrics.setdefault(key,{"sent":0,"replied":0,"interviews":0,"offers":0})
        parsed=datetime.fromisoformat(row["sent_at"].replace("Z","+00:00"))
        if not parsed.tzinfo: parsed=parsed.replace(tzinfo=timezone.utc)
        day=parsed.astimezone(config.TIMEZONE).strftime("%a")
        flags={"sent":1,"replied":int(row["status"] in {"replied","interview_scheduled","interview_completed","offer","no_offer"}),
               "interviews":int(row["recorded_interview"] or row["status"] in {"interview_scheduled","interview_completed"}),"offers":int(row["status"]=="offer")}
        for name,value in flags.items():
            entry[name]+=value
            weekdays[day][name]+=value
    def rates(entry):
        return {**entry,**{name+"_rate":round(entry[field]/entry["sent"]*100,1) if entry["sent"] else 0
                          for name,field in (("reply","replied"),("interview","interviews"),("offer","offers"))}}
    return {"denominator":"sent messages (including follow-ups)",
            "interview_basis":"Recorded interview events or current interview status; terminal outcomes alone do not establish an interview",
            "by_variant":[{"id":key,"name":variants.get(key,"Unassigned"),"variant":variants.get(key,"Unassigned"),**rates(value)} for key,value in metrics.items()],
            "by_weekday":[{"day":day,"weekday":day,**rates(value)} for day,value in weekdays.items()]}
