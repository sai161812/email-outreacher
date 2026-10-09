"""Central persistence boundary. Public query results are dictionaries."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from email.utils import make_msgid
import config
from db import get_connection
from errors import Conflict, NotFound
from services.state_machine import can_transition

def timestamp():
    return config.now().isoformat()

def rows(sql, params=()):
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(sql, params)]

def one(sql, params=()):
    result = rows(sql, params)
    return result[0] if result else None

def event(conn, eid, kind, detail=None):
    conn.execute("INSERT INTO events(email_id,kind,detail,created_at) VALUES (?,?,?,?)",
                 (eid, kind, json.dumps(detail or {}), timestamp()))

def require_email(conn, eid):
    row = conn.execute("SELECT * FROM emails WHERE id=?", (eid,)).fetchone()
    if not row:
        raise NotFound("Email not found")
    return dict(row)

def check_revision(row, expected):
    if expected is not None and row["revision"] != expected:
        raise Conflict("Draft changed. Reload and review the latest revision.")

def revoke_approvals(conn,field,record_id):
    if field not in {"company_id","contact_id"}: raise ValueError("Invalid approval relationship")
    affected=conn.execute(f"SELECT id FROM emails WHERE {field}=? AND status='approved'",(record_id,)).fetchall()
    conn.execute(f"UPDATE emails SET status='pending_review',approval_json=NULL,revision=revision+1,updated_at=? WHERE {field}=? AND status='approved'",(timestamp(),record_id))
    for row in affected: event(conn,row["id"],"approval_revoked",{"changed":field})

def snapshot(conn, row):
    import resume
    ct = conn.execute("SELECT * FROM contacts WHERE id=?", (row["contact_id"],)).fetchone()
    company = conn.execute("SELECT * FROM companies WHERE id=?", (row["company_id"],)).fetchone()
    if not ct or not company or ct["company_id"] != row["company_id"] or ct["archived"] or company["archived"]:
        raise Conflict("Contact/company is unavailable")
    asset = resume.delivery_asset(row.get("resume_variant_id"))
    return {"revision": row["revision"], "subject": row["subject"], "body": row["body"],
            "recipient": ct["email"].strip().lower(), "company_name": company["name"],
            "resume": asset, "attach_mode": config.RESUME_ATTACH_MODE}

class CompanyRepository:
    @staticmethod
    def get_all(limit=500,offset=0,search=""):
        return rows("""SELECT c.*,(SELECT COUNT(*) FROM contacts ct WHERE ct.company_id=c.id AND ct.archived=0) contact_count
                       FROM companies c WHERE c.archived=0 AND (c.name LIKE ? OR c.domain LIKE ?)
                       ORDER BY c.name,c.id LIMIT ? OFFSET ?""",(f"%{search}%",f"%{search}%",limit,offset))
    @staticmethod
    def find_identity(name,domain=None):
        return one("SELECT * FROM companies WHERE archived=0 AND (lower(trim(name))=lower(trim(?)) OR (? IS NOT NULL AND lower(trim(domain))=?)) ORDER BY id LIMIT 1",(name,domain,domain))
    @staticmethod
    def update(cid,data):
        if not data or set(data)-{"name","domain","job_url","job_text","notes"}: raise ValueError("Invalid company changes")
        with get_connection(immediate=True) as conn:
            if not conn.execute("SELECT 1 FROM companies WHERE id=? AND archived=0",(cid,)).fetchone(): raise NotFound("Company not found")
            if conn.execute("SELECT 1 FROM emails WHERE company_id=? AND status IN ('sending','uncertain')",(cid,)).fetchone():
                raise Conflict("Resolve in-flight delivery before changing this company")
            conn.execute("UPDATE companies SET "+",".join(f"{k}=?" for k in data)+" WHERE id=?",(*data.values(),cid))
            revoke_approvals(conn,"company_id",cid)
    @staticmethod
    def get_by_id(cid):
        return one("SELECT * FROM companies WHERE id=?", (cid,))
    @staticmethod
    def get_by_name(name):
        return one("SELECT * FROM companies WHERE lower(trim(name))=lower(trim(?)) AND archived=0", (name,))
    @staticmethod
    def create(name, domain=None, job_url=None, job_text=None, notes=None):
        with get_connection() as conn:
            try:
                return conn.execute("INSERT INTO companies(name,domain,job_url,job_text,notes) VALUES (?,?,?,?,?)",
                                    (name, domain, job_url, job_text, notes)).lastrowid
            except sqlite3.IntegrityError as exc:
                raise Conflict("Company already exists or data is invalid") from exc

class ContactRepository:
    @staticmethod
    def get_all_by_company(company_id=None, limit=500, offset=0, search=""):
        sql="""SELECT ct.*,c.name company_name FROM contacts ct JOIN companies c ON ct.company_id=c.id
               WHERE ct.archived=0 AND c.archived=0"""
        params=[]
        if company_id is not None:
            sql+=" AND ct.company_id=?";params.append(company_id)
        if search:
            sql+=" AND (ct.name LIKE ? OR ct.email LIKE ? OR c.name LIKE ?)";params.extend([f"%{search}%"]*3)
        return rows(sql+" ORDER BY c.name,ct.email LIMIT ? OFFSET ?",(*params,limit,offset))
    @staticmethod
    def update(cid,data):
        if not data or set(data)-{"email","name","title","source","archived"}: raise ValueError("Invalid contact changes")
        with get_connection(immediate=True) as conn:
            original=conn.execute("SELECT * FROM contacts WHERE id=? AND archived=0",(cid,)).fetchone()
            if not original: raise NotFound("Contact not found")
            if conn.execute("SELECT 1 FROM emails WHERE contact_id=? AND status IN ('sending','uncertain')",(cid,)).fetchone():
                raise Conflict("Resolve in-flight delivery before changing this contact")
            if "email" in data and data["email"]!=original["email"] and conn.execute("SELECT 1 FROM emails WHERE contact_id=? AND sent_at IS NOT NULL",(cid,)).fetchone():
                raise Conflict("Create a new contact to change an address with send history")
            conn.execute("UPDATE contacts SET "+",".join(f"{k}=?" for k in data)+" WHERE id=?",(*data.values(),cid))
            if data.get("archived"):
                affected=conn.execute("SELECT id FROM emails WHERE contact_id=? AND status IN ('pending_review','approved')",(cid,)).fetchall()
                conn.execute("UPDATE emails SET status='canceled',approval_json=NULL,revision=revision+1,updated_at=? WHERE contact_id=? AND status IN ('pending_review','approved')",(timestamp(),cid))
                for row in affected: event(conn,row["id"],"canceled",{"reason":"contact_archived"})
            else:
                revoke_approvals(conn,"contact_id",cid)
    @staticmethod
    def duplicate_groups():
        return rows("""SELECT ct.company_id,c.name company_name,lower(trim(ct.email)) email,
            COUNT(*) count,group_concat(ct.id) contact_ids FROM contacts ct JOIN companies c ON c.id=ct.company_id
            WHERE ct.archived=0 GROUP BY ct.company_id,lower(trim(ct.email)) HAVING COUNT(*)>1
            ORDER BY c.name,lower(trim(ct.email)) LIMIT 500""")
    @staticmethod
    def get_by_id(cid):
        return one("SELECT * FROM contacts WHERE id=?", (cid,))
    @staticmethod
    def get_by_email_and_company(email, company_id):
        return one("SELECT * FROM contacts WHERE lower(trim(email))=lower(trim(?)) AND company_id=? AND archived=0", (email,company_id))
    @staticmethod
    def create(company_id, email, name=None, title=None, source=None):
        with get_connection() as conn:
            try:
                return conn.execute("INSERT INTO contacts(company_id,email,name,title,source) VALUES (?,?,?,?,?)",
                                    (company_id,email.strip().lower(),name,title,source)).lastrowid
            except sqlite3.IntegrityError as exc:
                raise Conflict("Contact already exists or company is invalid") from exc

class ResumeRepository:
    @staticmethod
    def get_all():
        return rows("SELECT * FROM resume_variants WHERE archived=0 ORDER BY id")
    @staticmethod
    def get_by_id(rid):
        return one("SELECT * FROM resume_variants WHERE id=? AND archived=0", (rid,))
    @staticmethod
    def create(name, keywords, file_path, resume_url=None):
        with get_connection() as conn:
            return conn.execute("INSERT INTO resume_variants(name,keywords,file_path,resume_url) VALUES (?,?,?,?)",
                                (name, keywords,file_path,resume_url)).lastrowid

class SuppressionRepository:
    @staticmethod
    def get_all():
        return rows("SELECT * FROM suppressions ORDER BY created_at DESC")
    @staticmethod
    def is_suppressed(email):
        return bool(one("SELECT 1 FROM suppressions WHERE lower(trim(email))=lower(trim(?))", (email,)))
    @staticmethod
    def add(email, reason):
        with get_connection(immediate=True) as conn:
            conn.execute("DELETE FROM suppressions WHERE lower(trim(email))=lower(trim(?))", (email,))
            conn.execute("INSERT INTO suppressions(email,reason) VALUES (?,?)", (email.strip().lower(),reason))
            conn.execute("""UPDATE emails SET status='canceled',approval_json=NULL,updated_at=?
                WHERE status IN ('pending_review','approved') AND contact_id IN
                (SELECT id FROM contacts WHERE lower(trim(email))=?)""", (timestamp(),email.strip().lower()))
    @staticmethod
    def remove(email):
        with get_connection() as conn:
            conn.execute("DELETE FROM suppressions WHERE lower(trim(email))=lower(trim(?))", (email,))

JOINED = """SELECT e.*,c.name company_name,ct.email contact_email,ct.name contact_name
            FROM emails e JOIN companies c ON e.company_id=c.id JOIN contacts ct ON e.contact_id=ct.id """

class EmailRepository:
    @staticmethod
    def get_by_id(eid):
        return one("SELECT * FROM emails WHERE id=?", (eid,))
    @staticmethod
    def get_by_contact_id(cid):
        return rows("SELECT * FROM emails WHERE contact_id=? ORDER BY id", (cid,))
    @staticmethod
    def create(company_id, contact_id, resume_variant_id, hook, subject, body, qc_warnings, follow_up_to_email_id=None, research_notes=None, grounding_json=None):
        with get_connection(immediate=True) as conn:
            root = None
            if follow_up_to_email_id:
                parent = require_email(conn, follow_up_to_email_id)
                from followups import resolve_root,check
                root = resolve_root(conn,parent)
                check(conn,{"company_id":company_id,"contact_id":contact_id,"follow_up_to_email_id":follow_up_to_email_id})
            try:
                eid = conn.execute("""INSERT INTO emails(company_id,contact_id,resume_variant_id,hook,subject,body,qc_warnings,
                    follow_up_to_email_id,thread_root_id,research_notes,grounding_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (company_id,contact_id,resume_variant_id,hook,subject,body,qc_warnings,follow_up_to_email_id,root,research_notes,grounding_json)).lastrowid
            except sqlite3.IntegrityError as exc:
                raise Conflict("Invalid relationship or recipient already has active outreach") from exc
            event(conn,eid,"draft_created")
            return eid
    @staticmethod
    def update_content(eid, subject=None, body=None, hook=None, expected_revision=None, resume_variant_id=None, change_resume=False):
        import qc
        with get_connection(immediate=True) as conn:
            row = require_email(conn,eid)
            check_revision(row,expected_revision)
            if row["sent_at"] or row["status"] not in {"pending_review","approved","rejected","failed","canceled"}:
                raise Conflict("This email cannot be edited")
            for name, value in (("subject",subject),("body",body),("hook",hook)):
                if value is not None:
                    if not isinstance(value,str):
                        raise ValueError(f"{name} must be text")
                    if len(value)>{"subject":200,"body":10000,"hook":2000}[name]:
                        raise ValueError(f"{name} exceeds the size limit")
                    row[name] = value.strip()
            if change_resume:
                row["resume_variant_id"] = resume_variant_id
            warnings = "; ".join(qc.warnings(row["subject"],row["body"],bool(row["follow_up_to_email_id"])))
            conn.execute("""UPDATE emails SET subject=?,body=?,hook=?,resume_variant_id=?,qc_warnings=?,
                status='pending_review',approval_json=NULL,revision=revision+1,updated_at=? WHERE id=?""",
                (row["subject"],row["body"],row["hook"],row["resume_variant_id"],warnings,timestamp(),eid))
            event(conn,eid,"draft_edited",{"revision":row["revision"]+1})
    @staticmethod
    def approve(eid, expected_revision=None):
        import qc
        import followups
        with get_connection(immediate=True) as conn:
            row = require_email(conn,eid)
            check_revision(row,expected_revision)
            if row["status"] != "pending_review" or row["sent_at"]:
                raise Conflict("Only a pending draft can be approved")
            errors = qc.blockers(row["subject"],row["body"])
            if row["generation_error"] or row["hook"] == "PARSE_ERROR":
                errors.append("Regenerate the failed draft")
            if errors:
                raise ValueError("; ".join(errors))
            approved = snapshot(conn,row)
            if conn.execute("SELECT 1 FROM suppressions WHERE lower(trim(email))=?", (approved["recipient"],)).fetchone():
                raise Conflict("Recipient is suppressed")
            followups.check(conn,row,for_existing=True)
            conn.execute("UPDATE emails SET status='approved',approval_json=?,updated_at=? WHERE id=?",
                         (json.dumps(approved,sort_keys=True),timestamp(),eid))
            event(conn,eid,"approved",{"revision":row["revision"]})
    @staticmethod
    def update_status(eid, status, set_updated_at=True, set_sent_at=False, sent_at_time=None):
        if status == "approved":
            return EmailRepository.approve(eid)
        with get_connection(immediate=True) as conn:
            row = require_email(conn,eid)
            if status == row["status"]:
                return
            if not can_transition(row["status"],status):
                raise Conflict(f"Cannot change {row['status']} to {status}")
            if status in {"replied","ghosted","bounced","interview_scheduled","interview_completed","offer","no_offer"} and not row["sent_at"]:
                raise Conflict("Only actually sent emails can have outcomes")
            conn.execute("UPDATE emails SET status=?,updated_at=? WHERE id=?", (status,timestamp(),eid))
            event(conn,eid,status)
            if status == "bounced":
                ct = conn.execute("SELECT email FROM contacts WHERE id=?", (row["contact_id"],)).fetchone()
                conn.execute("INSERT OR REPLACE INTO suppressions(email,reason) VALUES (?,?)", (ct["email"].strip().lower(),"hard bounce"))
            if status in {"replied","bounced","interview_scheduled","interview_completed","offer","no_offer"}:
                root = row["thread_root_id"] or row["id"]
                conn.execute("""UPDATE emails SET status='canceled',approval_json=NULL,updated_at=?
                    WHERE (thread_root_id=? OR contact_id IN (SELECT id FROM contacts WHERE lower(trim(email))=
                    (SELECT lower(trim(email)) FROM contacts WHERE id=?))) AND status IN ('pending_review','approved') AND id<>?""",
                    (timestamp(),root,row["contact_id"],eid))
    @staticmethod
    def get_pending_review(limit=100, offset=0):
        return rows(JOINED+"WHERE e.status='pending_review' ORDER BY e.created_at,e.id LIMIT ? OFFSET ?",(limit,offset))
    @staticmethod
    def get_approved_queue(limit=None,offset=0):
        sql=JOINED+"""WHERE e.status='approved' ORDER BY
                    (ct.source='referral') DESC,e.created_at,e.id"""
        return rows(sql+" LIMIT ? OFFSET ?",(limit,offset)) if limit is not None else rows(sql)
    @staticmethod
    def get_all_tracked_emails(limit=100, offset=0):
        return rows(JOINED+"WHERE e.sent_at IS NOT NULL OR e.status IN ('failed','uncertain','sending','canceled') ORDER BY e.updated_at DESC,e.id DESC LIMIT ? OFFSET ?",(limit,offset))
    @staticmethod
    def get_sent_candidates_for_replies():
        return rows(JOINED+"WHERE e.sent_at IS NOT NULL AND e.status NOT IN ('bounced','offer','no_offer')")
    @staticmethod
    def count_company_sends_since(company_id, since_iso):
        return one("SELECT COUNT(*) n FROM emails WHERE company_id=? AND julianday(sent_at)>julianday(?)", (company_id,since_iso))["n"]
    @staticmethod
    def count_sends_today():
        local = config.now().astimezone(config.TIMEZONE)
        start = local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
        end = (local.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)).astimezone(timezone.utc)
        return one("SELECT COUNT(*) n FROM emails WHERE julianday(sent_at)>=julianday(?) AND julianday(sent_at)<julianday(?)",(start.isoformat(),end.isoformat()))["n"]
    @staticmethod
    def claim_for_sending(eid):
        from delivery import claim
        return claim(eid)
    @staticmethod
    def update_sent(eid, msg_id, subject):
        from delivery import finish
        attempt = one("SELECT id FROM send_attempts WHERE email_id=? AND message_id=?", (eid,msg_id))
        if not attempt:
            raise Conflict("Send attempt is missing")
        finish(attempt["id"],"accepted")

class ProfileRepository:
    @staticmethod
    def get_profile():
        return one("SELECT * FROM profile WHERE id=1")
    @staticmethod
    def upsert_profile(full_name, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None):
        ProfileRepository.save_settings(dict(full_name=full_name,email=email,phone=phone,
            linkedin_url=linkedin_url,github_url=github_url,portfolio_url=portfolio_url))
    @staticmethod
    def get_settings():
        with get_connection() as conn:
            # Both reads must observe the same committed candidate snapshot.
            conn.execute("BEGIN")
            profile=conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
            facts=conn.execute("SELECT value FROM settings WHERE key='candidate_context'").fetchone()
        context=facts["value"] if facts else (config.CONTEXT_PATH.read_text(encoding="utf8") if config.CONTEXT_PATH.is_file() else "")
        return {"profile":dict(profile) if profile else None,"candidate_context":context}
    @staticmethod
    def save_settings(profile=None, candidate_context=None):
        with get_connection(immediate=True) as conn:
            if candidate_context is not None:
                conn.execute("INSERT INTO settings(key,value) VALUES ('candidate_context',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(candidate_context,))
            if profile is None:
                return
            conn.execute("""INSERT INTO profile(id,full_name,email,phone,linkedin_url,github_url,portfolio_url)
                VALUES (1,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET full_name=excluded.full_name,email=excluded.email,
                phone=excluded.phone,linkedin_url=excluded.linkedin_url,github_url=excluded.github_url,
                portfolio_url=excluded.portfolio_url,updated_at=?""",
                (profile["full_name"],profile.get("email"),profile.get("phone"),profile.get("linkedin_url"),
                 profile.get("github_url"),profile.get("portfolio_url"),timestamp()))
