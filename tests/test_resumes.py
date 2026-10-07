from email import message_from_bytes
import pytest
import config
import resume
import reviewer
import sender
from errors import NotFound
from repository import EmailRepository
from test_sender import mail

@pytest.mark.parametrize("value",["http://example.test","javascript:alert(1)","https://user:pass@example.test","https://example.test/a b",True])
def test_unsafe_urls_rejected(value):
    with pytest.raises(ValueError): resume.safe_url(value)

def test_invalid_and_missing_pdfs_block_registration(temp_db,tmp_path):
    for name,data in [("plain.pdf",b"plain text"),("big.pdf",b"%PDF-"+b"x"*config.MAX_RESUME_BYTES)]:
        path=config.RESUME_DIR/name;path.write_bytes(data)
        with pytest.raises(ValueError): resume.add_resume_variant("Bad","",str(path))
    with pytest.raises(ValueError): resume.add_resume_variant("Missing","",str(config.RESUME_DIR/"missing.pdf"))
    outside=tmp_path/"outside.pdf";outside.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError): resume.add_resume_variant("Outside","",str(outside))

def test_link_mode_and_deterministic_matching(contact,mail,monkeypatch):
    monkeypatch.setattr(config,"RESUME_ATTACH_MODE","link")
    first=resume.add_resume_variant("First","python",resume_url="https://example.test/one.pdf")
    resume.add_resume_variant("Second","python",resume_url="https://example.test/two.pdf")
    assert resume.pick_best_variant(None)["id"]==first
    assert resume.pick_best_variant("Python")["id"]==first
    company,person=contact
    eid=EmailRepository.create(company,person,first,"H","S","B",None)
    reviewer.approve(eid)
    assert sender.run_send_batch()[0]["status"]=="sent"
    message=message_from_bytes(mail.sendmail.call_args.args[2])
    assert "https://example.test/one.pdf" in message.get_payload(decode=True).decode()
    assert not message.is_multipart()

def test_unknown_variant_fails(temp_db):
    with pytest.raises(NotFound): resume.get_variant(9999)
