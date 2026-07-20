"""
This is the core of the "clever email" idea, scoped honestly:
Gemini researches the company via Google Search grounding, finds 2-3
concrete, verifiable facts, and drafts a hook + email around them.
The output ALWAYS lands as pending_review — nothing here sends anything.

If the research turns up nothing solid, drafting should say so rather
than inventing a fact. That instruction is baked into the prompt below.
"""
import json
import re

from google import genai
from google.genai import types

import config
from db import get_connection

SYSTEM_PROMPT = """You are helping a first-year engineering student draft a cold \
outreach email to a company for an internship. You have Google Search available.

Steps:
1. Research the company (and the specific job posting if given) using search. \
Look for something concrete and current: a recent product launch, a specific \
technology they use, a blog post, an engineering challenge they've talked about. \
Do NOT use generic praise ("I admire your innovative culture") — that is worse \
than no hook at all.
2. If you cannot find anything concrete and verifiable after searching, say so \
explicitly in the "hook" field (e.g. "No specific hook found — verify manually \
before sending") rather than inventing something plausible-sounding.
3. Draft a short, direct, non-flowery cold email (120-180 words) that:
   - Opens with the specific hook, not a generic greeting
   - Briefly connects the student's relevant experience to the role
   - Has a clear, low-friction ask (e.g. a short call, or just "happy to share \
more") — not presumptuous
   - Ends with a plain sign-off
   A recruiter or HR skims cold emails in seconds — 120-180 words is a hard \
ceiling, not a target to reach. Shorter and specific beats longer and thorough.
5. Subject line: under 8 words, specific to the role or hook (e.g. "Backend \
intern interest — [specific project/tech]"), never generic ("Internship \
Application", "Reaching Out") since generic subjects get skipped in a crowded \
inbox.
4. Do not fabricate any claim about the student's own background beyond what is \
given to you in the candidate_context.

Respond with ONLY valid JSON, no markdown fences, no preamble, in this exact shape:
{"hook": "...", "subject": "...", "body": "...", "research_notes": "..."}

research_notes should list the specific facts you found and where (so the student \
can double check before sending).
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


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


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
        ),
    )

    full_text = response.text or ""

    try:
        return _extract_json(full_text)
    except json.JSONDecodeError:
        # Fall back to storing raw text so nothing is silently lost —
        # you'll see the mangled output in review and can retry/fix by hand.
        return {
            "hook": "PARSE_ERROR",
            "subject": "(needs manual fix)",
            "body": full_text,
            "research_notes": "Model output was not valid JSON, showing raw output.",
        }


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
