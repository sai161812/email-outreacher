import re

def detect_placeholders(text: str) -> list[str]:
    pattern = r"\[[A-Za-z][A-Za-z '\-]{1,20}\]"
    if not text:
        return []
    return re.findall(pattern, text)
