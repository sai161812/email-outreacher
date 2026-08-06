from google import genai
from google.genai import types
import config
import db
import contacts
import resume
import qc
from repository import CompanyRepository, ContactRepository, EmailRepository, SuppressionRepository
import time

def compose_email(company_id, contact_id, resume_variant_id=None):
    company = CompanyRepository.get_by_id(company_id)
    contact = ContactRepository.get_by_id(contact_id)
    
    if not company or not contact:
        raise ValueError("Invalid company or contact.")

    if SuppressionRepository.is_suppressed(contact["email"]):
        raise ValueError("Contact email is suppressed.")
        
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    resume_text = ""
    if resume_variant_id:
        from repository import ResumeRepository
        for rv in ResumeRepository.get_all():
            if rv["id"] == resume_variant_id:
                try:
                    with open(rv["file_path"], "r", encoding="utf-8") as f:
                        resume_text = f.read()
                except Exception:
                    pass
                break

    from repository import ProfileRepository
    profile = ProfileRepository.get_profile()
    if profile:
        profile_context = f"\nMy Background:\n{profile['full_name']} ({profile['email']})\n"
        if profile["linkedin_url"]: profile_context += f"LinkedIn: {profile['linkedin_url']}\n"
        if profile["github_url"]: profile_context += f"GitHub: {profile['github_url']}\n"
        if profile["portfolio_url"]: profile_context += f"Portfolio: {profile['portfolio_url']}\n"
    else:
        profile_context = ""

    prompt = f"""
    Write a cold outreach email to {contact['name']} ({contact['title']}) at {company['name']}.
    Source: {contact['source']}
    Job Domain/Text: {company['domain']} {company['job_text']}
    Notes: {company['notes']}
    Resume Context: {resume_text}
    {profile_context}
    
    Keep it under 100 words. Be professional but conversational. Do NOT use emojis.
    Return exactly 3 fields: hook (1 short sentence), subject, and body (including the hook at the start).
    """

    class EmailDraft(types.BaseModel):
        hook: str
        subject: str
        body: str

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=EmailDraft,
                    temperature=0.7,
                ),
            )
            draft = response.parsed
            
            warnings = []
            if qc_res := qc.check_body(draft.body):
                warnings.append(qc_res)
            if qc_res := qc.check_subject(draft.subject):
                warnings.append(qc_res)
                
            return {
                "hook": draft.hook,
                "subject": draft.subject,
                "body": draft.body,
                "qc_warnings": " | ".join(warnings) if warnings else None
            }
        except Exception as e:
            if attempt == 1:
                return {
                    "hook": "[Failed to generate hook]",
                    "subject": "[Failed to generate subject]",
                    "body": "[Failed to generate body - manual edit required]",
                    "qc_warnings": f"Generation failed: {str(e)}"
                }
            time.sleep(1)

def compose_and_store(company_id, contact_id, resume_variant_id=None):
    draft = compose_email(company_id, contact_id, resume_variant_id)
    return EmailRepository.create(
        company_id=company_id,
        contact_id=contact_id,
        resume_variant_id=resume_variant_id,
        hook=draft["hook"],
        subject=draft["subject"],
        body=draft["body"],
        qc_warnings=draft["qc_warnings"]
    )

def compose_follow_up(email_id):
    original_email = EmailRepository.get_by_id(email_id)
    if not original_email:
        raise ValueError("Original email not found")
        
    company = CompanyRepository.get_by_id(original_email["company_id"])
    contact = ContactRepository.get_by_id(original_email["contact_id"])
    
    prompt = f"""
    Write a short follow-up email to {contact['name']} at {company['name']}.
    Original Subject: {original_email['subject']}
    Original Body sent on {original_email['sent_at']}:
    {original_email['body']}
    
    Keep it under 50 words. Be polite and concise.
    Return exactly 2 fields: subject (usually Re: <original>), and body.
    """
    
    class FollowUpDraft(types.BaseModel):
        subject: str
        body: str

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FollowUpDraft,
                    temperature=0.7,
                ),
            )
            draft = response.parsed
            return {
                "subject": draft.subject,
                "body": draft.body
            }
        except Exception as e:
            if attempt == 1:
                return {
                    "subject": f"Re: {original_email['subject']}",
                    "body": "[Failed to generate follow-up - manual edit required]",
                }
            time.sleep(1)

def compose_follow_up_and_store(email_id):
    original_email = EmailRepository.get_by_id(email_id)
    draft = compose_follow_up(email_id)
    
    return EmailRepository.create(
        company_id=original_email["company_id"],
        contact_id=original_email["contact_id"],
        resume_variant_id=original_email["resume_variant_id"],
        hook="[Follow-up]",
        subject=draft["subject"],
        body=draft["body"],
        qc_warnings=None,
        follow_up_to_email_id=email_id
    )
