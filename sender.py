"""
Sends approved emails via Gmail SMTP. Enforces a daily cap and a random
delay between sends — this exists specifically to protect your account's
sender reputation. Do not remove the cap/delay to "send faster."
"""
import random
import smtplib
import ssl
import time
from datetime import datetime, date, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import make_msgid
from pathlib import Path

import config
from db import get_connection
import validate


def _sent_today_count():
    today = date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM emails WHERE status IN ('sent','replied','ghosted','bounced') "
            "AND date(sent_at) = ?",
            (today,),
        ).fetchone()
        return row["n"]


import re
import profile


def _get_personalized_attachment_name(company_name, fallback_path):
    p = profile.get_profile()
    name_prefix = "Resume"
    if p and p.get("full_name"):
        parts = [re.sub(r"[^\w\-]", "", part) for part in p["full_name"].strip().split() if part.strip()]
        if len(parts) >= 2:
            name_prefix = f"{parts[0]}_{parts[-1]}_Resume"
        elif len(parts) == 1:
            name_prefix = f"{parts[0]}_Resume"
            
    clean_company = re.sub(r"[^\w\-]", "", (company_name or "").strip())
    if clean_company:
        return f"{name_prefix}_{clean_company}.pdf"
    return f"{name_prefix}.pdf" if name_prefix != "Resume" else Path(fallback_path).name


def get_approved_queue():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.*, c.name as company_name, ct.name as contact_name, ct.email as contact_email, "
            "rv.file_path as resume_path, rv.resume_url "
            "FROM emails e "
            "JOIN companies c ON e.company_id = c.id "
            "JOIN contacts ct ON e.contact_id = ct.id "
            "LEFT JOIN resume_variants rv ON e.resume_variant_id = rv.id "
            "WHERE e.status = 'approved' "
            "ORDER BY e.updated_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def _send_one(to_email, subject, body, resume_path=None, company_name=None, in_reply_to=None):
    config.require_gmail_creds()
    msg = MIMEMultipart()
    msg_id = make_msgid()
    msg["Message-ID"] = msg_id
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    msg.attach(MIMEText(body, "plain"))

    if config.RESUME_ATTACH_MODE == "attach" and resume_path and Path(resume_path).exists():
        filename = _get_personalized_attachment_name(company_name, resume_path)
        with open(resume_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_ADDRESS, to_email, msg.as_string())

def is_in_send_window(now=None) -> bool:
    """
    Checks if current local time is within the allowed send-time window.
    """
    if now is None:
        now = datetime.now()
    day_str = now.strftime("%a").lower()
    in_day = day_str in config.SEND_DAYS
    in_hour = config.SEND_START_HOUR <= now.hour < config.SEND_END_HOUR
    return in_day and in_hour


def run_send_batch(dry_run=False, force=False):
    """
    Sends everything in the 'approved' queue, up to the daily cap,
    with a randomized delay between each send. Returns a summary list.
    """
    if not force and not is_in_send_window():
        print(
            f"Outside send window ({config.SEND_START_HOUR}:00 - {config.SEND_END_HOUR}:00, "
            f"{', '.join(config.SEND_DAYS)}). Use --force to override."
        )
        return []

    queue = get_approved_queue()
    remaining_today = config.DAILY_SEND_CAP - _sent_today_count()
    summary = []

    if remaining_today <= 0:
        print(f"Daily cap of {config.DAILY_SEND_CAP} already reached. Nothing sent.")
        return summary

    batch = queue[:remaining_today]
    if len(queue) > len(batch):
        print(f"{len(queue) - len(batch)} approved emails held back — daily cap reached.")

    for i, item in enumerate(batch):
        subject = item["subject"]
        in_reply_to = None

        if item.get("follow_up_to_email_id"):
            with get_connection() as conn:
                original = conn.execute(
                    "SELECT message_id, subject FROM emails WHERE id = ?",
                    (item["follow_up_to_email_id"],)
                ).fetchone()
                if original:
                    in_reply_to = original["message_id"]
                    orig_subj = original["subject"] or ""
                    if not subject.lower().startswith("re:"):
                        subject = f"Re: {orig_subj}" if orig_subj else f"Re: {subject}"

        if not validate.validate_email_syntax(item["contact_email"]):
            print(f"Skipping #{item['id']}: invalid email format '{item['contact_email']}'")
            summary.append((item["id"], "error: invalid email format"))
            continue

        if dry_run:
            print(f"[DRY RUN] Would send to {item['contact_email']} — {subject}")
            summary.append((item["id"], "dry_run"))
            continue

        try:
            msg_id = _send_one(
                item["contact_email"],
                subject,
                item["body"],
                item.get("resume_path"),
                item.get("company_name"),
                in_reply_to=in_reply_to
            )
            with get_connection() as conn:
                conn.execute(
                    "UPDATE emails SET status = 'sent', sent_at = ?, updated_at = ?, message_id = ?, subject = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), msg_id, subject, item["id"]),
                )
            print(f"Sent to {item['contact_email']} ({subject})")
            summary.append((item["id"], "sent"))
        except Exception as e:
            print(f"FAILED to send to {item['contact_email']}: {e}")
            summary.append((item["id"], f"error: {e}"))

        if i < len(batch) - 1:
            delay = random.randint(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
            print(f"Waiting {delay}s before next send...")
            time.sleep(delay)

    return summary
