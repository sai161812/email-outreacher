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
from test_writing_quality import STRONG_PITCH,STRONG_FOLLOWUP

@pytest.fixture
def ready(contact,monkeypatch):
    candidate_profile.set_profile("Candidate")
    config.CONTEXT_PATH.write_text("Target: entry-level backend engineering. Built a personal Python dashboard that validates CSV imports, queries SQLite and presents weekly usage summaries. No paid experience or measured business results.",encoding="utf8")
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

def test_real_sdk_response_contract_and_retry(ready,monkeypatch):
    from google.genai import types,errors
    fake=Mock()
    response=types.GenerateContentResponse(
        parsed=composer.EmailDraft(hook="Verified fact",subject="Backend engineering at Example",body=STRONG_PITCH,research_notes="Verify https://example.test"),
        candidates=[types.Candidate(grounding_metadata=types.GroundingMetadata(web_search_queries=["company"]))])
    fake.models.generate_content.side_effect=[errors.ServerError(503,{"error":{"message":"synthetic"}}),response]
    monkeypatch.setattr(config,"GEMINI_API_KEY","synthetic")
    monkeypatch.setattr(composer.genai,"Client",Mock(return_value=fake))
    monkeypatch.setattr(composer.time,"sleep",lambda _:None)
    result=composer._generate("synthetic",composer.EmailDraft,composer.SYSTEM_PROMPT,True)
    assert result["grounding"][0]["web_search_queries"]==["company"]
    assert fake.models.generate_content.call_count==2
    kwargs=fake.models.generate_content.call_args.kwargs
    assert kwargs["model"]==config.GEMINI_MODEL
    assert kwargs["config"].tools[0].google_search is not None
    fake.close.assert_called_once()

def test_provider_auth_error_is_not_retried(ready,monkeypatch):
    from google.genai import errors
    fake=Mock()
    fake.models.generate_content.side_effect=errors.ClientError(401,{"error":{"message":"synthetic"}})
    monkeypatch.setattr(config,"GEMINI_API_KEY","synthetic")
    monkeypatch.setattr(composer.genai,"Client",Mock(return_value=fake))
    with pytest.raises(ProviderError):
        composer._generate("synthetic",composer.EmailDraft,composer.SYSTEM_PROMPT)
    assert fake.models.generate_content.call_count==1
    fake.close.assert_called_once()

@pytest.fixture
def ai_client(monkeypatch):
    fake=Mock()
    factory=Mock(return_value=fake)
    monkeypatch.setattr(config,"GEMINI_API_KEY","synthetic")
    monkeypatch.setattr(composer.genai,"Client",factory)
    monkeypatch.setattr(composer.time,"sleep",lambda _:None)
    return fake,factory

def response(body=STRONG_PITCH,subject="Backend engineering at Example",grounding=False,follow_up=False):
    from google.genai import types
    draft=composer.FollowUpDraft(subject=subject,body=body) if follow_up else composer.EmailDraft(
        hook="Python data tooling matches the role",subject=subject,body=body,
        research_notes="Company source: https://example.test/careers. Candidate proof: Python CSV dashboard. Shared keywords: Python, data tools.")
    return types.GenerateContentResponse(parsed=draft,candidates=[types.Candidate(
        grounding_metadata=types.GroundingMetadata(web_search_queries=["Example careers"]))] if grounding else [])

def test_clean_pitch_uses_one_request_with_sdk_retries_disabled(ai_client):
    fake,factory=ai_client
    fake.models.generate_content.return_value=response()
    result=composer._generate("source facts",composer.EmailDraft,composer.SYSTEM_PROMPT,True)
    assert result["body"]==STRONG_PITCH
    assert result["quality_warnings"]==[]
    assert fake.models.generate_content.call_count==1
    options=factory.call_args.kwargs["http_options"]
    assert options.retry_options.attempts==1
    assert options.timeout==config.PROVIDER_TIMEOUT*1000
    fake.close.assert_called_once()

def test_weak_pitch_is_revised_with_original_facts_and_sources(ai_client):
    fake,_=ai_client
    fake.models.generate_content.side_effect=[response("I hope this email finds you well. I'm a perfect fit. Can we chat?",grounding=True),response()]
    original=composer._build_user_prompt({"name":"Example","job_text":"Python data tools"},{"title":"Technical Recruiter"},"Built a Python CSV dashboard.")
    result=composer._generate(original,composer.EmailDraft,composer.SYSTEM_PROMPT,True)
    assert fake.models.generate_content.call_count==2
    revision=json.loads(fake.models.generate_content.call_args.kwargs["contents"])
    assert revision["source_request"]==original
    assert "perfect fit" in revision["previous_draft_untrusted"]["body"]
    assert any("generic filler" in note for note in revision["writing_feedback"])
    assert result["body"]==STRONG_PITCH
    assert result["quality_warnings"]==[]
    assert result["grounding"][0]["web_search_queries"]==["Example careers"]

def test_sparse_facts_return_reviewable_warnings_after_one_revision(ai_client):
    fake,_=ai_client
    fake.models.generate_content.return_value=response("I built a Python dashboard. Could you advise on the application route?")
    result=composer._generate("Only a Python dashboard is confirmed",composer.EmailDraft,composer.SYSTEM_PROMPT)
    assert fake.models.generate_content.call_count==2
    assert any("target 80-120" in note for note in result["quality_warnings"])
    assert "Python dashboard" in result["body"]

def test_structural_failure_can_be_repaired_once(ai_client):
    from google.genai import types
    fake,_=ai_client
    fake.models.generate_content.side_effect=[types.GenerateContentResponse(parsed=None,candidates=[]),response()]
    assert composer._generate("candidate facts",composer.EmailDraft,composer.SYSTEM_PROMPT)["body"]==STRONG_PITCH
    assert fake.models.generate_content.call_count==2

def test_remaining_hard_blocker_fails_after_one_revision(ai_client):
    fake,_=ai_client
    fake.models.generate_content.return_value=response("I built [Project Name]. Could we talk?")
    with pytest.raises(ProviderError,match="still fails content checks"):
        composer._generate("facts",composer.EmailDraft,composer.SYSTEM_PROMPT)
    assert fake.models.generate_content.call_count==2
    fake.close.assert_called_once()

def test_transient_retry_and_revision_share_a_three_request_budget(ai_client):
    from google.genai import errors
    fake,_=ai_client
    fake.models.generate_content.side_effect=[
        response("I am writing to say I'm a perfect fit. Can we talk?"),
        errors.ServerError(503,{"error":{"message":"synthetic"}}),response()]
    result=composer._generate("facts",composer.EmailDraft,composer.SYSTEM_PROMPT)
    assert result["quality_warnings"]==[]
    assert fake.models.generate_content.call_count==3

def test_repeated_transient_errors_stop_without_an_unbounded_retry(ai_client):
    from google.genai import errors
    fake,_=ai_client
    fake.models.generate_content.side_effect=errors.ServerError(503,{"error":{"message":"synthetic"}})
    with pytest.raises(ProviderError):
        composer._generate("facts",composer.EmailDraft,composer.SYSTEM_PROMPT)
    assert fake.models.generate_content.call_count==2

def test_followup_has_its_own_budget_and_pressure_check(ai_client):
    fake,_=ai_client
    fake.models.generate_content.side_effect=[
        response("As per my last email, you have not replied. Can you respond?",follow_up=True),
        response(STRONG_FOLLOWUP,subject="Re: Backend engineering at Example",follow_up=True)]
    result=composer._generate("original thread and facts",composer.FollowUpDraft,composer.FOLLOW_UP_SYSTEM_PROMPT)
    assert result["body"]==STRONG_FOLLOWUP
    assert result["quality_warnings"]==[]
    assert fake.models.generate_content.call_count==2

@pytest.mark.parametrize("title,audience",[("Technical Recruiter","Recruiter/HR"),("Head of Talent Acquisition","Recruiter/HR"),("HR Partner","Recruiter/HR"),("Co-founder / CTO","Manager/founder"),("Engineering Manager","Manager/founder"),("Frontend Engineer","role unknown"),(None,"role unknown")])
def test_prompt_uses_recipient_role_without_leaking_contact_address(title,audience):
    payload=json.loads(composer._build_user_prompt({"id":1,"name":"Example","job_text":"Python"},
        {"email":"private@example.test","name":"Person","title":title},"Personal Python project; not paid experience"))
    assert audience in payload["audience_guidance"]
    assert payload["verified_candidate_facts"]=="Personal Python project; not paid experience"
    assert "email" not in payload["recipient"]
    assert "id" not in payload["company"]

@pytest.mark.parametrize("name,greeting",[(None,"Hello,"),("Maya Singh","Hi Maya,"),("Dr. Maya Singh","Hello Dr. Maya Singh,"),("Hiring Team","Hello Hiring Team,")])
def test_app_owns_greeting_signature_and_preserves_pitch(ready,name,greeting):
    body=composer._body("Hi Wrong Name,\n\n"+STRONG_PITCH+"\n\nBest,\nWrong Sender",{"name":name})
    assert body.startswith(greeting+"\n\n")
    assert STRONG_PITCH in body
    assert body.endswith("Best,\nCandidate")
    assert "Wrong Name" not in body and "Wrong Sender" not in body

def test_quality_suggestions_persist_on_pending_draft(ready,ai_client,monkeypatch):
    company,person=ready
    fake,_=ai_client
    fake.models.generate_content.return_value=response("I built a Python dashboard. Could you advise on the application route?")
    monkeypatch.setattr(composer,"compose_email",lambda company,contact,context:composer._generate(
        composer._build_user_prompt(company,contact,context),composer.EmailDraft,composer.SYSTEM_PROMPT,True))
    eid=composer.compose_and_store(company,person,composer.candidate_context())
    draft=EmailRepository.get_by_id(eid)
    assert draft["status"]=="pending_review"
    assert draft["approval_json"] is None
    assert "target 80-120" in draft["qc_warnings"]
    assert fake.models.generate_content.call_count==2

def test_generation_reservation_covers_all_timeout_bounded_calls(ready,monkeypatch):
    from datetime import datetime
    from repository import rows
    monkeypatch.setattr(config,"PROVIDER_TIMEOUT",300)
    key="generation:reservation-test"
    token=composer._reserve(key)
    value=json.loads(rows("SELECT value FROM settings WHERE key=?",(key,))[0]["value"])
    remaining=(datetime.fromisoformat(value["expires"])-config.now()).total_seconds()
    assert remaining>composer.MAX_GENERATION_CALLS*config.PROVIDER_TIMEOUT
    composer._release(key,token)

def test_whitespace_only_evidence_is_repaired_not_accepted(ai_client):
    from google.genai import types
    fake,_=ai_client
    fake.models.generate_content.side_effect=[types.GenerateContentResponse(parsed={
        "hook":"  ","subject":"Backend role","body":STRONG_PITCH,"research_notes":"  "},candidates=[]),response()]
    result=composer._generate("facts",composer.EmailDraft,composer.SYSTEM_PROMPT)
    assert result["hook"].strip() and result["research_notes"].strip()
    assert fake.models.generate_content.call_count==2

def test_generated_wrappers_without_a_pitch_are_not_stored(ready,monkeypatch):
    company,person=ready
    monkeypatch.setattr(composer,"compose_email",lambda *args:{"subject":"Role","hook":"Hook", "body":"Hi Person,\n\nBest,\nCandidate","research_notes":"Research unavailable"})
    with pytest.raises(ProviderError,match="no pitch"):
        composer.compose_and_store(company,person,composer.candidate_context())
    assert EmailRepository.get_by_contact_id(person)==[]

def test_valid_json_text_is_usable_when_sdk_parsed_field_is_absent(ai_client):
    from google.genai import types
    fake,_=ai_client
    payload=response().parsed.model_dump()
    fake.models.generate_content.return_value=types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(parts=[types.Part.from_text(text=json.dumps(payload))]))])
    result=composer._generate("source facts",composer.EmailDraft,composer.SYSTEM_PROMPT)
    assert result["body"]==STRONG_PITCH
    assert result["quality_warnings"]==[]
    assert fake.models.generate_content.call_count==1
