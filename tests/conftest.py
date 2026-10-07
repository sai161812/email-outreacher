import os
import socket
import tempfile
from pathlib import Path
import pytest

# Import-time application setup must never open the user's database.
_session = tempfile.TemporaryDirectory(prefix="outreach-test-session-")
os.environ["OUTREACH_DB_PATH"] = str(Path(_session.name) / "session.db")

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Real network is forbidden in tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    import config
    import db
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "CONTEXT_PATH", tmp_path / "candidate_context.txt")
    monkeypatch.setattr(config, "RESUME_DIR", tmp_path / "resumes")
    config.RESUME_DIR.mkdir()
    db.init_db()
    return config.DB_PATH

@pytest.fixture
def contact(temp_db):
    from repository import CompanyRepository, ContactRepository
    company = CompanyRepository.create("Example", "example.test", None, "Python", None)
    person = ContactRepository.create(company, "person@example.test", "Person", None, None)
    return company, person
