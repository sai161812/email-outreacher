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
