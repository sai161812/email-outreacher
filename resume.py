import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse
import config
from repository import ResumeRepository
from errors import NotFound

def safe_url(value):
    if value is None or value=="":
        return None
    if not isinstance(value,str) or len(value)>2000:
        raise ValueError("URL must be text under 2000 characters")
    value=value.strip()
    if not value: return None
    if any(c.isspace() or ord(c)<32 for c in value): raise ValueError("URL must not contain whitespace")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an HTTPS URL without embedded credentials")
    return value.strip()

def checked_pdf(path):
    target = Path(path).resolve()
    if not target.is_relative_to(config.RESUME_DIR.resolve()):
        raise ValueError("Copy the PDF into RESUME_DIR before registering it")
    if not target.is_file() or target.stat().st_size > config.MAX_RESUME_BYTES:
        raise ValueError("Resume PDF is missing or exceeds the size limit")
    data = target.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError("Resume must be a PDF")
    return target, data

def add_resume_variant(name, keywords="", file_path="", resume_url=None):
    if not isinstance(name,str) or not name.strip() or len(name)>100:
        raise ValueError("Resume name is required (at most 100 characters)")
    url = safe_url(resume_url)
    if file_path:
        target,_ = checked_pdf(file_path)
        file_path = str(target)
    if not file_path and not url:
        raise ValueError("Provide a PDF or an HTTPS resume link")
    if not isinstance(keywords,str) or len(keywords)>1000:
        raise ValueError("Keywords must be text under 1000 characters")
    return ResumeRepository.create(name.strip(), keywords, file_path, url)

def get_variant(variant_id):
    variant = ResumeRepository.get_by_id(variant_id)
    if not variant:
        raise NotFound("Resume not found")
    return variant

def list_resume_variants():
    return ResumeRepository.get_all()

def pick_best_variant(job_text):
    variants = list_resume_variants()
    if not variants:
        return None
    text = (job_text or "").casefold()
    return max(variants,key=lambda v: sum(bool(re.search(r"(?<!\w)"+re.escape(k.strip().casefold())+r"(?!\w)",text))
                                            for k in v["keywords"].split(",") if k.strip()))

def delivery_asset(variant_id):
    if not variant_id:
        return None
    variant = get_variant(variant_id)
    asset = {"id":variant_id,"name":variant["name"],"url":safe_url(variant.get("resume_url"))}
    if config.RESUME_ATTACH_MODE == "link":
        if not asset["url"]:
            raise ValueError("Selected resume has no HTTPS link")
    else:
        path,data = checked_pdf(variant["file_path"])
        asset.update(path=str(path),sha256=hashlib.sha256(data).hexdigest())
    return asset
