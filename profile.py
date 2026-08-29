from db import get_connection

def get_profile():
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM profile ORDER BY id ASC LIMIT 1').fetchone()
        return dict(row) if row else None

def set_profile(full_name=None, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None):
    with get_connection() as conn:
        existing = conn.execute('SELECT id FROM profile ORDER BY id ASC LIMIT 1').fetchone()
        if existing:
            updates = []
            params = []
            if full_name is not None:
                updates.append('full_name = ?')
                params.append(full_name)
            if email is not None:
                updates.append('email = ?')
                params.append(email)
            if phone is not None:
                updates.append('phone = ?')
                params.append(phone)
            if linkedin_url is not None:
                updates.append('linkedin_url = ?')
                params.append(linkedin_url)
            if github_url is not None:
                updates.append('github_url = ?')
                params.append(github_url)
            if portfolio_url is not None:
                updates.append('portfolio_url = ?')
                params.append(portfolio_url)
                
            if updates:
                params.append(existing['id'])
                conn.execute(f'UPDATE profile SET {", ".join(updates)} WHERE id = ?', params)
        else:
            conn.execute(
                'INSERT INTO profile (full_name, email, phone, linkedin_url, github_url, portfolio_url) VALUES (?, ?, ?, ?, ?, ?)',
                (full_name, email, phone, linkedin_url, github_url, portfolio_url)
            )
