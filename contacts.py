import csv
import io
import re
from pathlib import Path
from urllib.parse import urlparse
from errors import Conflict,NotFound
from repository import CompanyRepository,ContactRepository,EmailRepository
import validate
import resume

CSV_REQUIRED_COLUMNS=["company_name","contact_email"]
CSV_OPTIONAL_COLUMNS=["domain","job_url","job_text","notes","contact_name","contact_title","contact_source"]

def text(value,field,required=False,maximum=5000):
    if value is None:
        value=""
    if not isinstance(value,str) or len(value)>maximum:
        raise ValueError(f"{field} must be text under {maximum} characters")
    value=value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    return value or None

def normalize_company_name(name):
    return re.sub(r"\s+"," ",(name or "").strip()).rstrip(".")

def domain_name(value):
    if not value:
        return None
    value=text(value,"domain",maximum=253)
    if not value: return None
    value=value.lower()
    host=urlparse(value if "://" in value else "//"+value).hostname
    if not host or "." not in host or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",label) for label in host.rstrip(".").split(".")):
        raise ValueError("Enter a valid company domain")
    return host.rstrip(".")

def add_company(name,domain=None,job_url=None,job_text=None,notes=None):
    name=normalize_company_name(text(name,"name",True,200))
    if not name: raise ValueError("Company name is required")
    return CompanyRepository.create(name,domain_name(domain),resume.safe_url(job_url),text(job_text,"job_text",maximum=20000),text(notes,"notes"))

def add_contact(company_id,email,name=None,title=None,source=None):
    company=CompanyRepository.get_by_id(company_id)
    if not company or company["archived"]:
        raise NotFound("Company not found")
    return ContactRepository.create(company_id,validate.canonical_email(email),text(name,"name",maximum=200),text(title,"title",maximum=200),text(source,"source",maximum=500))

def find_company_by_name(name,domain=None):
    target=normalize_company_name(name)
    normalized=domain_name(domain)
    return CompanyRepository.find_identity(target,normalized)

def import_csv(file_path):
    with Path(file_path).open("r",encoding="utf-8-sig",newline="") as source:
        return import_stream(source)

def import_stream(source):
    summary={"companies_created":0,"contacts_created":0,"duplicates_skipped":0,"errors":[]}
    reader=csv.DictReader(source,strict=True)
    try: headers=reader.fieldnames
    except csv.Error as exc: raise ValueError("Malformed CSV header") from exc
    if not headers or len(headers)!=len(set(headers)) or any(c not in headers for c in CSV_REQUIRED_COLUMNS):
        raise ValueError("CSV needs unique headers including company_name and contact_email")
    if any(h not in CSV_REQUIRED_COLUMNS+CSV_OPTIONAL_COLUMNS for h in headers):
        raise ValueError("CSV contains unknown columns")
    try:
        for number,row in enumerate(reader,start=2):
            if number>10001:
                summary["errors"].append({"row":number,"error":"CSV is limited to 10000 rows; remaining rows were not imported"})
                break
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("Row has a different number of fields than the header")
                if any(len(value)>20000 for value in row.values()):
                    raise ValueError("Field exceeds size limit")
                name=normalize_company_name(text(row.get("company_name"),"company_name",True,200))
                email=validate.canonical_email(row.get("contact_email"))
                domain=domain_name(row.get("domain"))
                # Validate every value before creating a company.
                values=[text(row.get(key),key,maximum=200 if key in {"contact_name","contact_title"} else 5000)
                        for key in ("contact_name","contact_title","contact_source","notes")]
                job_url=resume.safe_url(row.get("job_url"))
                company=find_company_by_name(name,domain)
                if not company:
                    try:
                        cid=add_company(name,domain,job_url,row.get("job_text"),values[3])
                        summary["companies_created"]+=1
                    except Conflict:
                        company=find_company_by_name(name,domain)
                        if not company:
                            raise
                        cid=company["id"]
                else:
                    cid=company["id"]
                if ContactRepository.get_by_email_and_company(email,cid):
                    summary["duplicates_skipped"]+=1
                    continue
                try:
                    add_contact(cid,email,*values[:3])
                    summary["contacts_created"]+=1
                except Conflict:
                    summary["duplicates_skipped"]+=1
            except (ValueError,NotFound) as exc:
                summary["errors"].append({"row":number,"error":str(exc)})
    except csv.Error:
        summary["errors"].append({"row":reader.line_num,"error":"Malformed CSV; remaining rows were not imported"})
    return summary

def list_companies(limit=500,offset=0,search=""):
    return CompanyRepository.get_all(limit,offset,search)

def get_company(cid):
    result=CompanyRepository.get_by_id(cid)
    if not result or result["archived"]:
        raise NotFound("Company not found")
    return result

def get_contact(cid):
    result=ContactRepository.get_by_id(cid)
    if not result or result["archived"]:
        raise NotFound("Contact not found")
    return result

def list_contacts(company_id=None,limit=100,offset=0,search=""):
    return ContactRepository.get_all_by_company(company_id,limit,offset,search)

def get_emails_for_contact(cid):
    return EmailRepository.get_by_contact_id(cid)
