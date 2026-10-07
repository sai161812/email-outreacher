"""Single-owner Flask API. Long-running operations are queued for worker.py."""
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask,jsonify,request,session,send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash,generate_password_hash
import config
import db
import contacts
import candidate_profile
import composer
import reviewer
import resume
import tracker
import jobs
import delivery
from errors import AppError,Conflict,NotFound
from repository import EmailRepository,SuppressionRepository,CompanyRepository,ContactRepository,rows,timestamp,event,require_email,check_revision

def payload(allowed,required=()):
    data=request.get_json()
    if not isinstance(data,dict):
        raise ValueError("JSON body must be an object")
    if set(data)-set(allowed): raise ValueError("Unknown request fields")
    if set(required)-set(data): raise ValueError("Missing required fields")
    return data

def ident(value,name="id"):
    if type(value) is not int or value<1: raise ValueError(f"{name} must be a positive integer")
    return value

def page():
    try:
        limit=int(request.args.get("limit",100));offset=int(request.args.get("offset",0))
    except ValueError as exc:
        raise ValueError("Invalid pagination") from exc
    if not 1<=limit<=500 or offset<0: raise ValueError("Invalid pagination")
    return limit,offset

def request_key():
    key=request.headers.get("Idempotency-Key","")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}",key):
        raise ValueError("Supply an Idempotency-Key (8-128 letters, digits, hyphens or underscores)")
    return key

def create_app(overrides=None):
    app=Flask(__name__,static_folder="static")
    secret=config.SECRET_KEY
    hosts={h.strip().lower() for h in os.getenv("ALLOWED_HOSTS","localhost,127.0.0.1,::1").split(",")}
    remote=hosts-{"localhost","127.0.0.1","::1"}
    if (config.OWNER_PASSWORD or remote) and (not config.OWNER_PASSWORD or len(secret)<32):
        raise ValueError("Remote/owner mode requires OWNER_PASSWORD and SECRET_KEY of at least 32 characters")
    app.config.update(SECRET_KEY=secret or secrets.token_hex(32),MAX_CONTENT_LENGTH=config.MAX_RESUME_BYTES+65536,
                      SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Strict",SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE","0")=="1")
    if overrides: app.config.update(overrides)
    db.init_db()
    owner_hash=generate_password_hash(config.OWNER_PASSWORD) if config.OWNER_PASSWORD else None
    attempts={}
    @app.before_request
    def protect():
        host=urlsplit("http://"+request.host).hostname
        if host not in hosts: return jsonify(error="Host is not allowed"),403
        session.setdefault("csrf",secrets.token_urlsafe(32))
        if request.method not in {"GET","HEAD","OPTIONS"}:
            origin=request.headers.get("Origin")
            if origin and origin!=request.host_url.rstrip("/"): return jsonify(error="Origin is not allowed"),403
            token=request.headers.get("X-CSRF-Token","")
            if not hmac.compare_digest(token,session["csrf"]): return jsonify(error="Invalid request token; reload the page"),403
        if owner_hash and request.path.startswith("/api/") and request.path not in {"/api/session","/api/login"} and not session.get("owner"):
            return jsonify(error="Sign in required"),401
    @app.after_request
    def headers(response):
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="same-origin"
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
    @app.errorhandler(AppError)
    def app_error(exc): return jsonify(error=str(exc)),exc.status
    @app.errorhandler(ValueError)
    def invalid(exc): return jsonify(error=str(exc)),400
    @app.errorhandler(HTTPException)
    def http_error(exc): return jsonify(error=exc.description),exc.code
    @app.errorhandler(sqlite3.IntegrityError)
    def integrity(exc): return jsonify(error="Data conflicts with an existing record or relationship"),409
    @app.errorhandler(Exception)
    def unexpected(exc):
        logging.error("request_failed path=%s type=%s",request.path,type(exc).__name__)
        return jsonify(error="Unexpected failure; check server diagnostics"),500
    @app.get("/")
    def index(): return send_from_directory(app.static_folder,"index.html")
    @app.get("/api/session")
    def session_info():
        return jsonify(csrf=session["csrf"],authenticated=not owner_hash or bool(session.get("owner")),owner_mode=bool(owner_hash))
    @app.post("/api/login")
    def login():
        data=payload({"password"},{"password"})
        address=request.remote_addr or "unknown"
        recent=[t for t in attempts.get(address,[]) if time.monotonic()-t<300]
        attempts[address]=recent
        if len(recent)>=5: return jsonify(error="Too many attempts; try again in five minutes"),429
        if not isinstance(data["password"],str) or not owner_hash or not check_password_hash(owner_hash,data["password"]):
            recent.append(time.monotonic())
            return jsonify(error="Invalid password"),401
        session.clear();session["owner"]=True;session["csrf"]=secrets.token_urlsafe(32)
        attempts.pop(address,None)
        return jsonify(success=True,csrf=session["csrf"])
    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(success=True)
    @app.get("/api/stats")
    def stats(): return jsonify(summary=tracker.pipeline_summary(),stats=tracker.stats())
    @app.get("/api/settings")
    def settings():
        from zoneinfo import ZoneInfo
        readiness={"gemini":bool(config.GEMINI_API_KEY),"gmail":bool(config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD),
                   "profile":bool(candidate_profile.get_profile()),"context":config.CONTEXT_PATH.is_file()}
        return jsonify(profile=candidate_profile.get_profile(),candidate_context=config.CONTEXT_PATH.read_text(encoding="utf8") if config.CONTEXT_PATH.is_file() else "",
            resumes=resume.list_resume_variants(),suppressions=SuppressionRepository.get_all(),readiness=readiness,
            configuration={"model":config.GEMINI_MODEL,"timezone":config.TIMEZONE_NAME,"daily_cap":config.DAILY_SEND_CAP,
                           "company_weekly_cap":config.MAX_PER_COMPANY_PER_WEEK,"resume_mode":config.RESUME_ATTACH_MODE},
            migration_reports=rows("SELECT * FROM migration_reports WHERE count>0"),
            worker=rows("SELECT value FROM settings WHERE key='worker_heartbeat'"))
    @app.post("/api/settings")
    def save_settings():
        data=payload({"profile","candidate_context"})
        if "candidate_context" in data:
            context=contacts.text(data["candidate_context"],"candidate_context",True,20000)
            temporary=config.CONTEXT_PATH.with_name(config.CONTEXT_PATH.name+"."+uuid.uuid4().hex+".tmp")
            temporary.parent.mkdir(parents=True,exist_ok=True)
            try:
                temporary.write_text(context,encoding="utf8")
                temporary.replace(config.CONTEXT_PATH)
            finally:
                temporary.unlink(missing_ok=True)
        if "profile" in data:
            profile=data["profile"]
            if not isinstance(profile,dict) or set(profile)-{"full_name","email","phone","linkedin_url","github_url","portfolio_url"} or "full_name" not in profile:
                raise ValueError("Invalid profile fields")
            candidate_profile.set_profile(**profile)
        return jsonify(success=True)
    @app.get("/api/companies")
    def companies(): return jsonify(contacts.list_companies())
    @app.post("/api/companies")
    def add_company():
        data=payload({"name","domain","job_url","job_text","notes"},{"name"})
        return jsonify(id=contacts.add_company(**data)),201
    @app.get("/api/contacts")
    def contact_list():
        limit,offset=page()
        company=request.args.get("company_id")
        if company:
            try: company=ident(int(company),"company_id")
            except (ValueError,TypeError): raise ValueError("Invalid company_id")
        return jsonify(contacts.list_contacts(company,limit,offset,request.args.get("search","")[:200]))
    @app.post("/api/contacts")
    def add_contact():
        data=payload({"company_id","email","name","title","source"},{"company_id","email"})
        ident(data["company_id"],"company_id")
        return jsonify(id=contacts.add_contact(**data)),201
    @app.post("/api/contacts/import")
    def import_contacts():
        file=request.files.get("file")
        if not file or not file.filename or not file.filename.lower().endswith(".csv"):
            raise ValueError("Upload a CSV file")
        raw=file.stream.read(config.MAX_UPLOAD_BYTES+1)
        if len(raw)>config.MAX_UPLOAD_BYTES: return jsonify(error="CSV exceeds upload size limit"),413
        try: text=raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc: raise ValueError("CSV must use UTF-8 encoding") from exc
        return jsonify(contacts.import_stream(io.StringIO(text,newline="")))
    @app.post("/api/resumes")
    def add_resume():
        if request.is_json:
            data=payload({"name","keywords","resume_url"},{"name","resume_url"})
            return jsonify(id=resume.add_resume_variant(**data)),201
        file=request.files.get("file")
        if not file or not file.filename or not file.filename.lower().endswith(".pdf"): raise ValueError("Upload a PDF")
        content=file.stream.read(config.MAX_RESUME_BYTES+1)
        if len(content)>config.MAX_RESUME_BYTES: return jsonify(error="Resume exceeds upload size limit"),413
        if not content.startswith(b"%PDF-"): raise ValueError("Resume must be a PDF")
        config.RESUME_DIR.mkdir(parents=True,exist_ok=True)
        target=config.RESUME_DIR/(uuid.uuid4().hex+".pdf")
        target.write_bytes(content)
        try:
            rid=resume.add_resume_variant(request.form.get("name",""),request.form.get("keywords",""),str(target),request.form.get("resume_url"))
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return jsonify(id=rid),201
    @app.get("/api/resumes/<int:rid>/pdf")
    def resume_pdf(rid):
        variant=resume.get_variant(rid)
        path,_=resume.checked_pdf(variant["file_path"])
        return send_from_directory(path.parent,path.name,mimetype="application/pdf",as_attachment=True,download_name="resume.pdf")
    @app.post("/api/suppressions")
    def suppress():
        from validate import canonical_email
        data=payload({"email","reason"},{"email","reason"})
        SuppressionRepository.add(canonical_email(data["email"]),contacts.text(data["reason"],"reason",True,500))
        return jsonify(success=True)
    @app.delete("/api/suppressions")
    def unsuppress():
        from validate import canonical_email
        data=payload({"email"},{"email"})
        SuppressionRepository.remove(canonical_email(data["email"]))
        return jsonify(success=True)
    @app.get("/api/review")
    def review_list(): return jsonify(reviewer.list_pending(*page()))
    @app.get("/api/queue")
    def queue(): return jsonify(EmailRepository.get_approved_queue())
    @app.post("/api/review/<int:eid>")
    def review_action(eid):
        data=payload({"action","revision","subject","body","hook","resume_variant_id"},{"action","revision"})
        ident(data["revision"],"revision")
        if data["action"]=="approve":
            if set(data)-{"action","revision"}: raise ValueError("Save visible edits before approving")
            reviewer.approve(eid,data["revision"])
        elif data["action"]=="reject": reviewer.reject(eid,data["revision"])
        elif data["action"]=="edit":
            if "resume_variant_id" in data and data["resume_variant_id"] is not None:
                resume.delivery_asset(ident(data["resume_variant_id"],"resume_variant_id"))
            reviewer.edit(eid,subject=data.get("subject"),body=data.get("body"),hook=data.get("hook"),
                expected_revision=data["revision"],resume_variant_id=data.get("resume_variant_id"),change_resume="resume_variant_id" in data)
        else: raise ValueError("Unknown review action")
        return jsonify(success=True,email=EmailRepository.get_by_id(eid))
    @app.get("/api/tracking")
    def tracking(): return jsonify(EmailRepository.get_all_tracked_emails(*page()))
    @app.get("/api/tracking/due")
    def due(): return jsonify(tracker.due_for_follow_up())
    @app.post("/api/tracking/<int:eid>/mark")
    def mark(eid):
        data=payload({"status"},{"status"})
        actions={"replied":tracker.mark_replied,"ghosted":tracker.mark_ghosted,"bounced":tracker.mark_bounced,
                 "interview_scheduled":tracker.mark_interview_scheduled,"interview_completed":tracker.mark_interview_completed,
                 "offer":tracker.mark_offer,"no_offer":tracker.mark_no_offer}
        if not isinstance(data["status"],str) or data["status"] not in actions: raise ValueError("Unknown tracking action")
        actions[data["status"]](eid)
        return jsonify(success=True)
    @app.post("/api/compose")
    def compose():
        data=payload({"company_id","contact_id","resume_variant_id"},{"company_id","contact_id"})
        for name in ("company_id","contact_id"): ident(data[name],name)
        company=contacts.get_company(data["company_id"]);contact=contacts.get_contact(data["contact_id"])
        if contact["company_id"]!=company["id"]: raise Conflict("Contact does not belong to company")
        if "resume_variant_id" not in data:
            selected=resume.pick_best_variant(company.get("job_text"))
            data["resume_variant_id"]=selected["id"] if selected else None
        if data["resume_variant_id"] is not None: resume.delivery_asset(ident(data["resume_variant_id"],"resume_variant_id"))
        return jsonify(jobs.enqueue("compose",data,request_key())),202
    @app.post("/api/tracking/<int:eid>/followup")
    def followup(eid):
        payload(set())
        original=EmailRepository.get_by_id(eid)
        if not original: raise NotFound("Email not found")
        import followups
        with db.get_connection() as conn: followups.check(conn,{**original,"follow_up_to_email_id":eid})
        return jsonify(jobs.enqueue("followup",{"email_id":eid},request_key())),202
    @app.post("/api/send")
    def send():
        data=payload({"dry_run"})
        if "dry_run" in data and type(data["dry_run"]) is not bool: raise ValueError("dry_run must be boolean")
        return jsonify(jobs.enqueue("send",data,request_key())),202
    @app.post("/api/check_replies")
    def check_replies():
        payload(set())
        return jsonify(jobs.enqueue("replies",{},request_key())),202
    @app.get("/api/jobs")
    def job_list(): return jsonify(jobs.list_jobs())
    @app.get("/api/jobs/<int:jid>")
    def job(jid): return jsonify(jobs.get(jid))
    @app.get("/api/attempts")
    def attempts_list():
        return jsonify(rows("SELECT * FROM send_attempts WHERE state IN ('failed','uncertain','reserved','submitting') ORDER BY id DESC LIMIT 100"))
    @app.post("/api/attempts/<int:aid>/reconcile")
    def reconcile(aid):
        data=payload({"accepted"},{"accepted"})
        if type(data["accepted"]) is not bool: raise ValueError("accepted must be boolean")
        delivery.reconcile(aid,data["accepted"])
        return jsonify(success=True)
    @app.post("/api/emails/<int:eid>/retry")
    def retry(eid):
        payload(set())
        row=EmailRepository.get_by_id(eid)
        if not row: raise NotFound("Email not found")
        if row["status"]!="failed" or row["sent_at"]: raise Conflict("Only definitely failed unsent messages can be reviewed again")
        reviewer.edit(eid,expected_revision=row["revision"])
        return jsonify(success=True)
    @app.patch("/api/contacts/<int:cid>")
    def edit_contact(cid):
        data=payload({"email","name","title","source","archived"})
        original=contacts.get_contact(cid)
        if "email" in data:
            from validate import canonical_email
            data["email"]=canonical_email(data["email"])
            if data["email"]!=original["email"] and any(e["sent_at"] for e in EmailRepository.get_by_contact_id(cid)):
                raise Conflict("Create a new contact to change an address with send history")
        for field in ("name","title","source"):
            if field in data: data[field]=contacts.text(data[field],field,maximum=500)
        if "archived" in data:
            if type(data["archived"]) is not bool: raise ValueError("archived must be boolean")
            data["archived"]=int(data["archived"])
        if not data: raise ValueError("No changes supplied")
        with db.get_connection(immediate=True) as conn:
            conn.execute("UPDATE contacts SET "+",".join(f"{k}=?" for k in data)+" WHERE id=?",(*data.values(),cid))
            conn.execute("UPDATE emails SET status='pending_review',approval_json=NULL,revision=revision+1 WHERE contact_id=? AND status='approved'",(cid,))
        return jsonify(success=True)
    @app.patch("/api/companies/<int:cid>")
    def edit_company(cid):
        data=payload({"name","domain","job_url","job_text","notes"})
        contacts.get_company(cid)
        for field in data:
            if field=="name": data[field]=contacts.normalize_company_name(contacts.text(data[field],field,True,200))
            elif field=="domain": data[field]=contacts.domain_name(data[field])
            elif field=="job_url": data[field]=resume.safe_url(data[field])
            else: data[field]=contacts.text(data[field],field,maximum=20000)
        if not data: raise ValueError("No changes supplied")
        with db.get_connection(immediate=True) as conn:
            conn.execute("UPDATE companies SET "+",".join(f"{k}=?" for k in data)+" WHERE id=?",(*data.values(),cid))
            conn.execute("UPDATE emails SET status='pending_review',approval_json=NULL,revision=revision+1 WHERE company_id=? AND status='approved'",(cid,))
        return jsonify(success=True)
    return app

# Flask/Waitress discovery initializes the schema through the same supported factory.
app=create_app()

if __name__=="__main__":
    app.run(host="127.0.0.1",port=5000,debug=False)
