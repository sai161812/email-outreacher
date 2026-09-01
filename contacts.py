import csv
from pathlib import Path
from repository import CompanyRepository, ContactRepository, EmailRepository

def list_companies():
    return [dict(r) for r in CompanyRepository.get_all()]

def get_company(company_id):
    row = CompanyRepository.get_by_id(company_id)
    if not row:
        raise ValueError(f"No company found with ID {company_id}")
    return dict(row)

def add_company(name, domain=None, job_url=None, job_text=None, notes=None):
    return CompanyRepository.create(name, domain, job_url, job_text, notes)

def add_contact(company_id, email, name=None, title=None, source=None):
    c = CompanyRepository.get_by_id(company_id)
    if not c:
        raise ValueError(f"Company ID {company_id} does not exist.")
    
    return ContactRepository.create(company_id, email, name, title, source)

def list_contacts(company_id=None):
    return [dict(r) for r in ContactRepository.get_all_by_company(company_id)]

def get_emails_for_contact(contact_id):
    return [dict(r) for r in EmailRepository.get_by_contact_id(contact_id)]

def import_csv(file_path):
    import_path = Path(file_path)
    if not import_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    stats = {"companies_added": 0, "contacts_added": 0, "skipped": 0}
    with import_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            company_name = row.get("company_name", "").strip()
            contact_email = row.get("contact_email", "").strip()

            if not company_name or not contact_email:
                stats["skipped"] += 1
                continue

            company_row = CompanyRepository.get_by_name(company_name)
            if company_row:
                company_id = company_row["id"]
            else:
                company_id = add_company(
                    name=company_name,
                    domain=row.get("company_domain", "").strip(),
                    job_url=row.get("job_url", "").strip(),
                    job_text=row.get("job_text", "").strip(),
                    notes=row.get("company_notes", "").strip(),
                )
                stats["companies_added"] += 1

            contact_row = ContactRepository.get_by_email_and_company(contact_email, company_id)
            if not contact_row:
                add_contact(
                    company_id=company_id,
                    email=contact_email,
                    name=row.get("contact_name", "").strip(),
                    title=row.get("contact_title", "").strip(),
                    source=row.get("contact_source", "").strip()
                )
                stats["contacts_added"] += 1
            else:
                stats["skipped"] += 1

    return stats
