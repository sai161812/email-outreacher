import pytest
import qc

STRONG_PITCH=(
    "I'm exploring backend engineering opportunities with Example, particularly work involving Python and data tools. "
    "The role's focus on reliable data handling connects with a project I have built.\n\n"
    "I built a Python dashboard that validates CSV imports and presents weekly usage summaries. "
    "It gave me practical experience with input validation, database queries, and clear error handling. "
    "That is the foundation I would bring to a team developing dependable internal tools.\n\n"
    "Could you point me to the appropriate application route for the backend role?"
)
STRONG_FOLLOWUP=(
    "Following up on my interest in backend engineering with Example. "
    "My Python dashboard work involved CSV validation and database queries, which relate to the data tools described in the role. "
    "Is there a preferred application route for this opportunity?"
)

def test_scannable_evidence_led_pitch_has_no_style_flags():
    assert qc.generation_feedback("Backend engineering at Example",STRONG_PITCH)==[]
    assert qc.generation_feedback("Re: Backend engineering at Example",STRONG_FOLLOWUP,True)==[]

@pytest.mark.parametrize("greeting",["Hi Maya,","Hello,","Hello Hiring Team,","Dear Dr. Singh,"])
def test_length_budget_excludes_only_email_wrappers(greeting):
    body=f"{greeting}\n\n{STRONG_PITCH}\n\nBest,\nCandidate\nhttps://example.test/profile"
    assert qc.pitch_text(body)==STRONG_PITCH
    assert qc.warnings("Backend engineering at Example",body)==[]

def test_manual_email_without_signature_keeps_its_final_ask():
    assert qc.pitch_text("Hello,\n\n"+STRONG_PITCH)==STRONG_PITCH
    assert not any("question or request" in warning for warning in qc.warnings("Backend opportunity","Hello,\n\n"+STRONG_PITCH))

@pytest.mark.parametrize("body,fragment",[
    ("I hope this email finds you well. I'm a perfect fit for your esteemed company. Can we talk?","generic filler"),
    ("Python, Java, SQL, React, Kubernetes, AWS, Docker are my skills. Can we talk?","comma-separated"),
    (STRONG_PITCH.replace("\n\n"," "),"2-3 short paragraphs"),
    (STRONG_PITCH+" Can we also schedule a call?","multiple asks"),
    ("**Excellent candidate**\n- Python\n- SQL","markup"),
    ("PLEASE CONSIDER MY APPLICATION FOR THIS POSITION?","all caps"),
])
def test_actionable_writing_flags(body,fragment):
    assert any(fragment in warning for warning in qc.check_body(body))

def test_followup_removes_pressure_without_blocking_manual_review():
    body="As per my last email, you have not replied. I am still waiting. Can you respond?"
    assert any("pressure or guilt" in warning for warning in qc.check_body(body,True))
    assert qc.blockers("Re: Backend role",body)==[]

def test_technical_acronyms_are_not_treated_as_all_caps_spam():
    assert not any("all caps" in warning for warning in qc.check_body("I used SQL and HTTP APIs in a Python dashboard. Could you advise on the application route?"))

def test_specific_longer_role_subject_is_allowed_but_fake_thread_is_flagged():
    assert qc.check_subject("Backend software engineering internship at Example")==[]
    assert any("existing conversation" in warning for warning in qc.check_subject("Re: Backend role"))
    assert qc.check_subject("Re: Backend role",True)==[]

def test_generated_wrappers_are_flagged_for_revision():
    assert any("pitch only" in warning for warning in qc.generation_feedback("Backend role","Hi Maya,\n\n"+STRONG_PITCH+"\n\nBest,\nCandidate"))

def test_greeting_and_signature_alone_cannot_pass_content_checks():
    assert any("Pitch is required" in error for error in qc.blockers("Backend role","Hi Maya,\n\nBest,\nCandidate"))
