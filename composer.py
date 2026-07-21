"""
This is the core of the "clever email" idea, scoped honestly:
Gemini researches the company via Google Search grounding, finds 2-3
concrete, verifiable facts, and drafts a hook + email around them.
The output ALWAYS lands as pending_review — nothing here sends anything.

If the research turns up nothing solid, drafting should say so rather
than inventing a fact. That instruction is baked into the prompt below.
"""
import re

from google import genai
from google.genai import types
from pydantic import BaseModel

import config
from db import get_connection

class EmailDraft(BaseModel):
    hook: str
    subject: str
    body: str
    research_notes: str

SYSTEM_PROMPT = """You are an elite B2B copywriter helping a first-year engineering student \
draft a highly-converting cold email for an internship. You have Google Search available.

CRITICAL DIRECTIVES:
1. OUTPUT ONLY THE BODY PITCH. Do not include a greeting line (e.g., "Hi Name,") or a sign-off/signature (e.g., "Best, Student"). 
2. NO PLACEHOLDERS. Never use bracket placeholders like [Name], [Student], or [Company] anywhere in your output. Write actual sentences.
3. NO PLEASANTRIES. Never use "Hope this finds you well" or introduce yourself.
4. DEEP PERSONALIZATION. Research the company using search. Find a recent product launch, \
a specific tech stack detail, or an engineering challenge they face.
5. THE "WHY YOU, WHY ME" FRAMEWORK. The body must be exactly 3-4 sentences:
   - Sentence 1 (The Hook): A direct, specific observation about their company based on your research.
   - Sentence 2 (The Pitch): Connect their specific context to a specific skill or project from the student's background.
   - Sentence 3 (The Ask): A low-friction, confident call to action (e.g., "Open to a brief chat?", not "Please interview me").
6. CONFIDENT TONE. Be direct, professional, and confident. Do not sound pleading, desperate, or overly deferential.
7. LENGTH: 50-90 words MAXIMUM. Shorter is always better.
8. SUBJECT LINE: Under 6 words, highly specific to the hook or role. Never generic.

Example Good Draft:
Subject: Question about the new payment API
Noticed you just rolled out the new GraphQL payment API—looks like a massive upgrade for latency.
I recently built a similar distributed caching layer for a Go microservice that handled 10k requests/sec, and I'd love to bring that experience to your backend team as an intern.
Open to a brief chat later this week?

If you cannot find anything concrete and verifiable after searching, say so explicitly in the "hook" field rather than inventing something.
Do not fabricate any claim about the student's own background beyond what is in the candidate_context.
research_notes should list the specific facts you found and where.
"""


def _build_user_prompt(company: dict, contact: dict, candidate_context: str) -> str:
    parts = [
        f"Company: {company.get('name')}",
        f"Domain: {company.get('domain') or 'unknown'}",
    ]
    if company.get("job_url"):
        parts.append(f"Job posting URL: {company['job_url']}")
    if company.get("job_text"):
        parts.append(f"Job posting text:\n{company['job_text']}")
    if contact.get("name"):
        parts.append(f"Recipient name: {contact['name']}")
    if contact.get("title"):
        parts.append(f"Recipient title: {contact['title']}")
    parts.append(f"\nCandidate context (use only this for the student's background):\n{candidate_context}")
    return "\n".join(parts)


def compose_email(company: dict, contact: dict, candidate_context: str) -> dict:
    """
    Calls Gemini with Google Search grounding enabled, returns dict with
    hook, subject, body, research_notes. Does NOT write to the DB.
    """
    config.require_gemini_key()
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    user_prompt = _build_user_prompt(company, contact, candidate_context)

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
            response_schema=EmailDraft,
        ),
    )

    try:
        draft = response.parsed
        subject = draft.subject
        body = draft.body
        
        # Deterministic greeting
        first_name = contact.get("name", "").split()[0] if contact.get("name") else ""
        greeting = f"Hi {first_name}," if first_name else "Hi there,"
        body = f"{greeting}\n\n{body}"
        
        # Regex safety net
        placeholder_pattern = r'\[[A-Za-z][A-Za-z \'-]{1,20}\]'
        if re.search(placeholder_pattern, subject) or re.search(placeholder_pattern, body):
            subject = f"[WARNING: PLACEHOLDER DETECTED] {subject}"

        return {
            "hook": draft.hook,
            "subject": subject,
            "body": body,
            "research_notes": draft.research_notes,
        }
    except Exception as e:
        full_text = response.text or ""
        return {
            "hook": "PARSE_ERROR",
            "subject": "(needs manual fix)",
            "body": f"Failed to parse structured output: {e}\n\n{full_text}",
            "research_notes": "Model output parsing failed.",
        }


class FollowUpDraft(BaseModel):
    subject: str
    body: str

FOLLOW_UP_SYSTEM_PROMPT = """You are an elite B2B copywriter helping a first-year engineering student \
write a highly-converting, brief follow-up to a cold outreach email they sent earlier.

CRITICAL DIRECTIVES:
1. OUTPUT ONLY THE BODY PITCH. Do not include a greeting line (e.g., "Hi Name,") or a sign-off/signature (e.g., "Best, Student"). 
2. NO PLACEHOLDERS. Never use bracket placeholders like [Name], [Student], or [Company] anywhere in your output. Write actual sentences.
3. MAX 2-3 SENTENCES. Brevity is paramount. This is a nudge, not a new pitch. (40 words max).
4. TONE: Confident, polite, and low-pressure. No guilt-tripping ("Since you didn't reply"), no "just checking in" filler.
5. CONTEXT: Reference the original email seamlessly without restating it (assume they will scroll down).
6. VALUE-ADD (Optional but preferred): If possible, mention one tiny new relevant detail (e.g., "Just shipped a new feature on the Go project I mentioned..."), otherwise just keep it extremely brief.
7. THE ASK: A simple, low-friction yes/no question.

Example Good Follow-Up:
Subject: Re: Question about the new payment API
Following up on my note below—I actually just finished open-sourcing the caching layer I mentioned. 
Would you be open to a quick 10-minute chat next week to see if my background aligns with your backend internship needs?

Subject should be "Re: <original subject>" unless it reads awkwardly.
"""


def compose_follow_up(original_email_id: int) -> dict:
    """
    Drafts a short follow-up referencing an already-sent email, rather
    than re-researching the company from scratch. Does NOT write to the DB.
    """
    config.require_gemini_key()
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    with get_connection() as conn:
        original = conn.execute(
            "SELECT * FROM emails WHERE id = ?", (original_email_id,)
        ).fetchone()
    if not original:
        raise ValueError(f"No email found with id {original_email_id}")
    original = dict(original)

    user_prompt = (
        f"Original subject: {original.get('subject')}\n"
        f"Original body:\n{original.get('body')}\n"
        f"Original hook used: {original.get('hook')}\n"
    )

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=FOLLOW_UP_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=FollowUpDraft,
        ),
    )

    try:
        draft = response.parsed
        subject = draft.subject
        body = draft.body

        # Deterministic greeting
        with get_connection() as conn:
            contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (original["contact_id"],)).fetchone()
            contact = dict(contact) if contact else {}
        first_name = contact.get("name", "").split()[0] if contact.get("name") else ""
        greeting = f"Hi {first_name}," if first_name else "Hi there,"
        body = f"{greeting}\n\n{body}"

        # Regex safety net
        placeholder_pattern = r'\[[A-Za-z][A-Za-z \'-]{1,20}\]'
        if re.search(placeholder_pattern, subject) or re.search(placeholder_pattern, body):
            subject = f"[WARNING: PLACEHOLDER DETECTED] {subject}"

        result = {
            "subject": subject,
            "body": body,
        }
    except Exception as e:
        full_text = response.text or ""
        result = {
            "subject": "(needs manual fix)",
            "body": f"Failed to parse structured output: {e}\n\n{full_text}",
        }
    result["hook"] = original.get("hook")  # carry the original hook forward for reference
    return result


def compose_follow_up_and_store(original_email_id: int) -> int:
    from db import get_connection as _get_connection

    with get_connection() as conn:
        original = conn.execute(
            "SELECT * FROM emails WHERE id = ?", (original_email_id,)
        ).fetchone()
    if not original:
        raise ValueError(f"No email found with id {original_email_id}")
    original = dict(original)

    if original["status"] not in ("sent", "replied", "ghosted"):
        raise ValueError(
            f"Email #{original_email_id} has status '{original['status']}' — "
            "follow-ups are only for emails that were actually sent."
        )

    result = compose_follow_up(original_email_id)

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO emails (company_id, contact_id, resume_variant_id, "
            "follow_up_to_email_id, hook, subject, body, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_review')",
            (
                original["company_id"], original["contact_id"], original["resume_variant_id"],
                original_email_id, result.get("hook"), result.get("subject"), result.get("body"),
            ),
        )
        return cur.lastrowid


def compose_and_store(company_id: int, contact_id: int, candidate_context: str,
                       resume_variant_id: int = None) -> int:
    from contacts import get_company, get_contact  # local import avoids circularity

    company = get_company(company_id)
    contact = get_contact(contact_id)
    result = compose_email(company, contact, candidate_context)

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO emails (company_id, contact_id, resume_variant_id, hook, "
            "subject, body, status) VALUES (?, ?, ?, ?, ?, ?, 'pending_review')",
            (
                company_id, contact_id, resume_variant_id,
                result.get("hook"), result.get("subject"), result.get("body"),
            ),
        )
        return cur.lastrowid