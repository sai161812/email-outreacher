import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
import time
import config
from repository import EmailRepository

def get_approved_queue():
    return [dict(r) for r in EmailRepository.get_approved_queue()]

def count_company_sends_this_week(company_id):
    import datetime as dt
    last_week = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
    return EmailRepository.count_company_sends_since(company_id, last_week)

def count_sends_today():
    return EmailRepository.count_sends_today()

def run_send_batch():
    queue = get_approved_queue()
    if not queue:
        return []

    if count_sends_today() >= config.MAX_SENDS_PER_DAY:
        return [{"error": "Daily send limit reached"}]

    summary = []
    
    server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
    server.starttls()
    server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)

    for item in queue:
        if count_sends_today() >= config.MAX_SENDS_PER_DAY:
            summary.append({"id": item["id"], "status": "skipped", "reason": "daily limit"})
            break
            
        if count_company_sends_this_week(item["company_id"]) >= config.MAX_COMPANY_SENDS_PER_WEEK:
            summary.append({"id": item["id"], "status": "skipped", "reason": "company weekly limit"})
            continue
            
        msg = EmailMessage()
        msg['Subject'] = item['subject']
        msg['From'] = config.GMAIL_ADDRESS
        msg['To'] = item['contact_email']
        msg.set_content(item['body'])
        
        try:
            for attempt in range(2):
                try:
                    server.send_message(msg)
                    break
                except smtplib.SMTPException as e:
                    if attempt == 1:
                        raise e
                    time.sleep(5)
            
            EmailRepository.update_status(item["id"], 'sent', set_sent_at=True)
            summary.append({"id": item["id"], "status": "sent"})
        except Exception as e:
            EmailRepository.update_status(item["id"], 'rejected')
            summary.append({"id": item["id"], "status": "failed", "reason": str(e)})

    server.quit()
    return summary
