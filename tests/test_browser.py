import threading
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import Mock
import pytest
from playwright.sync_api import sync_playwright,expect
from werkzeug.serving import make_server
import config
import composer
import jobs
import sender
from app import create_app

pytestmark=pytest.mark.browser

@pytest.fixture
def browser_app(temp_db,monkeypatch):
    monkeypatch.setattr(config,"GEMINI_API_KEY","synthetic-key")
    monkeypatch.setattr(config,"GMAIL_ADDRESS","owner@example.test")
    monkeypatch.setattr(config,"GMAIL_APP_PASSWORD","synthetic-password")
    monkeypatch.setattr(sender,"is_in_send_window",lambda *a:True)
    monkeypatch.setattr(sender.time,"sleep",lambda *a:None)
    smtp=Mock()
    monkeypatch.setattr(sender.smtplib,"SMTP",Mock(return_value=smtp))
    monkeypatch.setattr(composer,"compose_email",lambda *a:{
        "subject":'Quoted "subject"',"hook":"Verified company hook",
        "body":'Built a Python dashboard. </textarea><img src=x onerror="window.__injected=true"> Open to a chat?',
        "research_notes":"Verified source: https://example.test/source","grounding":[]})
    server=make_server("127.0.0.1",0,create_app({"TESTING":True}),threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        context=browser.new_context()
        context.route("**/*",lambda route:route.continue_() if urlsplit(route.request.url).hostname=="127.0.0.1" else route.abort())
        page=context.new_page()
        errors=[]
        page.on("pageerror",lambda error:errors.append(str(error)))
        yield page,f"http://127.0.0.1:{server.server_port}",smtp,errors
        context.close();browser.close()
    server.shutdown();thread.join(timeout=5)

def open_view(page,name):
    page.get_by_role("navigation").get_by_role("button",name=name,exact=True).click()

def test_review_edits_during_save_require_another_save(browser_app,contact):
    from repository import EmailRepository
    page,url,_,errors=browser_app
    company,person=contact
    eid=EmailRepository.create(company,person,None,"Hook","Subject","Original body",None)
    page.goto(url)
    open_view(page,"Review")
    held=[]
    page.route("**/api/review/*",lambda route:held.append(route))
    page.get_by_label("Body",exact=True).fill("First edit")
    page.get_by_role("button",name="Save edits",exact=True).click()
    page.get_by_label("Body",exact=True).fill("Newer edit while saving")
    expect(page.get_by_role("button",name="Reject",exact=True)).to_be_disabled()
    held.pop().continue_()
    expect(page.get_by_role("button",name="Save edits",exact=True)).to_be_enabled()
    approve=page.get_by_role("button",name="Approve saved revision")
    expect(approve).to_be_disabled()
    expect(page.get_by_label("Body",exact=True)).to_have_value("Newer edit while saving")
    assert EmailRepository.get_by_id(eid)["body"]=="First edit"
    page.unroute("**/api/review/*")
    page.get_by_role("button",name="Save edits",exact=True).click()
    expect(approve).to_be_enabled()
    # An approval in flight must lock editable content and other actions.
    page.route("**/api/review/*",lambda route:held.append(route))
    approve.click()
    expect(page.get_by_label("Body",exact=True)).to_be_disabled()
    expect(page.get_by_role("button",name="Save edits",exact=True)).to_be_disabled()
    held.pop().continue_()
    expect(approve).to_have_count(0)
    assert EmailRepository.get_by_id(eid)["body"]=="Newer edit while saving"
    assert EmailRepository.get_by_id(eid)["status"]=="approved"
    assert errors==[]

def test_settings_mutations_preserve_unsaved_profile(browser_app):
    page,url,_,errors=browser_app
    page.goto(url)
    open_view(page,"Settings")
    page.get_by_label("full name",exact=True).fill("Unsaved candidate")
    page.get_by_label("Candidate facts",exact=False).fill("Unsaved verified facts")
    page.get_by_label("Resume name",exact=True).fill("Link CV")
    page.get_by_label("HTTPS resume link",exact=False).fill("https://example.test/cv.pdf")
    page.get_by_role("button",name="Register resume",exact=True).click()
    expect(page.get_by_role("cell",name="Link CV",exact=True)).to_be_visible()
    expect(page.get_by_label("full name",exact=True)).to_have_value("Unsaved candidate")
    page.get_by_label("Email to suppress",exact=True).fill("blocked@example.test")
    page.get_by_label("Reason",exact=True).fill("Requested")
    page.get_by_role("button",name="Suppress address",exact=True).click()
    expect(page.get_by_role("cell",name="blocked@example.test",exact=True)).to_be_visible()
    expect(page.get_by_label("Candidate facts",exact=False)).to_have_value("Unsaved verified facts")
    page.get_by_role("button",name="Remove suppression",exact=True).click()
    expect(page.get_by_role("cell",name="blocked@example.test",exact=True)).to_have_count(0)
    expect(page.get_by_label("full name",exact=True)).to_have_value("Unsaved candidate")
    assert errors==[]

def test_expired_session_cannot_render_a_stale_dashboard(browser_app):
    page,url,_,errors=browser_app
    page.goto(url)
    expect(page.get_by_role("heading",name="Dashboard",exact=True)).to_be_visible()
    with page.expect_response(lambda response:response.url.endswith("/api/check_replies")):
        page.get_by_role("button",name="Check replies",exact=True).click()
    held=[]
    page.route("**/api/settings",lambda route:held.append(route))
    page.route("**/api/jobs/*",lambda route:route.fulfill(status=401,json={"error":"Sign in again"}))
    open_view(page,"Settings")
    # Background operation polling expires the session while a different,
    # successful view request is still in flight.
    expect(page.get_by_role("heading",name="Owner sign in",exact=True)).to_be_visible(timeout=10000)
    held.pop().continue_()
    trigger=page.get_by_role("navigation").get_by_role("button",name="Settings",exact=True)
    expect(trigger).not_to_have_attribute("aria-busy","true")
    expect(page.get_by_role("heading",name="Owner sign in",exact=True)).to_be_visible()
    expect(page.get_by_role("heading",name="Settings",exact=True)).to_have_count(0)
    expect(page.locator("#content")).to_have_attribute("aria-busy","false")
    assert errors==[]

def test_due_followup_review_send_and_reply_closes_thread(browser_app,contact,monkeypatch):
    from datetime import timedelta
    from email import message_from_bytes
    import candidate_profile
    import reviewer
    from repository import EmailRepository
    page,url,smtp,errors=browser_app
    company,person=contact
    candidate_profile.set_profile(full_name="Candidate")
    config.CONTEXT_PATH.write_text("Built a Python dashboard.",encoding="utf8")
    original=EmailRepository.create(company,person,None,"Hook","Original subject","Original body",None)
    current=config.now()
    monkeypatch.setattr(config,"now",lambda:current-timedelta(days=config.FOLLOW_UP_AFTER_DAYS+1))
    reviewer.approve(original)
    assert sender.run_send_batch()[0]["status"]=="sent"
    original_id=EmailRepository.get_by_id(original)["message_id"]
    monkeypatch.setattr(config,"now",lambda:current)
    monkeypatch.setattr(composer,"compose_follow_up",lambda *args:{"subject":"Re: Original subject","body":"Following up on my Python dashboard experience. Open to a brief chat?"})
    page.goto(url)
    open_view(page,"Tracking")
    with page.expect_response(lambda response:response.url.endswith(f"/api/tracking/{original}/followup")) as queued:
        page.get_by_role("button",name="Draft follow-up",exact=True).click()
    assert queued.value.status==202
    assert jobs.process_next()
    job=jobs.list_jobs()[0]
    assert job["status"]=="complete"
    followup=job["result"]["id"]
    open_view(page,"Review")
    expect(page.get_by_label("Subject",exact=True)).to_have_value("Re: Original subject")
    page.get_by_role("button",name="Approve saved revision").click()
    expect(page.get_by_role("button",name="Approve saved revision")).to_have_count(0)
    open_view(page,"Queue")
    with page.expect_response(lambda response:response.url.endswith("/api/send")) as queued:
        page.get_by_role("button",name="Send approved batch",exact=True).click()
    assert queued.value.status==202
    assert jobs.process_next()
    assert jobs.list_jobs()[0]["result"]["counts"]["sent"]==1
    assert smtp.sendmail.call_count==2
    delivered=message_from_bytes(smtp.sendmail.call_args.args[2])
    assert delivered["In-Reply-To"]==original_id
    assert delivered["References"]==original_id
    open_view(page,"Tracking")
    choice=page.get_by_label(f"Outcome for email #{followup}",exact=True)
    choice.select_option("replied")
    choice.locator("..").get_by_role("button",name="Apply outcome",exact=True).click()
    expect(page.get_by_role("cell",name="replied",exact=True)).to_have_count(2)
    assert EmailRepository.get_by_id(original)["status"]=="replied"
    assert EmailRepository.get_by_id(followup)["status"]=="replied"
    assert page.get_by_role("button",name="Draft follow-up",exact=True).count()==0
    assert errors==[]

def test_full_setup_review_send_workflow(browser_app):
    page,url,smtp,errors=browser_app
    page.goto(url)
    expect(page.get_by_role("heading",name="Dashboard",exact=True)).to_be_visible()
    open_view(page,"Companies")
    page.get_by_role("button",name="Add company",exact=True).click()
    dialog=page.get_by_role("dialog")
    dialog.get_by_label("name",exact=True).fill("Example")
    dialog.get_by_label("domain",exact=True).fill("example.test")
    dialog.get_by_label("job text",exact=True).fill("Python")
    dialog.get_by_role("button",name="Save",exact=True).click()
    expect(page.get_by_role("cell",name="Example",exact=True)).to_be_visible()
    open_view(page,"Settings")
    page.get_by_label("full name",exact=True).fill("Candidate")
    page.get_by_label("Candidate facts",exact=False).fill("Built a Python dashboard.")
    held=[]
    page.route("**/api/settings",lambda route:held.append(route) if route.request.method=="POST" else route.continue_())
    with page.expect_request(lambda request:request.url.endswith("/api/settings") and request.method=="POST"):
        page.get_by_role("button",name="Save profile and facts").click()
    # Typing into another setup form during a slow save must survive completion.
    page.get_by_label("Resume name",exact=True).fill("Python CV")
    assert len(held)==1
    held[0].continue_()
    expect(page.get_by_text("Profile and facts saved.",exact=True)).to_be_visible()
    expect(page.get_by_label("Resume name",exact=True)).to_have_value("Python CV")
    page.get_by_label("Matching keywords",exact=False).fill("python")
    page.get_by_label("PDF",exact=True).set_input_files({"name":"cv.pdf","mimeType":"application/pdf","buffer":b"%PDF-1.4\nsynthetic fixture"})
    page.get_by_role("button",name="Register resume").click()
    expect(page.get_by_role("cell",name="Python CV",exact=True)).to_be_visible()
    open_view(page,"Contacts")
    page.get_by_role("button",name="Add contact",exact=True).click()
    dialog=page.get_by_role("dialog")
    dialog.get_by_label("Name",exact=True).fill("Person")
    dialog.get_by_label("Email",exact=True).fill("person@example.test")
    dialog.get_by_role("button",name="Save",exact=True).click()
    expect(page.get_by_role("cell",name="person@example.test",exact=True)).to_be_visible()
    page.get_by_role("button",name="Draft",exact=True).click()
    expect(page.get_by_text("Operation queued.",exact=False)).to_be_visible()
    assert jobs.process_next()
    assert jobs.list_jobs()[0]["status"]=="complete"
    open_view(page,"Review")
    expect(page.get_by_label("Subject",exact=True)).to_have_value('Quoted "subject"')
    assert page.locator("img").count()==0
    assert page.evaluate("window.__injected") is None
    page.get_by_label("Subject",exact=True).fill('Reviewed "subject"')
    approve=page.get_by_role("button",name="Approve saved revision")
    expect(approve).to_be_disabled()
    page.get_by_role("button",name="Save edits").click()
    expect(approve).to_be_enabled()
    expect(page.get_by_text("Saved, awaiting approval",exact=False)).to_be_visible()
    approve.click()
    open_view(page,"Queue")
    expect(page.get_by_role("cell",name='Reviewed "subject"',exact=True)).to_be_visible()
    with page.expect_response(lambda response: response.url.endswith("/api/send") and response.request.method=="POST") as queued:
        page.get_by_role("button",name="Send approved batch").click()
    assert queued.value.status==202
    assert jobs.process_next()
    result=jobs.list_jobs()[0]
    assert result["status"]=="complete"
    assert result["result"]["counts"]["sent"]==1
    assert smtp.sendmail.call_count==1
    open_view(page,"Tracking")
    expect(page.get_by_role("cell",name="sent",exact=True)).to_be_visible()
    page.get_by_role("combobox").select_option("replied")
    page.get_by_role("button",name="Apply outcome").click()
    expect(page.get_by_role("cell",name="replied",exact=True)).to_be_visible()
    Path("test-results").mkdir(exist_ok=True)
    page.screenshot(path="test-results/workflow-desktop.png",full_page=True)
    assert errors==[]

@pytest.mark.parametrize("width",[375,768,1440])
def test_responsive_keyboard_dialog(browser_app,width):
    page,url,_,errors=browser_app
    page.set_viewport_size({"width":width,"height":900})
    page.goto(url)
    open_view(page,"Companies")
    trigger=page.get_by_role("button",name="Add company",exact=True)
    trigger.focus();page.keyboard.press("Enter")
    expect(page.get_by_role("dialog")).to_be_visible()
    expect(page.get_by_label("name",exact=True)).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(trigger).to_be_focused()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    Path("test-results").mkdir(exist_ok=True)
    page.screenshot(path=f"test-results/responsive-{width}.png",full_page=True)
    assert errors==[]
