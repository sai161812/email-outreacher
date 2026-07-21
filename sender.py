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
from pathlib import Path

import config
from db import get_connection


def _sent_today_count():
    today = date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM emails WHERE status IN ('sent','replied','ghosted','bounced') "
            "AND date(sent_at) = ?",
            (today,),
        ).fetchone()
        return row["n"]


def get_approved_queue():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.*, c.email as contact_email, rv.file_path as resume_path "
            "FROM emails e "
            "JOIN contacts c ON e.contact_id = c.id "
            "LEFT JOIN resume_variants rv ON e.resume_variant_id = rv.id "
            "WHERE e.status = 'approved' "
            "ORDER BY e.updated_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def _send_one(to_email, subject, body, resume_path=None):
    config.require_gmail_creds()
    msg = MIMEMultipart()
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if resume_path and Path(resume_path).exists():
        with open(resume_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=Path(resume_path).name)
        part["Content-Disposition"] = f'attachment; filename="{Path(resume_path).name}"'
        msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_ADDRESS, to_email, msg.as_string())


def run_send_batch(dry_run=False):
    """
    Sends everything in the 'approved' queue, up to the daily cap,
    with a randomized delay between each send. Returns a summary list.
    """
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
        if dry_run:
            print(f"[DRY RUN] Would send to {item['contact_email']} — {item['subject']}")
            summary.append((item["id"], "dry_run"))
            continue

        try:
            _send_one(item["contact_email"], item["subject"], item["body"], item.get("resume_path"))
            with get_connection() as conn:
                conn.execute(
                    "UPDATE emails SET status = 'sent', sent_at = ?, updated_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), item["id"]),
                )
            print(f"Sent to {item['contact_email']} ({item['subject']})")
            summary.append((item["id"], "sent"))
        except Exception as e:
            print(f"FAILED to send to {item['contact_email']}: {e}")
            summary.append((item["id"], f"error: {e}"))

        if i < len(batch) - 1:
            delay = random.randint(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
            print(f"Waiting {delay}s before next send...")
            time.sleep(delay)

    return summary
