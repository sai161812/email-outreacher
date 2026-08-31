import re

def detect_placeholders(text: str) -> list[str]:
    pattern = r"\[[A-Za-z][A-Za-z '\-]{1,20}\]"
    if not text:
        return []
    return re.findall(pattern, text)

def check_body(body: str) -> list[str]:
    warnings = []
    if not body:
        return warnings
    
    words = body.split()
    if len(words) < 50 or len(words) > 90:
        warnings.append(f"Body length ({len(words)} words) outside 50-90 range")

    banned = ["hope this email finds you", "my name is", "i am writing to"]
    lower_body = body.lower()
    for phrase in banned:
        if phrase in lower_body:
            warnings.append(f"Contains banned phrase: '{phrase}'")
            
    return warnings

def check_subject(subject: str) -> list[str]:
    warnings = []
    if not subject:
        return warnings
    
    words = subject.split()
    if len(words) > 6:
        warnings.append(f"Subject length ({len(words)} words) over 6 words")
    
    generic_patterns = ["internship opportunity", "application"]
    lower_subj = subject.lower()
    for pat in generic_patterns:
        if pat in lower_subj:
            warnings.append(f"Subject contains generic phrase: '{pat}'")
            
    return warnings
