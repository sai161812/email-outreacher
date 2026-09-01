import smtplib
import ssl
import time
import random
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import make_msgid
from pathlib import Path
import config
from repository import EmailRepository, SuppressionRepository

def _get_personalized_attachment_name(company_name, original_path):
    if not company_name:
        return Path(original_path).name
    clean = "".join(c if c.isalnum() else "_" for c in company_name)
    clean = clean.strip("_")
    return f"Resume_{clean}.pdf"

def get_approved_queue():
    return [dict(r) for r in EmailRepository.get_approved_queue()]

def count_company_sends_this_week(company_id):
    last_week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    return EmailRepository.count_company_sends_since(company_id, last_week)

def count_sends_today():
    return EmailRepository.count_sends_today()

def is_in_send_window(now=None) -> bool:
    if now is None:
        now = datetime.now()
    day_str = now.strftime("%a").lower()
    in_day = day_str in config.SEND_DAYS
    in_hour = config.SEND_START_HOUR <= now.hour < config.SEND_END_HOUR
    return in_day and in_hour

def _send_one(server, to_email, subject, body, resume_path=None, company_name=None, in_reply_to=None, resume_url=None, attach_mode=None):
    if attach_mode is None:
        attach_mode = config.RESUME_ATTACH_MODE

    msg = MIMEMultipart()
    msg_id = make_msgid()
    msg["Message-ID"] = msg_id
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    if attach_mode == "link" and resume_url:
        if resume_url not in body:
            body = f"{body}\n\nResume: {resume_url}"

    msg.attach(MIMEText(body, "plain"))

    if (attach_mode == "attach" or not resume_url) and resume_path and Path(resume_path).exists():
        filename = _get_personalized_attachment_name(company_name, resume_path)
        with open(resume_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    server.sendmail(config.GMAIL_ADDRESS, to_email, msg.as_string())
    return msg_id

def run_send_batch(dry_run=False, force=True):
    if not force and not is_in_send_window():
        return [{"error": f"Outside send window ({config.SEND_START_HOUR}:00 - {config.SEND_END_HOUR}:00)"}]

    queue = get_approved_queue()
    remaining_today = config.DAILY_SEND_CAP - count_sends_today()
    summary = []

    if remaining_today <= 0:
        return [{"error": "Daily send limit reached"}]

    company_counts = {}
    cutoff_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    filtered_queue = []
    
    for item in queue:
        cid = item["company_id"]
        if cid not in company_counts:
            company_counts[cid] = EmailRepository.count_company_sends_since(cid, cutoff_7d)
        
        if company_counts[cid] >= config.MAX_PER_COMPANY_PER_WEEK:
            continue
        else:
            filtered_queue.append(item)
            company_counts[cid] += 1

    queue = filtered_queue
    batch = queue[:remaining_today]

    server = None
    if not dry_run and batch:
        context = ssl.create_default_context()
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
        server.starttls(context=context)
        server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)

    try:
        for i, item in enumerate(batch):
            if SuppressionRepository.is_suppressed(item["contact_email"]):
                summary.append({"id": item["id"], "status": "skipped", "reason": "suppressed"})
                continue

            subject = item["subject"]
            in_reply_to = None

            if item.get("follow_up_to_email_id"):
                original = EmailRepository.get_by_id(item["follow_up_to_email_id"])
                if original:
                    in_reply_to = original["message_id"]
                    orig_subj = original["subject"] or ""
                    if not subject.lower().startswith("re:"):
                        subject = f"Re: {orig_subj}" if orig_subj else f"Re: {subject}"

            if dry_run:
                summary.append({"id": item["id"], "status": "dry_run", "contact": item["contact_email"]})
                continue

            success = False
            for attempt in range(2):
                try:
                    
                    resume_path = None
                    resume_url = None
                    if item.get("resume_variant_id"):
                        from repository import ResumeRepository
                        for rv in ResumeRepository.get_all():
                            if rv["id"] == item["resume_variant_id"]:
                                resume_path = rv["file_path"]
                                resume_url = rv.get("resume_url")
                                break

                    msg_id = _send_one(
                        server,
                        item["contact_email"],
                        subject,
                        item["body"],
                        resume_path=resume_path,
                        company_name=item.get("company_name", ""),
                        in_reply_to=in_reply_to,
                        resume_url=resume_url,
                        attach_mode=config.RESUME_ATTACH_MODE,
                    )
                    
                    EmailRepository.update_sent(item["id"], msg_id, subject)
                    summary.append({"id": item["id"], "status": "sent", "contact": item["contact_email"]})
                    success = True
                    break
                except Exception as e:
                    if attempt == 0:
                        time.sleep(5)
                    else:
                        EmailRepository.update_status(item["id"], 'rejected')
                        summary.append({"id": item["id"], "status": "failed", "reason": str(e)})

            if success and i < len(batch) - 1:
                time.sleep(random.randint(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS))
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

    return summary
