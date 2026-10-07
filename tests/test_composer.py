import json
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
import config
import composer
import candidate_profile
import resume
from repository import EmailRepository
from errors import Conflict,ProviderError

@pytest.fixture
def ready(contact,monkeypatch):
    candidate_profile.set_profile("Candidate")
    config.CONTEXT_PATH.write_text("Built a Python dashboard.",encoding="utf8")
    draft={"subject":"Your dashboard","hook":"A verifiable hook","body":"I built a Python dashboard. Open to a brief chat?","research_notes":"Source: https://example.test","grounding":[{"web_search_queries":["test"]}]}
    monkeypatch.setattr(composer,"compose_email",lambda *args:draft)
    return contact

def test_persists_sources_and_safe_body(ready):
    company,person=ready
    eid=composer.compose_and_store(company,person,composer.candidate_context())
    row=EmailRepository.get_by_id(eid)
    assert row["status"]=="pending_review"
    assert row["research_notes"]=="Source: https://example.test"
    assert json.loads(row["grounding_json"])[0]["web_search_queries"]==["test"]
    assert row["body"].startswith("Hi Person,")
    with pytest.raises(Conflict):
        composer.compose_and_store(company,person,composer.candidate_context())

def test_assigned_resume_drafts(ready):
    pdf=config.RESUME_DIR/"cv.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfixture")
    rid=resume.add_resume_variant("CV","python",str(pdf))
    company,person=ready
    eid=composer.compose_and_store(company,person,composer.candidate_context(),rid)
    assert EmailRepository.get_by_id(eid)["resume_variant_id"]==rid

def test_failure_does_not_store_sendable_draft(ready,monkeypatch):
    company,person=ready
    monkeypatch.setattr(composer,"compose_email",Mock(side_effect=ProviderError("Failed")))
    with pytest.raises(ProviderError):
        composer.compose_and_store(company,person,composer.candidate_context())
    assert EmailRepository.get_by_contact_id(person)==[]

def test_invalid_generated_text_not_stored(ready,monkeypatch):
    company,person=ready
    monkeypatch.setattr(composer,"compose_email",lambda *a:{"subject":"S","hook":"H","body":"[Your Name]","research_notes":"Unknown"})
    with pytest.raises(ProviderError):
        composer.compose_and_store(company,person,composer.candidate_context())
    assert EmailRepository.get_by_contact_id(person)==[]

def test_concurrent_generation_reserved(ready,monkeypatch):
    company,person=ready
    entered=Event(); release=Event()
    original=composer.compose_email
    def slow(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(composer,"compose_email",slow)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future=pool.submit(composer.compose_and_store,company,person,composer.candidate_context())
        assert entered.wait(5)
        with pytest.raises(Conflict):
            composer.compose_and_store(company,person,composer.candidate_context())
        release.set()
        assert future.result()
    assert len(EmailRepository.get_by_contact_id(person))==1

def test_missing_profile_blocks_provider(contact,monkeypatch):
    company,person=contact
    provider=Mock()
    monkeypatch.setattr(composer,"compose_email",provider)
    with pytest.raises(ValueError,match="profile"):
        composer.compose_and_store(company,person,"A verified fact")
    provider.assert_not_called()

def test_provider_parse_failure_closes_client(ready,monkeypatch):
    fake=Mock()
    fake.models.generate_content.return_value=Mock(parsed=None,candidates=[])
    monkeypatch.setattr(config,"GEMINI_API_KEY","test-key")
    monkeypatch.setattr(composer.genai,"Client",Mock(return_value=fake))
    with pytest.raises(ProviderError):
        composer._generate("test",composer.EmailDraft,composer.SYSTEM_PROMPT)
    fake.close.assert_called_once()

def test_followup_prompt_forbids_invention():
    assert "Never invent" in composer.FOLLOW_UP_SYSTEM_PROMPT
    assert "first-year" not in composer.SYSTEM_PROMPT
