from repository import EmailRepository

def list_pending():
    return [dict(r) for r in EmailRepository.get_pending_review()]

def approve(email_id):
    EmailRepository.update_status(email_id, 'approved', set_updated_at=True)

def reject(email_id):
    EmailRepository.update_status(email_id, 'rejected', set_updated_at=True)

def edit(email_id, subject=None, body=None, hook=None):
    EmailRepository.update_content(email_id, subject, body, hook)
