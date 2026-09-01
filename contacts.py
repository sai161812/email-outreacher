import csv
import re
from pathlib import Path
from repository import CompanyRepository, ContactRepository, EmailRepository
import validate

CSV_REQUIRED_COLUMNS = ["company_name", "contact_email"]
CSV_OPTIONAL_COLUMNS = [
    "domain", "job_url", "notes",
    "contact_name", "contact_title", "contact_source",
]

def add_company(name, domain=None, job_url=None, job_text=None, notes=None):
    return CompanyRepository.create(name, domain, job_url, job_text, notes)

def add_contact(company_id, email, name=None, title=None, source=None):
    if not validate.is_valid_syntax(email):
        raise ValueError(f"Invalid email address: {email}")
        
    c = CompanyRepository.get_by_id(company_id)
    if not c:
        raise ValueError(f"Company ID {company_id} does not exist.")
    
    return ContactRepository.create(company_id, email, name, title, source)

def normalize_company_name(name):
    if not name:
        return ""
    n = re.sub(r'\s+', ' ', name.strip())
    return n.rstrip('.')

def find_company_by_name(name, domain=None):
    if domain:
        # SQLite raw was used before, let's use repository
        # It's fine to do it here via the repo by getting all and matching
        pass
    
    norm_name = normalize_company_name(name)
    rows = CompanyRepository.get_all()
    
    if domain:
        for r in rows:
            if r["domain"] and r["domain"].strip().lower() == domain.strip().lower():
                return r

    for r in rows:
        if normalize_company_name(r["name"]).lower() == norm_name.lower():
            return r

    return None

def import_csv(file_path):
    summary = {"companies_created": 0, "contacts_created": 0, "errors": []}
    company_cache = {}  # name.lower() -> company_id
    
    import_path = Path(file_path)
    if not import_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    with import_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        missing = [c for c in CSV_REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"CSV is missing required column(s): {', '.join(missing)}. "
                f"Required: {', '.join(CSV_REQUIRED_COLUMNS)}"
            )

        for i, row in enumerate(reader, start=2):
            name = (row.get("company_name") or "").strip()
            email = (row.get("contact_email") or "").strip()

            if not name or not email:
                summary["errors"].append((i, "missing company_name or contact_email"))
                continue

            if not validate.is_valid_syntax(email):
                summary["errors"].append((i, f"Invalid email format: {email}"))
                continue

            domain = (row.get("domain") or "").strip()
            cache_key = (normalize_company_name(name).lower(), domain.lower() if domain else "")
            
            if cache_key in company_cache:
                company_id = company_cache[cache_key]
            else:
                existing = find_company_by_name(name, domain)
                if existing:
                    company_id = existing["id"]
                else:
                    company_id = add_company(
                        name=normalize_company_name(name),
                        domain=domain or None,
                        job_url=(row.get("job_url") or "").strip() or None,
                        notes=(row.get("notes") or "").strip() or None,
                    )
                    summary["companies_created"] += 1
                company_cache[cache_key] = company_id

            try:
                add_contact(
                    company_id,
                    email,
                    name=(row.get("contact_name") or "").strip() or None,
                    title=(row.get("contact_title") or "").strip() or None,
                    source=(row.get("contact_source") or "").strip() or None,
                )
                summary["contacts_created"] += 1
            except ValueError as e:
                summary["errors"].append((i, str(e)))

    return summary

def list_companies():
    return [dict(r) for r in CompanyRepository.get_all()]

def get_company(company_id):
    row = CompanyRepository.get_by_id(company_id)
    return dict(row) if row else None

def get_contact(contact_id):
    row = ContactRepository.get_by_id(contact_id)
    return dict(row) if row else None

def list_contacts(company_id=None):
    return [dict(r) for r in ContactRepository.get_all_by_company(company_id)]

def find_contact_without_email(company_id):
    contacts_list = list_contacts(company_id)
    out = []
    for c in contacts_list:
        emails = get_emails_for_contact(c["id"])
        if not emails:
            out.append(c)
    return out

def get_emails_for_contact(contact_id):
    return [dict(r) for r in EmailRepository.get_by_contact_id(contact_id)]
