"""Deterministic checks: hard blockers and optional writing suggestions."""
import re

def detect_placeholders(text):
    return re.findall(r"\[[A-Za-z][A-Za-z '\-]{1,40}\]|\{\{[^}]+\}\}", text or "")

def blockers(subject, body):
    errors = []
    if not isinstance(subject, str) or not subject.strip():
        errors.append("Subject is required")
    if not isinstance(body, str) or not body.strip():
        errors.append("Body is required")
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
    if follow_up and words > 40:
        warnings.append(f"Follow-up pitch is {words} words; target at most 40")
    elif not follow_up and not 50 <= words <= 90:
        warnings.append(f"Pitch is {words} words; target 50-90")
    for phrase in ("hope this email finds you", "my name is", "i am writing to"):
        if phrase in body.lower():
            warnings.append(f"Contains filler: {phrase}")
    return warnings

def check_subject(subject):
    if not subject or not subject.strip():
        return ["Subject is required"]
    return ["Subject target is at most 6 words"] if len(subject.split()) > 6 else []

def warnings(subject, body, follow_up=False):
    # Greeting and signature are assembled by us, not part of the pitch budget.
    parts = (body or "").split("\n\n")
    pitch = "\n\n".join(parts[1:-1]) if len(parts) >= 3 and parts[0].startswith("Hi ") else body
    return blockers(subject, body) + check_subject(subject) + check_body(pitch, follow_up)
