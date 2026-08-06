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
RESUME_ATTACH_MODE = os.getenv("RESUME_ATTACH_MODE", "attach").lower()

# --- Gemini API (used for research + drafting) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.1-pro-preview"

# --- Gmail SMTP / IMAP ---
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")

# --- Rate limiting (protects your sender reputation) ---
DAILY_SEND_CAP = int(os.getenv("DAILY_SEND_CAP", "15"))
MAX_PER_COMPANY_PER_WEEK = int(os.getenv("MAX_PER_COMPANY_PER_WEEK", "2"))
MIN_DELAY_SECONDS = int(os.getenv("MIN_DELAY_SECONDS", "45"))
MAX_DELAY_SECONDS = int(os.getenv("MAX_DELAY_SECONDS", "240"))

# --- Send-time window (local time) ---
SEND_DAYS = [d.strip().lower() for d in os.getenv("SEND_DAYS", "mon,tue,wed,thu,fri").split(",") if d.strip()]
SEND_START_HOUR = int(os.getenv("SEND_START_HOUR", "9"))
SEND_END_HOUR = int(os.getenv("SEND_END_HOUR", "18"))

# --- Follow-up ---
FOLLOW_UP_AFTER_DAYS = int(os.getenv("FOLLOW_UP_AFTER_DAYS", "7"))


def require_gemini_key():
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Add it to your .env file.\n"
            "Get one at: https://aistudio.google.com/apikey"
        )


def require_gmail_creds():
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set. Add them to your .env file.\n"
            "Generate an app password at: https://myaccount.google.com/apppasswords"
        )
