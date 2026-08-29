from db import get_connection

def get_profile():
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        return dict(row) if row else None

def set_profile(full_name, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO profile (id, full_name, email, phone, linkedin_url, github_url, portfolio_url)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                full_name = excluded.full_name,
                email = excluded.email,
                phone = excluded.phone,
                linkedin_url = excluded.linkedin_url,
                github_url = excluded.github_url,
                portfolio_url = excluded.portfolio_url,
                updated_at = datetime('now')
            """,
            (full_name, email, phone, linkedin_url, github_url, portfolio_url)
        )
