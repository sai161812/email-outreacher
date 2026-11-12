"""Small role briefs and owner-supplied project evidence."""
import json
import uuid
from datetime import date
from contacts import text,get_company
from resume import safe_url
from db import get_connection
from repository import rows,one,timestamp,event,require_email,check_revision
from errors import Conflict,NotFound
import config

FIELDS={'role','level','role_url','requisition','application_status','application_date','constraints','project_id','relationship','company_source','source_verified_date','job_text','approach'}

def projects():
    saved=one("SELECT value FROM settings WHERE key='projects'")
    return json.loads(saved['value']) if saved else []

def invalidate(conn,opportunity_id=None):
    where="status IN ('pending_review','approved')"+(" AND opportunity_id=?" if opportunity_id else '')
    args=(opportunity_id,) if opportunity_id else ()
    affected=conn.execute('SELECT id FROM emails WHERE '+where,args).fetchall()
    conn.execute("UPDATE emails SET evidence_verified_at=NULL,approval_json=NULL,status='pending_review',revision=revision+1,updated_at=? WHERE "+where,(timestamp(),*args))
    for row in affected: event(conn,row['id'],'evidence_changed')

def save_projects(items):
    if not isinstance(items,list) or len(items)>3: raise ValueError('Supply at most three projects')
    cleaned=[]
    for item in items:
        if not isinstance(item,dict) or set(item)-{'id','name','action','result','proof_url'}: raise ValueError('Invalid project fields')
        pid=item.get('id') or uuid.uuid4().hex
        if not isinstance(pid,str) or not pid.isalnum() or len(pid)>64: raise ValueError('Invalid project id')
        cleaned.append({'id':pid,'name':text(item.get('name'),'name',True,200),'action':text(item.get('action'),'action',True,3000),
            'result':text(item.get('result'),'result',maximum=3000),'proof_url':safe_url(item.get('proof_url'))})
    if len({p['id'] for p in cleaned})!=len(cleaned): raise ValueError('Duplicate project ids')
    with get_connection(immediate=True) as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('projects',?)",(json.dumps(cleaned),))
        invalidate(conn)
    return cleaned

def get(oid,company_id=None):
    row=one('SELECT * FROM opportunities WHERE id=?',(oid,))
    if not row: raise NotFound('Opportunity not found')
    if company_id is not None and row['company_id']!=company_id: raise Conflict('Opportunity belongs to another company')
    return {**json.loads(row['brief_json']),**row}

def list_all(company_id=None):
    query='SELECT * FROM opportunities'
    return [{**json.loads(r['brief_json']),**r} for r in rows(query+(' WHERE company_id=?' if company_id else '')+' ORDER BY id',(company_id,) if company_id else ())]

def save(company_id,data,oid=None):
    get_company(company_id)
    if not isinstance(data,dict) or set(data)-FIELDS: raise ValueError('Invalid opportunity fields')
    role=text(data.get('role'),'role',True,200);job=text(data.get('job_text'),'job_text',maximum=20000) or ''
    brief={k:text(v,k,maximum=2000) for k,v in data.items() if k not in {'role','job_text'}}
    for key in ('role_url','company_source'): brief[key]=safe_url(data.get(key))
    if brief.get('application_status') not in {None,'unknown','not_applied','applied'}: raise ValueError('Invalid application status')
    for key in ('application_date','source_verified_date'):
        if brief.get(key):
            date.fromisoformat(brief[key])
            if date.fromisoformat(brief[key])>config.now().astimezone(config.TIMEZONE).date(): raise ValueError('Evidence dates must not be in the future')
    if brief.get('application_date') and brief.get('application_status')!='applied': raise ValueError('Application date requires applied status')
    if brief.get('project_id') and brief['project_id'] not in {p['id'] for p in projects()}: raise ValueError('Selected project not found')
    with get_connection(immediate=True) as conn:
        if oid:
            old=conn.execute('SELECT company_id FROM opportunities WHERE id=?',(oid,)).fetchone()
            if not old or old['company_id']!=company_id: raise NotFound('Opportunity not found')
            conn.execute('UPDATE opportunities SET role=?,job_text=?,brief_json=?,revision=revision+1 WHERE id=?',(role,job,json.dumps(brief),oid))
            invalidate(conn,oid)
        else: oid=conn.execute('INSERT INTO opportunities(company_id,role,job_text,brief_json) VALUES (?,?,?,?)',(company_id,role,job,json.dumps(brief))).lastrowid
    return oid

def acknowledge(eid,revision):
    with get_connection(immediate=True) as conn:
        row=require_email(conn,eid);check_revision(row,revision)
        if row['status']!='pending_review': raise Conflict('Review the pending revision first')
        conn.execute('UPDATE emails SET evidence_verified_at=? WHERE id=?',(timestamp(),eid))
        event(conn,eid,'evidence_verified',{'revision':revision})
