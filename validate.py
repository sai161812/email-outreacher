import re
import time
from functools import lru_cache
EMAIL_REGEX=re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")

def is_valid_syntax(email):
    if not isinstance(email,str):
        return False
    email=email.strip()
    if len(email)>254 or not EMAIL_REGEX.fullmatch(email):
        return False
    local=email.split("@")[0]
    return len(local)<=64 and not local.startswith(".") and not local.endswith(".") and ".." not in local

def canonical_email(email):
    if not is_valid_syntax(email):
        raise ValueError("Enter a valid email address")
    return email.strip().lower()

def has_mx_record(domain):
    return _has_mx_record(domain.lower(),int(time.monotonic()//300))

@lru_cache(maxsize=256)
def _has_mx_record(domain,bucket):
    try:
        import dns.resolver
        answers=dns.resolver.resolve(domain,"MX",lifetime=3)
        return bool(answers) and any(str(a.exchange)!="." for a in answers)
    except Exception as exc:
        return False if type(exc).__name__ in {"NXDOMAIN","NoAnswer"} else None

def validate_email(email, check_dns=True):
    if not is_valid_syntax(email):
        return False,"Invalid email address"
    mx=has_mx_record(email.strip().split("@")[1]) if check_dns else True
    return True, ("Domain has no usable MX record" if mx is False else "DNS verification was inconclusive" if mx is None else None)
