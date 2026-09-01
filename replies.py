import imaplib
import email
from email.header import decode_header
import config
from repository import EmailRepository

def check_replies(dry_run=False):
    candidates = EmailRepository.get_sent_candidates_for_replies()
    if not candidates:
        return []

    mail = imaplib.IMAP4_SSL(config.IMAP_HOST)
    mail.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
    mail.select("INBOX")
    
    summary = []
    
    for c in candidates:
        email_id = c["id"]
        msg_id = c["message_id"]
        contact_email = c["contact_email"]
        
        found = False
        
        if msg_id:
            search_crit = f'(HEADER References "{msg_id}")'
            status, data = mail.search(None, search_crit)
            if data[0]:
                found = True
        
        if not found:
            status, data = mail.search(None, f'(FROM "{contact_email}")')
            if data[0]:
                found = True
                
        if found:
            if not dry_run:
                EmailRepository.update_status(email_id, 'replied', set_updated_at=True)
            summary.append({"id": email_id, "contact_email": contact_email, "status": "replied"})
            
    mail.logout()
    return summary
