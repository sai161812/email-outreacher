"""Email lifecycle rules shared by review, tracking and delivery."""
from enum import StrEnum

class EmailStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SENDING = "sending"
    SENT = "sent"

TRANSITIONS = {
    "pending_review": {"approved","rejected","canceled"},
    "approved": {"pending_review","rejected","sending","canceled"},
    "sending": {"sent","failed","uncertain","canceled"},
    "failed": {"pending_review","canceled"},
    "uncertain": {"sent","failed"},
    "sent": {"replied","ghosted","bounced","interview_scheduled","interview_completed","offer","no_offer"},
    "ghosted": {"replied","bounced","interview_scheduled","interview_completed","offer","no_offer"},
    "replied": {"interview_scheduled","interview_completed","offer","no_offer"},
    "interview_scheduled": {"interview_completed","offer","no_offer"},
    "interview_completed": {"offer","no_offer"},
    "rejected": {"pending_review"},
    "canceled": set(), "bounced": set(), "offer": set(), "no_offer": set()
}
def can_transition(current, target):
    return target in TRANSITIONS.get(current, set())
