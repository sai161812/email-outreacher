from repository import ProfileRepository

def set_profile(full_name, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None):
    ProfileRepository.upsert_profile(full_name, email, phone, linkedin_url, github_url, portfolio_url)

def get_profile():
    row = ProfileRepository.get_profile()
    return dict(row) if row else None
