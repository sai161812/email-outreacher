"""
Unit tests for Sender & State Machine.
"""
import pytest
from services.state_machine import can_transition, EmailStatus
from repository import CompanyRepository, ContactRepository, EmailRepository

def test_state_machine_valid_transitions():
    assert can_transition(EmailStatus.PENDING_REVIEW.value, EmailStatus.APPROVED.value)
    assert can_transition(EmailStatus.APPROVED.value, EmailStatus.SENDING.value)
    assert can_transition(EmailStatus.SENDING.value, EmailStatus.SENT.value)
    assert not can_transition(EmailStatus.DRAFT.value, EmailStatus.SENT.value)

def test_atomic_claim_prevents_duplicate_send(temp_db):
    cid = CompanyRepository.create("Test Corp", "test.com")
    ctid = ContactRepository.create(cid, "test@test.com", "Tester")
    eid = EmailRepository.create(cid, ctid, None, "Hook", "Subject", "Body", None)
    
    # Move to approved
    EmailRepository.update_status(eid, "approved")
    
    # First claim must succeed
    assert EmailRepository.claim_for_sending(eid) is True
    
    # Second claim must fail
    assert EmailRepository.claim_for_sending(eid) is False
