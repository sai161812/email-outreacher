import io
import secrets
import pytest
import config
from app import create_app
from repository import EmailRepository

@pytest.fixture
def client(temp_db):
    return create_app({"TESTING":True}).test_client()

def post(client,path,data,method="post",**kwargs):
    token=client.get("/api/session").get_json()["csrf"]
    body={"data":"null","content_type":"application/json"} if data is None else {"json":data}
    return getattr(client,method)(path,**body,headers={"X-CSRF-Token":token,"Idempotency-Key":secrets.token_hex(16)},**kwargs)

def test_fresh_factory_and_read_routes(client):
    for path in ["/","/api/stats","/api/contacts","/api/companies","/api/settings","/api/review","/api/queue","/api/tracking","/api/tracking/due","/api/jobs","/api/attempts"]:
        assert client.get(path).status_code==200,path

@pytest.mark.parametrize("data",[None,[],{},{"name":""},{"name":123},{"name":"Valid","unknown":"x"}])
def test_bad_company_requests_are_json(client,data):
    response=post(client,"/api/companies",data)
    assert response.status_code==400
    assert "error" in response.get_json()

def test_company_contact_setup(client):
    company=post(client,"/api/companies",{"name":"New","domain":"new.test"})
    assert company.status_code==201
    contact=post(client,"/api/contacts",{"company_id":company.get_json()["id"],"email":"test@new.test"})
    assert contact.status_code==201
    assert post(client,"/api/contacts",{"company_id":True,"email":"test@new.test"}).status_code==400

def test_host_origin_and_csrf_protection(client):
    assert client.get("/api/stats",headers={"Host":"untrusted.example"}).status_code==403
    assert client.post("/api/send",json={}).status_code==403
    token=client.get("/api/session").get_json()["csrf"]
    response=client.post("/api/send",json={},headers={"X-CSRF-Token":token,"Origin":"https://untrusted.example","Idempotency-Key":"request_key_1"})
    assert response.status_code==403

def test_action_validation_and_notfound(client,contact):
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    assert post(client,f"/api/review/{eid}",{"action":"typo","revision":1}).status_code==400
    assert post(client,"/api/review/9999",{"action":"approve","revision":1}).status_code==404
    assert post(client,f"/api/tracking/{eid}/mark",{"status":[]}).status_code==400
    assert post(client,f"/api/tracking/{eid}/mark",{"status":"offer"}).status_code==409

def test_revision_required_and_conflicts(client,contact):
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    assert post(client,f"/api/review/{eid}",{"action":"approve"}).status_code==400
    assert post(client,f"/api/review/{eid}",{"action":"edit","revision":1,"body":"Changed"}).status_code==200
    assert post(client,f"/api/review/{eid}",{"action":"approve","revision":1}).status_code==409
    assert post(client,f"/api/review/{eid}",{"action":"approve","revision":2}).status_code==200

def test_unique_stream_upload_and_invalid_encoding(client):
    token=client.get("/api/session").get_json()["csrf"]
    for _ in range(2):
        response=client.post("/api/contacts/import",data={"file":(io.BytesIO(b"company_name,contact_email\nUpload,p@upload.test\n"),"same.csv")},headers={"X-CSRF-Token":token})
        assert response.status_code==200
    assert response.get_json()["duplicates_skipped"]==1
    response=client.post("/api/contacts/import",data={"file":(io.BytesIO(b"\xff"),"bad.csv")},headers={"X-CSRF-Token":token})
    assert response.status_code==400

def test_send_enqueues_idempotently(client):
    token=client.get("/api/session").get_json()["csrf"]
    headers={"X-CSRF-Token":token,"Idempotency-Key":"same_request_123"}
    first=client.post("/api/send",json={},headers=headers)
    second=client.post("/api/send",json={},headers=headers)
    assert first.status_code==second.status_code==202
    assert first.get_json()["id"]==second.get_json()["id"]
    assert first.get_json()["status"]=="pending"

def test_owner_authentication(temp_db,monkeypatch):
    monkeypatch.setattr(config,"OWNER_PASSWORD","test-password")
    monkeypatch.setattr(config,"SECRET_KEY","a"*32)
    client=create_app({"TESTING":True}).test_client()
    assert client.get("/api/stats").status_code==401
    assert post(client,"/api/login",{"password":"bad"}).status_code==401
    assert post(client,"/api/login",{"password":"test-password"}).status_code==200
    assert client.get("/api/stats").status_code==200

def test_remote_configuration_fails_closed(temp_db,monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS","example.test")
    monkeypatch.setattr(config,"OWNER_PASSWORD","")
    with pytest.raises(ValueError,match="requires"):
        create_app()

def test_invalid_profile_does_not_overwrite_context(client):
    config.CONTEXT_PATH.write_text("Original facts",encoding="utf8")
    response=post(client,"/api/settings",{"profile":{"full_name":""},"candidate_context":"Replacement"})
    assert response.status_code==400
    assert config.CONTEXT_PATH.read_text(encoding="utf8")=="Original facts"

def test_unsent_reply_is_rejected(client,contact):
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    assert post(client,f"/api/tracking/{eid}/mark",{"status":"replied"}).status_code==409

def test_optional_dns_warning(client,contact,monkeypatch):
    import validate
    monkeypatch.setattr(validate,"has_mx_record",lambda domain:None)
    _,person=contact
    response=post(client,f"/api/contacts/{person}/validate",{})
    assert response.status_code==200
    assert "inconclusive" in response.get_json()["warning"]

def test_remote_requires_https(temp_db,monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS","example.test")
    monkeypatch.setattr(config,"OWNER_PASSWORD","synthetic")
    monkeypatch.setattr(config,"SECRET_KEY","s"*32)
    monkeypatch.delenv("COOKIE_SECURE",raising=False)
    with pytest.raises(ValueError,match="HTTPS"):
        create_app()
    monkeypatch.setenv("COOKIE_SECURE","1")
    client=create_app({"TESTING":True}).test_client()
    assert client.get("/api/session",base_url="http://example.test").status_code==403
    assert client.get("/api/session",base_url="https://example.test").status_code==200

@pytest.mark.parametrize("path",[
    "/api/settings","/api/companies","/api/contacts","/api/suppressions",
    "/api/review/9999","/api/tracking/9999/mark","/api/compose",
    "/api/tracking/9999/followup","/api/send","/api/check_replies",
    "/api/attempts/9999/reconcile","/api/emails/9999/retry","/api/resumes"])
def test_mutation_null_body_has_safe_json_error(client,path):
    response=post(client,path,None)
    assert response.status_code==400
    assert response.get_json()["error"]

def test_contact_edit_is_blocked_while_delivery_in_flight(client,contact):
    import reviewer,delivery
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    reviewer.approve(eid)
    delivery.claim(eid)
    response=post(client,f"/api/contacts/{person}",{"email":"changed@example.test"},method="patch")
    assert response.status_code==409
    response=post(client,f"/api/companies/{company}",{"name":"Changed"},method="patch")
    assert response.status_code==409

def test_contact_edit_revokes_exact_approval(client,contact):
    import reviewer
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    reviewer.approve(eid)
    assert post(client,f"/api/contacts/{person}",{"name":"New name"},method="patch").status_code==200
    row=EmailRepository.get_by_id(eid)
    assert row["status"]=="pending_review" and row["revision"]==2

def test_archiving_contact_cancels_unsubmitted_work(client,contact):
    import reviewer
    company,person=contact
    eid=EmailRepository.create(company,person,None,"H","S","B",None)
    reviewer.approve(eid)
    assert post(client,f"/api/contacts/{person}",{"archived":True},method="patch").status_code==200
    assert EmailRepository.get_by_id(eid)["status"]=="canceled"
    assert client.get("/api/queue").get_json()==[]

def test_concurrent_fresh_read_requests_do_not_change_journal_mode(temp_db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    app=create_app({"TESTING":True})
    barrier=Barrier(8,timeout=10)
    def read(index):
        with app.test_client() as client:
            barrier.wait()
            return client.get("/api/stats" if index%2 else "/api/settings").status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(read,range(8)))==[200]*8
