from db import get_connection

def add(email: str, reason: str = ""):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO suppressions (email, reason) VALUES (?, ?)",
            (email.strip().lower(), reason)
        )

def remove(email: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM suppressions WHERE email = ?", (email.strip().lower(),))

def is_suppressed(email: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM suppressions WHERE email = ?",
            (email.strip().lower(),)
        ).fetchone()
        return bool(row)

def list_all():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM suppressions ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
