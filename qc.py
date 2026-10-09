"""Deterministic checks: hard blockers and optional writing suggestions."""
import re

INITIAL_WORD_RANGE = (80, 120)
FOLLOW_UP_WORD_RANGE = (30, 60)

def pitch_text(body):
    """Count the actual pitch, stripping only recognizable email wrappers."""
    lines=(body or "").replace("\r\n","\n").strip().splitlines()
    if lines and re.fullmatch(r"(?:Hi|Hello|Dear)\b[^\n]{0,200}[,!]",lines[0].strip(),re.I):
        lines=lines[1:]
    for index,line in enumerate(lines):
        if index and not lines[index-1].strip() and re.fullmatch(r"(?:Best(?: regards)?|Kind regards|Regards|Sincerely|Thanks(?: again)?|Thank you)[,!]?",line.strip(),re.I):
            lines=lines[:index]
            break
    return "\n".join(lines).strip()

def detect_placeholders(text):
    return re.findall(r"\[[A-Za-z][A-Za-z '\-]{1,40}\]|\{\{[^}]+\}\}", text or "")

def blockers(subject, body):
    errors = []
    if not isinstance(subject, str) or not subject.strip():
        errors.append("Subject is required")
    if not isinstance(body, str) or not body.strip():
        errors.append("Body is required")
    elif not pitch_text(body):
        errors.append("Pitch is required, beyond the greeting and signature")
    if any(token in (body or "") for token in ("Failed to parse structured output", "PARSE_ERROR")):
        errors.append("Generation failed: regenerate the draft")
    if detect_placeholders(subject) or detect_placeholders(body):
        errors.append("Replace all placeholders")
    if "\n" in (subject or "") or "\r" in (subject or ""):
        errors.append("Subject must be one line")
    if len(subject or "") > 200 or len(body or "") > 12000:
        errors.append("Content exceeds size limits")
    return errors

def check_body(body, follow_up=False):
    if not body or not body.strip():
        return ["Body is required"]
    words = len(body.split())
    warnings = []
    lower,upper=FOLLOW_UP_WORD_RANGE if follow_up else INITIAL_WORD_RANGE
    if not lower <= words <= upper:
        warnings.append(f"{'Follow-up pitch' if follow_up else 'Pitch'} is {words} words; target {lower}-{upper}. Keep it shorter if facts are limited")
    for phrase in ("hope this email finds you", "hope this message finds you", "my name is", "i am writing to",
                   "esteemed", "prestigious", "perfect fit", "dream company", "rockstar", "synergy", "humbly request", "do the needful"):
        if re.search(r"\b"+re.escape(phrase)+r"\b",body,re.I):
            warnings.append(f"Replace generic filler or inflated wording: {phrase}")
    paragraphs=[p for p in re.split(r"\n\s*\n",body.strip()) if p.strip()]
    if not follow_up and words>60 and len(paragraphs)==1:
        warnings.append("Break the pitch into 2-3 short paragraphs for scanning")
    if len(paragraphs)>(2 if follow_up else 3):
        warnings.append("Use at most 2 short paragraphs" if follow_up else "Use at most 3 short paragraphs")
    if any(len(sentence.split())>35 for sentence in re.split(r"(?<=[.!?])\s+",body.strip())):
        warnings.append("Shorten sentences over 35 words")
    if any(line.count(",")>=5 for line in body.splitlines()):
        warnings.append("Replace long comma-separated lists with one relevant example and a few supported skills")
    if body.count("?")>1:
        warnings.append("Use one clear next-step question, rather than multiple asks")
    elif "?" not in body and not re.search(r"\b(?:please (?:let|share|consider|advise)|let me know|(?:I'd|I would) welcome|open to)\b",body,re.I):
        warnings.append("End with one clear, easy-to-answer question or request")
    if re.search(r"(?:^|\n)\s*(?:#{1,6}\s|[-*]\s|\d+[.)]\s)|\*\*|```|<[^>]+>",body):
        warnings.append("Use plain-text paragraphs without markup or lists")
    letters=[c for c in body if c.isalpha()]
    if len(letters)>20 and sum(c.isupper() for c in letters)/len(letters)>0.7:
        warnings.append("Use normal sentence case, not all caps")
    if follow_up and re.search(r"\b(?:bumping|as per my (?:last|previous) email|you (?:haven't|have not) (?:responded|replied)|still waiting|urgent response)\b",body,re.I):
        warnings.append("Remove pressure or guilt from the follow-up")
    return warnings

def check_subject(subject,follow_up=False):
    if not subject or not subject.strip():
        return ["Subject is required"]
    if follow_up:
        return []  # Preserve the original thread; hard header checks still apply.
    result=[]
    if len(subject.split())>8 or len(subject)>65:
        result.append("Use a specific subject of at most 8 words and 65 characters")
    if re.match(r"\s*(?:re|fw|fwd)\s*:",subject,re.I):
        result.append("Do not imply an existing conversation in an initial subject")
    if re.search(r"\b(?:urgent|guaranteed|must read|act now)\b|!!",subject,re.I):
        result.append("Remove urgency or clickbait from the subject")
    return result

def generation_feedback(subject,body,follow_up=False):
    result=blockers(subject,body)+check_subject(subject,follow_up)+check_body(body,follow_up)
    if re.match(r"\s*(?:Hi|Hello|Dear)\b[^\n]*[,!]\s*(?:\n|$)",body,re.I) or re.search(r"(?:^|\n)\s*(?:Best(?: regards)?|Kind regards|Sincerely|Regards)[,!]?\s*(?:\n|$)",body,re.I):
        result.append("Return the pitch only; the application adds the greeting and signature")
    return list(dict.fromkeys(result))

def warnings(subject, body, follow_up=False):
    # Greeting and signature are assembled by us, not part of the pitch budget.
    return blockers(subject, body) + check_subject(subject,follow_up) + check_body(pitch_text(body), follow_up)
