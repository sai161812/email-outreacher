import hashlib
import random
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path
import config
import delivery
from errors import Conflict
from repository import EmailRepository, SuppressionRepository, event
from db import get_connection

def _get_personalized_attachment_name(company_name, original_path="resume.pdf"):
    clean="".join(c if c.isalnum() else "_" for c in (company_name or "")).strip("_")[:80]
    return f"Resume_{clean or 'Candidate'}.pdf"

def get_approved_queue():
    return EmailRepository.get_approved_queue()

def count_sends_today():
    return EmailRepository.count_sends_today()

def count_company_sends_this_week(company_id):
    from datetime import timedelta
    return EmailRepository.count_company_sends_since(company_id,(config.now()-timedelta(days=7)).isoformat())

def is_in_send_window(now=None):
    local = (now or config.now()).astimezone(config.TIMEZONE)
    return local.strftime("%a").lower() in config.SEND_DAYS and config.SEND_START_HOUR<=local.hour<config.SEND_END_HOUR

def _send_one(server,to_email,subject,body,resume_path=None,company_name=None,in_reply_to=None,
              resume_url=None,attach_mode=None,message_id=None,asset=None):
    msg=EmailMessage()
    msg["Message-ID"]=message_id or make_msgid(domain="outreach.local")
    msg["Date"]=format_datetime(config.now())
    msg["From"]=config.GMAIL_ADDRESS
    msg["To"]=to_email
    msg["Subject"]=subject
    if in_reply_to:
        msg["In-Reply-To"]=in_reply_to
        msg["References"]=in_reply_to
    mode=attach_mode or config.RESUME_ATTACH_MODE
    if asset:
        resume_path=asset.get("path")
        resume_url=asset.get("url")
    if mode=="link" and resume_url and resume_url not in body:
        body += f"\n\nResume: {resume_url}"
    msg.set_content(body)
    if mode=="attach" and resume_path:
        import resume
        _, data=resume.checked_pdf(resume_path)
        if asset and hashlib.sha256(data).hexdigest()!=asset["sha256"]:
            raise Conflict("Resume changed since approval")
        msg.add_attachment(data,maintype="application",subtype="pdf",
                           filename=_get_personalized_attachment_name(company_name,resume_path))
    elif mode=="link" and resume_path and not resume_url:
        raise ValueError("Resume link is required in link mode")
    server.sendmail(config.GMAIL_ADDRESS,to_email,msg.as_bytes())
    return msg["Message-ID"]

def run_send_batch(dry_run=False, force=False, progress=None):
    if force:
        raise ValueError("Send-window overrides are disabled; change the configured window explicitly")
    queue=get_approved_queue()
    summary=[]
    if not dry_run and queue:
        config.require_gmail_creds()
    server=None
    needs_delay=False
    projected=[]
    transport_failed=False
    try:
        for item in queue:
            eid=item["id"]
            claim=None
            try:
                if transport_failed:
                    summary.append({"id":eid,"status":"deferred","reason":"Transport setup failed earlier in this batch"})
                    continue
                if not is_in_send_window():
                    summary.append({"id":eid,"status":"deferred","reason":"Outside send window"})
                    continue
                if SuppressionRepository.is_suppressed(item["contact_email"]):
                    summary.append({"id":eid,"status":"skipped","reason":"Recipient is suppressed"})
                    continue
                if dry_run:
                    with get_connection(immediate=True) as conn:
                        row=dict(conn.execute("SELECT * FROM emails WHERE id=?",(eid,)).fetchone())
                        delivery._validate(conn,row)
                        delivery._quota(conn,row["company_id"],projected=projected)
                    projected.append(row["company_id"])
                    summary.append({"id":eid,"status":"dry_run","contact":item["contact_email"]})
                    continue
                if needs_delay:
                    time.sleep(random.randint(config.MIN_DELAY_SECONDS,config.MAX_DELAY_SECONDS))
                    needs_delay=False
                if not is_in_send_window():
                    summary.append({"id":eid,"status":"deferred","reason":"Outside send window"})
                    continue
                claim=delivery.claim(eid)
                if not claim:
                    summary.append({"id":eid,"status":"skipped","reason":"Already claimed or changed"})
                    continue
                # Establish connection before entering the submission-uncertain phase.
                if server is None:
                    server=smtplib.SMTP(config.SMTP_HOST,config.SMTP_PORT,timeout=config.PROVIDER_TIMEOUT)
                    server.starttls(context=ssl.create_default_context())
                    server.login(config.GMAIL_ADDRESS,config.GMAIL_APP_PASSWORD)
                approved=delivery.prepare(claim["attempt_id"])
                parent=EmailRepository.get_by_id(item["follow_up_to_email_id"]) if item["follow_up_to_email_id"] else None
                try:
                    needs_delay=True
                    msg_id=_send_one(server,approved["recipient"],approved["subject"],approved["body"],
                        company_name=approved["company_name"],in_reply_to=parent["message_id"] if parent else None,
                        attach_mode=approved["attach_mode"],message_id=claim["message_id"],asset=approved["resume"])
                except smtplib.SMTPRecipientsRefused as exc:
                    delivery.finish(claim["attempt_id"],"failed","recipient_refused")
                    if all(code>=500 for code,_ in exc.recipients.values()):
                        SuppressionRepository.add(approved["recipient"],"hard bounce")
                    summary.append({"id":eid,"status":"failed","reason":"Recipient refused"})
                    continue
                except (smtplib.SMTPSenderRefused,smtplib.SMTPDataError) as exc:
                    delivery.finish(claim["attempt_id"],"failed",type(exc).__name__)
                    summary.append({"id":eid,"status":"failed","reason":"SMTP rejected the message"})
                    continue
                except Exception:
                    delivery.finish(claim["attempt_id"],"uncertain","submission_interrupted")
                    summary.append({"id":eid,"status":"uncertain","reason":"Delivery requires reconciliation; automatic retry disabled"})
                    _close_transport(server)
                    server=None
                    continue
                try:
                    EmailRepository.update_sent(eid,msg_id,approved["subject"])
                    summary.append({"id":eid,"status":"sent","contact":approved["recipient"]})
                except Exception:
                    # SMTP already succeeded. Never re-enter submission.
                    try:
                        delivery.finish(claim["attempt_id"],"uncertain","acceptance_record_failed")
                    except Exception:
                        pass  # Durable 'submitting' attempt is recovered as uncertain.
                    summary.append({"id":eid,"status":"uncertain","reason":"SMTP accepted; database confirmation failed"})
            except (ValueError,Conflict) as exc:
                if claim:
                    delivery.finish(claim["attempt_id"],"canceled","preflight_failed")
                summary.append({"id":eid,"status":"deferred","reason":str(exc)})
            except Exception:
                if claim:
                    delivery.finish(claim["attempt_id"],"failed","transport_setup_failed")
                summary.append({"id":eid,"status":"failed","reason":"Mail transport unavailable; check settings"})
                transport_failed=True
            finally:
                if progress:
                    progress(summary)
    finally:
        _close_transport(server)
    return summary

def _close_transport(server):
    if server is None: return
    try:
        server.quit()
    except Exception:
        try: server.close()
        except Exception: pass
