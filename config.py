"""
Central config. Everything tunable lives here so no magic numbers
are buried inside other modules.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "outreach.db"
RESUME_DIR = BASE_DIR / "resumes"

# --- Anthropic API (used for research + drafting) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-5"

# --- Gmail SMTP sending ---
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# --- Rate limiting (protects your sender reputation) ---
DAILY_SEND_CAP = int(os.getenv("DAILY_SEND_CAP", "15"))
MIN_DELAY_SECONDS = int(os.getenv("MIN_DELAY_SECONDS", "45"))
MAX_DELAY_SECONDS = int(os.getenv("MAX_DELAY_SECONDS", "240"))

# --- Follow-up ---
FOLLOW_UP_AFTER_DAYS = int(os.getenv("FOLLOW_UP_AFTER_DAYS", "7"))


def require_anthropic_key():
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to your .env file."
        )


def require_gmail_creds():
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set. Add them to your .env file.\n"
            "Generate an app password at: https://myaccount.google.com/apppasswords"
        )
