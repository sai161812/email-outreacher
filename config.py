"""Validated, environment-backed settings for the single-owner application."""
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def integer(name, default, minimum=0, maximum=1000000):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value

def local_path(name, default):
    value = Path(os.getenv(name, str(default))).expanduser()
    return (BASE_DIR / value).resolve() if not value.is_absolute() else value.resolve()

DB_PATH = local_path("OUTREACH_DB_PATH", "outreach.db")
RESUME_DIR = local_path("RESUME_DIR", "resumes")
CONTEXT_PATH = local_path("CONTEXT_PATH", "candidate_context.txt")
RESUME_ATTACH_MODE = os.getenv("RESUME_ATTACH_MODE", "attach").strip().lower()
if RESUME_ATTACH_MODE not in {"attach", "link"}:
    raise ValueError("RESUME_ATTACH_MODE must be attach or link")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview").strip()
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = integer("SMTP_PORT", 587, 1, 65535)
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
PROVIDER_TIMEOUT = integer("PROVIDER_TIMEOUT", 60, 1, 300)
DAILY_SEND_CAP = integer("DAILY_SEND_CAP", 15, 1, 1000)
MAX_PER_COMPANY_PER_WEEK = integer("MAX_PER_COMPANY_PER_WEEK", 2, 1, 1000)
MIN_DELAY_SECONDS = integer("MIN_DELAY_SECONDS", 45, 0, 3600)
MAX_DELAY_SECONDS = integer("MAX_DELAY_SECONDS", 240, 0, 3600)
if MIN_DELAY_SECONDS > MAX_DELAY_SECONDS:
    raise ValueError("MIN_DELAY_SECONDS must not exceed MAX_DELAY_SECONDS")
SEND_DAYS = [d.strip().lower() for d in os.getenv("SEND_DAYS", "mon,tue,wed,thu,fri").split(",")]
if not SEND_DAYS or any(d not in ["mon","tue","wed","thu","fri","sat","sun"] for d in SEND_DAYS):
    raise ValueError("SEND_DAYS must contain weekday abbreviations")
SEND_START_HOUR = integer("SEND_START_HOUR", 9, 0, 23)
SEND_END_HOUR = integer("SEND_END_HOUR", 18, 1, 24)
if SEND_START_HOUR >= SEND_END_HOUR:
    raise ValueError("SEND_START_HOUR must precede SEND_END_HOUR")
TIMEZONE_NAME = os.getenv("OUTREACH_TIMEZONE", "Asia/Kolkata")
try:
    TIMEZONE = ZoneInfo(TIMEZONE_NAME)
except ZoneInfoNotFoundError as exc:
    raise ValueError("OUTREACH_TIMEZONE must be a valid IANA timezone; install tzdata") from exc
FOLLOW_UP_AFTER_DAYS = integer("FOLLOW_UP_AFTER_DAYS", 7, 1, 365)
MAX_FOLLOW_UPS = integer("MAX_FOLLOW_UPS", 1, 0, 10)
MAX_UPLOAD_BYTES = integer("MAX_UPLOAD_BYTES", 1048576, 1024, 10485760)
MAX_RESUME_BYTES = integer("MAX_RESUME_BYTES", 5242880, 1024, 20971520)
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")

def now():
    return datetime.now(timezone.utc)

def require_gemini_key():
    if not GEMINI_API_KEY:
        raise ValueError("Set GEMINI_API_KEY in .env before drafting")

def require_gmail_creds():
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise ValueError("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env before sending or checking replies")
