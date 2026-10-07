import io
from concurrent.futures import ThreadPoolExecutor
import pytest
import contacts
import validate
from errors import Conflict

@pytest.mark.parametrize("address",[".person@example.test","p..name@example.test","p.@example.test","bad","a@local",None])
def test_invalid_addresses(address):
    assert not validate.is_valid_syntax(address)

def test_canonical_dedup(contact):
    company,_=contact
    with pytest.raises(Conflict):
        contacts.add_contact(company," PERSON@EXAMPLE.TEST ")
    assert contacts.list_contacts()[0]["email"]=="person@example.test"

def test_import_is_repeatable(temp_db):
    data="company_name,contact_email\nNew,new@example.test\n"
    assert contacts.import_stream(io.StringIO(data))["contacts_created"]==1
    result=contacts.import_stream(io.StringIO(data))
    assert result["contacts_created"]==0 and result["duplicates_skipped"]==1

@pytest.mark.parametrize("data",["","company_name\nA\n","company_name,company_name,contact_email\nA,A,a@a.test\n"])
def test_bad_headers(temp_db,data):
    with pytest.raises(ValueError):
        contacts.import_stream(io.StringIO(data))

def test_bad_row_does_not_create_company(temp_db):
    result=contacts.import_stream(io.StringIO("company_name,contact_email,job_url\nFake,bad,https://example.test\n"))
    assert result["errors"][0]["row"]==2
    assert contacts.list_companies()==[]

def test_concurrent_contact_insert(contact):
    company,_=contact
    def insert(_):
        try: return contacts.add_contact(company,"same@example.test")
        except Conflict: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(bool(v) for v in pool.map(insert,range(2)))==1

@pytest.mark.parametrize("domain",["bad..test","-bad.test","bad-.test"])
def test_invalid_domain_labels_rejected(domain):
    import contacts
    with pytest.raises(ValueError): contacts.domain_name(domain)

def test_blank_domain_is_optional():
    import contacts
    assert contacts.domain_name("   ") is None

def test_malformed_tail_reports_committed_rows(temp_db):
    report=contacts.import_stream(io.StringIO('company_name,contact_email\nValid,valid@example.test\n"unfinished'))
    assert report["contacts_created"]==1
    assert len(contacts.list_contacts())==1
    assert "Malformed" in report["errors"][0]["error"]

def test_unicode_company_identity_reimport(temp_db):
    data="company_name,contact_email\nStraße,p@example.test\n"
    assert contacts.import_stream(io.StringIO(data))["contacts_created"]==1
    assert contacts.import_stream(io.StringIO(data))["duplicates_skipped"]==1
