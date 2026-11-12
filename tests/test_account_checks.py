import json
from unittest.mock import Mock
import smtplib
import config,account_checks

def test_unconfigured_checks_never_connect(monkeypatch):
    monkeypatch.setattr(config,'GMAIL_ADDRESS','');monkeypatch.setattr(config,'GMAIL_APP_PASSWORD','')
    smtp=Mock();imap=Mock()
    monkeypatch.setattr(account_checks.smtplib,'SMTP',smtp);monkeypatch.setattr(account_checks.imaplib,'IMAP4_SSL',imap)
    report=account_checks.check_mail()
    assert report['smtp']['status']==report['imap']['status']=='not_configured'
    smtp.assert_not_called();imap.assert_not_called()

def test_checks_authenticate_without_sending_or_mutating_mailbox(monkeypatch):
    monkeypatch.setattr(config,'GMAIL_ADDRESS','owner@example.test');monkeypatch.setattr(config,'GMAIL_APP_PASSWORD','private-password')
    smtp=Mock();smtp.noop.return_value=(250,b'OK')
    imap=Mock();imap.login.return_value=('OK',[]);imap.select.return_value=('OK',[])
    monkeypatch.setattr(account_checks.smtplib,'SMTP',Mock(return_value=smtp));monkeypatch.setattr(account_checks.imaplib,'IMAP4_SSL',Mock(return_value=imap))
    report=account_checks.check_mail()
    assert report['smtp']['status']==report['imap']['status']=='verified'
    smtp.sendmail.assert_not_called();imap.store.assert_not_called();imap.expunge.assert_not_called()
    imap.select.assert_called_once_with('INBOX',readonly=True)
    smtp.quit.assert_called_once();imap.logout.assert_called_once()
    assert 'private-password' not in json.dumps(report)

def test_authentication_errors_are_redacted_and_clients_close(monkeypatch):
    monkeypatch.setattr(config,'GMAIL_ADDRESS','owner@example.test');monkeypatch.setattr(config,'GMAIL_APP_PASSWORD','secret')
    smtp=Mock();smtp.login.side_effect=smtplib.SMTPAuthenticationError(535,b'private-provider-text')
    imap=Mock();imap.login.side_effect=account_checks.imaplib.IMAP4.error('private-provider-text')
    monkeypatch.setattr(account_checks.smtplib,'SMTP',Mock(return_value=smtp));monkeypatch.setattr(account_checks.imaplib,'IMAP4_SSL',Mock(return_value=imap))
    report=account_checks.check_mail()
    assert report['smtp']['status']=='authentication_failed' and report['imap']['status']=='authentication_or_mailbox_failed'
    assert 'private-provider-text' not in json.dumps(report)
    smtp.quit.assert_called_once();imap.logout.assert_called_once()

def test_saved_results_are_scoped_to_account(temp_db,monkeypatch):
    monkeypatch.setattr(config,'GMAIL_ADDRESS','owner@example.test');monkeypatch.setattr(config,'GMAIL_APP_PASSWORD','synthetic-password')
    monkeypatch.setattr(account_checks,'check_mail',lambda:{'scope':account_checks.scope(),'checked_at':'2026-11-12','smtp':{'status':'verified'},'imap':{'status':'verified'}})
    account_checks.check_and_save()
    assert account_checks.saved_status()['smtp']=='verified'
    monkeypatch.setattr(config,'GMAIL_ADDRESS','different@example.test')
    assert account_checks.saved_status()['smtp']=='configuration_changed'

def test_unconfigured_model_check_makes_zero_calls(monkeypatch):
    monkeypatch.setattr(config,'GEMINI_API_KEY','')
    assert account_checks.check_model()['calls']==0
