import hashlib
import io
import re
from pathlib import Path
from urllib.parse import urlparse
import config
from repository import ResumeRepository
from errors import NotFound
from pypdf import PdfReader


def validate_pdf(data):
    if not data.startswith(b"%PDF-") or len(data)>config.MAX_RESUME_BYTES:
        raise ValueError("Resume must be a PDF within the size limit")
    try:
        reader=PdfReader(io.BytesIO(data),strict=True)
        if reader.is_encrypted:
            raise ValueError("Resume PDF must not be encrypted")
        count=len(reader.pages)
        if not 1<=count<=100:
            raise ValueError("Resume PDF must contain 1-100 readable pages")
        for page in reader.pages:
            if float(page.mediabox.width)<=0 or float(page.mediabox.height)<=0:
                raise ValueError("Resume PDF contains an invalid page")
    except Exception as exc:
        raise ValueError("Resume PDF must be readable, unencrypted and contain 1-100 pages") from exc

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
    target = Path(path)
    target = (config.BASE_DIR/target).resolve() if not target.is_absolute() else target.resolve()
    if not target.is_relative_to(config.RESUME_DIR.resolve()):
        raise ValueError("Copy the PDF into RESUME_DIR before registering it")
    if not target.is_file() or target.stat().st_size > config.MAX_RESUME_BYTES:
        raise ValueError("Resume PDF is missing or exceeds the size limit")
    with target.open("rb") as source:
        data=source.read(config.MAX_RESUME_BYTES+1)
    validate_pdf(data)
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
    variants=[]
    for variant in list_resume_variants():
        try: delivery_asset(variant['id'])
        except (ValueError,OSError): continue
        variants.append(variant)
    if not variants:
        return None
    text = (job_text or "").casefold()
    return max(variants,key=lambda v: matching_score(v,text))

def matching_score(variant,text):
    return sum(bool(re.search(r'(?<!\w)'+re.escape(k.strip().casefold())+r'(?!\w)',(text or '').casefold())) for k in variant['keywords'].split(',') if k.strip())

def revise(variant_id,changes,file_path=None,archive=False):
    from db import get_connection
    from repository import timestamp,event
    from errors import Conflict
    old=get_variant(variant_id)
    if set(changes)-{'name','keywords','resume_url'}: raise ValueError('Invalid resume changes')
    values={**old,**changes}
    if not isinstance(values['name'],str) or not values['name'].strip() or len(values['name'])>100: raise ValueError('Resume name is required (at most 100 characters)')
    if not isinstance(values['keywords'],str) or len(values['keywords'])>1000: raise ValueError('Invalid keywords')
    values['resume_url']=safe_url(values.get('resume_url'))
    if file_path: values['file_path']=str(checked_pdf(file_path)[0])
    with get_connection(immediate=True) as conn:
        if not conn.execute('SELECT 1 FROM resume_variants WHERE id=? AND archived=0',(variant_id,)).fetchone(): raise Conflict('Resume already changed; reload')
        if conn.execute("SELECT 1 FROM emails WHERE resume_variant_id=? AND status IN ('sending','uncertain')",(variant_id,)).fetchone(): raise Conflict('Resolve in-flight delivery before changing this resume')
        new_id=None
        if not archive:
            new_id=conn.execute('INSERT INTO resume_variants(name,keywords,file_path,resume_url) VALUES (?,?,?,?)',(values['name'].strip(),values['keywords'],values['file_path'],values['resume_url'])).lastrowid
        conn.execute('UPDATE resume_variants SET archived=1 WHERE id=?',(variant_id,))
        affected=conn.execute("SELECT id FROM emails WHERE resume_variant_id=? AND status IN ('pending_review','approved')",(variant_id,)).fetchall()
        conn.execute("UPDATE emails SET resume_variant_id=?,status='pending_review',approval_json=NULL,evidence_verified_at=NULL,revision=revision+1,updated_at=? WHERE resume_variant_id=? AND status IN ('pending_review','approved')",(variant_id if archive else new_id,timestamp(),variant_id))
        for row in affected: event(conn,row['id'],'resume_changed',{'previous_variant':variant_id,'replacement_variant':new_id})
    return new_id

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
