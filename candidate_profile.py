from repository import ProfileRepository
from contacts import text
from validate import canonical_email
from resume import safe_url

def validate_profile(full_name,email=None,phone=None,linkedin_url=None,github_url=None,portfolio_url=None):
    return dict(full_name=text(full_name,"full_name",True,200),email=canonical_email(email) if email else None,
        phone=text(phone,"phone",maximum=100),linkedin_url=safe_url(linkedin_url),github_url=safe_url(github_url),portfolio_url=safe_url(portfolio_url))

def set_profile(full_name,email=None,phone=None,linkedin_url=None,github_url=None,portfolio_url=None):
    ProfileRepository.upsert_profile(**validate_profile(full_name,email,phone,linkedin_url,github_url,portfolio_url))

def get_profile():
    return ProfileRepository.get_profile()

def get_settings():
    return ProfileRepository.get_settings()

def save_settings(profile=None,candidate_context=None):
    validated=validate_profile(**profile) if profile is not None else None
    context=text(candidate_context,"candidate_context",True,20000) if candidate_context is not None else None
    ProfileRepository.save_settings(validated,context)
