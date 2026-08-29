import re

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def validate_email_syntax(email: str) -> bool:
    """
    Checks if an email string has valid syntax according to standard email format.
    """
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_email_domain_mx(email: str) -> bool:
    """
    Checks if the domain of an email address has active MX records via DNS.
    Returns True if valid or if DNS check is inconclusive (network issue),
    returns False if the domain explicitly does not exist or has no MX records.
    """
    if not validate_email_syntax(email):
        return False

    domain = email.strip().split("@")[-1]
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        return len(answers) > 0
    except Exception as e:
        # If domain specifically does not exist or has no MX answer
        err_name = type(e).__name__
        if err_name in ("NXDOMAIN", "NoAnswer", "NoNameservers"):
            return False
        # If there's a timeout or local network resolution issue, treat as inconclusive/permissive
        return True


def validate_contact_email(email: str, check_mx: bool = False) -> tuple[bool, str | None]:
    """
    Validates email format and optionally checks MX records.
    Returns (is_valid, error_message).
    """
    if not email or not isinstance(email, str):
        return False, "Email address is empty"

    email = email.strip()
    if not validate_email_syntax(email):
        return False, f"Invalid email format: '{email}'"

    if check_mx:
        if not validate_email_domain_mx(email):
            return False, f"Domain '{email.split('@')[-1]}' has no valid MX records"

    return True, None
