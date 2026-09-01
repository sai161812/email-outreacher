from repository import SuppressionRepository

def add(email, reason):
    SuppressionRepository.add(email, reason)

def remove(email):
    SuppressionRepository.remove(email)

def is_suppressed(email) -> bool:
    return SuppressionRepository.is_suppressed(email)

def list_all():
    return [dict(r) for r in SuppressionRepository.get_all()]
