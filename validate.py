import re

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def is_valid_syntax(email: str) -> bool:
    """
    Checks if an email string has valid syntax according to standard email format.
    Must reject things like 'jane@acme' with no TLD, spaces, multiple @ signs.
    """
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if not EMAIL_REGEX.match(email):
        return False
    # Ensure there is a dot in domain part and non-empty TLD
    domain = email.split("@")[-1]
    if "." not in domain or domain.endswith("."):
        return False
    return True


def has_mx_record(domain: str) -> bool | None:
    """
    Checks if the domain has active MX records via DNS.
    Returns True if valid MX found, False if NXDOMAIN/NoAnswer,
    and None on any other DNS/network failure.
    """
    if not domain or not isinstance(domain, str):
        return False
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain.strip(), "MX")
        return len(answers) > 0
    except Exception as e:
        err_name = type(e).__name__
        if err_name in ("NXDOMAIN", "NoAnswer", "NoNameservers"):
            return False
        # Inconclusive/network/timeout -> return None
        return None


def validate_email(email: str) -> tuple[bool, str | None]:
    """
    Combines syntax and MX checks.
    Hard-fails (False, reason) on bad syntax.
    Soft-warns (True, reason) on missing/unknown MX.
    Returns (is_valid, warning_or_error_message).
    """
    if not email or not isinstance(email, str):
        return False, "Email address is empty"

    email = email.strip()
    if not is_valid_syntax(email):
        return False, f"Invalid email syntax: '{email}'"

    domain = email.split("@")[-1]
    mx_status = has_mx_record(domain)
    if mx_status is False:
        return True, f"Domain '{domain}' has no valid MX records"
    elif mx_status is None:
        return True, f"Could not verify MX records for '{domain}'"

    return True, None
