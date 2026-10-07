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
    page.get_by_role("button",name="Save profile and facts").click()
    expect(page.get_by_label("full name",exact=True)).to_have_value("Candidate")
    page.get_by_label("Resume name",exact=True).fill("Python CV")
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
