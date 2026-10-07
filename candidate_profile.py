from repository import ProfileRepository
from contacts import text
from validate import canonical_email
from resume import safe_url

def set_profile(full_name,email=None,phone=None,linkedin_url=None,github_url=None,portfolio_url=None):
    ProfileRepository.upsert_profile(text(full_name,"full_name",True,200),canonical_email(email) if email else None,
        text(phone,"phone",maximum=100),safe_url(linkedin_url),safe_url(github_url),safe_url(portfolio_url))

def get_profile():
    return ProfileRepository.get_profile()
