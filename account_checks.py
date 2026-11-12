"""Explicit account diagnostics. This module never submits an email."""
import hashlib
import imaplib
import json
import smtplib
import ssl
import config


def scope():
    values=(config.GMAIL_ADDRESS.strip().lower(),config.SMTP_HOST,str(config.SMTP_PORT),config.IMAP_HOST,config.IMAP_MAILBOX)
    return hashlib.sha256('\n'.join(values).encode()).hexdigest()

def check_mail():
    report={'scope':scope(),'checked_at':config.now().isoformat(),'smtp':{'status':'not_configured'},'imap':{'status':'not_configured'}}
    if not config.GMAIL_ADDRESS or not config.GMAIL_APP_PASSWORD: return report
    try: config.require_gmail_creds()
    except ValueError:
        report.update(smtp={'status':'invalid_configuration'},imap={'status':'invalid_configuration'})
        return report
    timeout=min(config.PROVIDER_TIMEOUT,15)
    server=None
    try:
        server=smtplib.SMTP(config.SMTP_HOST,config.SMTP_PORT,timeout=timeout)
        server.starttls(context=ssl.create_default_context())
        server.login(config.GMAIL_ADDRESS,config.GMAIL_APP_PASSWORD)
        code,_=server.noop()
        report['smtp']={'status':'verified' if code==250 else 'connection_rejected','smtp_code':int(code)}
    except smtplib.SMTPAuthenticationError:
        report['smtp']={'status':'authentication_failed','action':'Check the app password, 2-Step Verification and account/admin policy.'}
    except Exception:
        report['smtp']={'status':'connection_failed','action':'Check SMTP host/port, TLS support and connectivity; then retry explicitly.'}
    finally:
        if server:
            try: server.quit()
            except Exception:
                try: server.close()
                except Exception: pass
    mailbox=None
    try:
        mailbox=imaplib.IMAP4_SSL(config.IMAP_HOST,timeout=timeout)
        status,_=mailbox.login(config.GMAIL_ADDRESS,config.GMAIL_APP_PASSWORD)
        if status!='OK': raise imaplib.IMAP4.error('login failed')
        name=config.IMAP_MAILBOX
        selected=name if name=='INBOX' else '"'+name.replace('\\','\\\\').replace('"','\\"')+'"'
        status,_=mailbox.select(selected,readonly=True)
        report['imap']={'status':'verified' if status=='OK' else 'mailbox_unavailable','mailbox':name,
            'action':'Reply matching still needs a real thread/reply acceptance check.'}
    except imaplib.IMAP4.error:
        report['imap']={'status':'authentication_or_mailbox_failed','action':'Check credentials, selected mailbox and administrator restrictions.'}
    except Exception:
        report['imap']={'status':'connection_failed','action':'Check IMAP host, TLS and connectivity; then retry explicitly.'}
    finally:
        if mailbox:
            try: mailbox.logout()
            except Exception: pass
    return report

def saved_status():
    from repository import one
    row=one("SELECT value FROM settings WHERE key='mail_connection_check'")
    if not row: return {'smtp':'not_verified','imap':'not_verified'}
    report=json.loads(row['value'])
    if report.get('scope')!=scope(): return {'smtp':'configuration_changed','imap':'configuration_changed'}
    return {key:report[key]['status'] for key in ('smtp','imap')}|{'checked_at':report['checked_at']}

def check_and_save():
    from db import get_connection
    report=check_mail()
    with get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('mail_connection_check',?)",(json.dumps(report),))
    return report

def check_model():
    """One synthetic draft, existing maximum of three generation calls; never saved/sent."""
    if not config.GEMINI_API_KEY: return {'status':'not_configured','calls':0,'model':config.GEMINI_MODEL}
    import composer
    try:
        result=composer.compose_email({'name':'Example','domain':'example.test','job_text':'Synthetic Python backend role'},
            {'name':'Recruiting Team','title':'Recruiter'},'Synthetic candidate: entry-level backend target. Built a personal Python CSV validator; no business metrics or paid experience.')
        return {'status':'verified','model':config.GEMINI_MODEL,'calls':result.get('generation',{}).get('calls'),
            'generation':result.get('generation'),'draft':{key:result[key] for key in ('subject','body','research_notes')},
            'note':'Synthetic diagnostic only; account access is verified for this request, not live outreach quality.'}
    except Exception as exc:
        return {'status':'generation_failed','model':config.GEMINI_MODEL,'calls':getattr(exc,'generation',{}).get('calls'),
            'action':'Check API billing, model access, grounding/structured output support, quota and connectivity.'}
