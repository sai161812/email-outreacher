"""Incremental, read-only IMAP scanning with exact thread matching."""
import email
import imaplib
import json
import re
from datetime import timezone
from email.utils import getaddresses,parsedate_to_datetime
from email.message import Message
import config
import tracker
from errors import ProviderError,Conflict
from db import get_connection
from repository import EmailRepository,rows,timestamp
from followups import parsed_time


def unresolved_candidates():
    return rows("""SELECT e.id,a.id attempt_id,a.message_id,a.recipient contact_email,'sent' status,
        COALESCE((SELECT created_at FROM events v WHERE v.email_id=e.id AND v.kind='submission_started'
          AND json_extract(v.detail,'$.attempt_id')=a.id ORDER BY v.id LIMIT 1),a.created_at) sent_at
        FROM send_attempts a JOIN emails e ON e.id=a.email_id
        WHERE a.state IN ('submitting','uncertain') AND e.sent_at IS NULL""")


def replay_evidence():
    # Idempotent outcome transitions allow recovery after a crash between applying
    # an outcome and marking evidence processed. No message body is retained.
    pending=rows("""SELECT r.*,a.state FROM reply_evidence r JOIN send_attempts a ON a.id=r.attempt_id
        WHERE r.processed=0 AND a.state IN ('accepted','failed','canceled')""")
    for item in pending:
        if item['state']=='accepted':
            if item['kind']=='human': tracker.mark_replied(item['email_id'])
            else:
                try: tracker.mark_bounced(item['email_id'],suppress=item['kind']=='bounced')
                except Conflict: pass
        with get_connection() as conn:
            conn.execute('UPDATE reply_evidence SET processed=1 WHERE scope=? AND uid=? AND attempt_id=?',
                (item['scope'],item['uid'],item['attempt_id']))

def _failed_recipients(message,invalid_only=False):
    recipients=set()
    if message.get_content_type()!="multipart/report" or not isinstance(message.get_payload(),list):
        return recipients
    for part in message.get_payload():
        if part.get_content_type()!="message/delivery-status" or not isinstance(part.get_payload(),list):
            continue
        for block in part.get_payload():
            if not isinstance(block,Message): continue
            if block.get("Action","").strip().lower()!="failed" or not re.fullmatch(r"5\.\d{1,3}\.\d{1,3}",block.get("Status","").strip()):
                continue
            if invalid_only and block.get('Status','').strip()!='5.1.1': continue
            for name in ("Original-Recipient","Final-Recipient"):
                address_type,separator,address=block.get(name,"").partition(";")
                if separator and address_type.strip().lower()=="rfc822":
                    from validate import canonical_email
                    try: recipients.add(canonical_email(address.strip()))
                    except ValueError: pass
    return recipients

def _returned_ids(message):
    """Use the returned message's own ID, never IDs quoted in its body."""
    ids=set()
    for part in message.get_payload() if isinstance(message.get_payload(),list) else []:
        originals=[]
        if part.get_content_type()=="message/rfc822" and isinstance(part.get_payload(),list):
            originals=part.get_payload()
        elif part.get_content_type()=="text/rfc822-headers":
            raw=part.get_payload(decode=True)
            if raw: originals=[email.message_from_bytes(raw)]
        for original in originals:
            ids.update(re.findall(r"<[^<>\s]+>",original.get("Message-ID","")))
    return ids

def classify(message):
    if message.get_content_type()=="multipart/report":
        return "bounced" if _failed_recipients(message) else "automatic"
    if message.get("Auto-Submitted","no").lower()!="no" or message.get("Precedence","").lower() in {"bulk","list","junk"} or message.get("X-Autoreply") or message.get("X-Autorespond"):
        return "automatic"
    return "human"

def matched_candidates(message,candidates):
    ids=set(re.findall(r"<[^<>\s]+>", " ".join(message.get_all("References",[])+message.get_all("In-Reply-To",[]))))
    senders={a.strip().lower() for _,a in getaddresses(message.get_all("From",[]))}
    try:
        received=parsedate_to_datetime(message.get("Date",""))
        if not received.tzinfo: received=received.replace(tzinfo=timezone.utc)
    except (TypeError,ValueError,IndexError):
        return []
    kind=classify(message)
    if kind=="automatic":
        return []
    if kind=="bounced":
        # DSNs commonly omit outer reply headers. RFC 3464/6522 allow either
        # the original message or just its headers as the report's third part.
        ids=_returned_ids(message) or ids
        failed=_failed_recipients(message)
        return [c for c in candidates if c.get("message_id") in ids and c["sent_at"] and received>=parsed_time(c["sent_at"]).replace(microsecond=0)
                and c["contact_email"].strip().lower() in failed and c["status"] in {"sent","ghosted"}]
    return [c for c in candidates if c.get("message_id") in ids and c["sent_at"] and received>=parsed_time(c["sent_at"]).replace(microsecond=0)
            and c["contact_email"].strip().lower() in senders]

def _ok(result,operation):
    status,data=result
    if status!="OK":
        raise ProviderError(f"IMAP {operation} failed")
    return data

def check_replies(dry_run=False,detailed=False):
    config.require_gmail_creds()
    from delivery import bind_mailbox
    with get_connection(immediate=True) as conn: bind_mailbox(conn)
    candidates=EmailRepository.get_sent_candidates_for_replies()
    unresolved=unresolved_candidates()
    replay_evidence()
    if not candidates and not unresolved and not detailed:
        return []
    mailbox=None
    matches=[]
    scanned=0;skipped=0
    previous_scan=rows("SELECT value FROM settings WHERE key='reply_scan'")
    prior=json.loads(previous_scan[0]['value']) if previous_scan else {}
    last_success=prior.get('last_successful_at') if prior.get('mailbox')==config.IMAP_MAILBOX and prior.get('account')==config.GMAIL_ADDRESS.strip().lower() else None
    if not dry_run:
        with get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('reply_scan',?)",(json.dumps({'complete':False,'mailbox':config.IMAP_MAILBOX,'account':config.GMAIL_ADDRESS.lower(),'last_successful_at':last_success}),))
    try:
        mailbox=imaplib.IMAP4_SSL(config.IMAP_HOST,timeout=config.PROVIDER_TIMEOUT)
        _ok(mailbox.login(config.GMAIL_ADDRESS,config.GMAIL_APP_PASSWORD),"login")
        name=config.IMAP_MAILBOX
        selected=name if name=='INBOX' else '"'+name.replace('\\','\\\\').replace('"','\\"')+'"'
        _ok(mailbox.select(selected,readonly=True),"select")
        validity_data=mailbox.response("UIDVALIDITY")[1]
        validity=(validity_data[0] if validity_data else b"unknown").decode()
        if validity=="unknown":
            raise ProviderError("IMAP UIDVALIDITY is unavailable")
        scope=f"{config.GMAIL_ADDRESS.lower()}:{config.IMAP_MAILBOX}:{validity}"
        previous=rows("SELECT value FROM settings WHERE key=?",("imap_cursor:"+scope,))
        last=int(previous[0]["value"]) if previous else 0
        found=_ok(mailbox.uid("search",None,"UID",f"{last+1}:*"),"search")
        uids=[int(v) for v in (found[0] or b"").split() if int(v)>last]
        for uid in sorted(uids)[:500]:
            scanned+=1
            processed=rows("SELECT 1 FROM reply_messages WHERE uidvalidity=? AND uid=?",(scope,str(uid)))
            if processed: continue
            fetched=_ok(mailbox.uid("fetch",str(uid),"(BODY.PEEK[HEADER] RFC822.SIZE)"),"fetch")
            chunks=[v for v in fetched if isinstance(v,tuple)]
            if not chunks:
                raise ProviderError("IMAP returned an unreadable message header")
            metadata,raw=chunks[0]
            message=email.message_from_bytes(raw)
            skip_report=False
            if message.get_content_type()=="multipart/report":
                sizes=re.findall(rb"RFC822.SIZE (\d+)",metadata)
                if not sizes or int(sizes[0])>config.MAX_UPLOAD_BYTES:
                    skip_report=True
                    skipped+=1
                    matches.append({"uid":uid,"kind":"skipped_report","reason":"Delivery report is too large or has no size; inspect it manually in the configured mailbox"})
                else:
                    complete=_ok(mailbox.uid("fetch",str(uid),"(BODY.PEEK[])"),"fetch delivery report")
                    raw=next((v[1] for v in complete if isinstance(v,tuple)),None)
                    if raw is None: raise ProviderError("IMAP returned an unreadable delivery report")
                    message=email.message_from_bytes(raw)
            matched=[] if skip_report else matched_candidates(message,candidates)
            held=[] if skip_report else matched_candidates(message,unresolved)
            for candidate in matched:
                kind=classify(message)
                matches.append({"email_id":candidate["id"],"contact_email":candidate["contact_email"],"match_type":"exact_thread","kind":kind})
                if not dry_run:
                    if kind=="bounced":
                        try: tracker.mark_bounced(candidate["id"],suppress=candidate['contact_email'].strip().lower() in _failed_recipients(message,True))
                        except Conflict:
                            matches[-1].update(applied=False,reason="Outcome changed; delivery report ignored")
                    else: tracker.mark_replied(candidate["id"])
            if not dry_run:
                with get_connection() as conn:
                    if skip_report:
                        conn.execute('INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)',('reply_report:'+scope+':'+str(uid),json.dumps({'mailbox':config.IMAP_MAILBOX,'uid':uid})))
                    for candidate in held:
                        kind=classify(message)
                        if kind=='bounced' and candidate['contact_email'].strip().lower() not in _failed_recipients(message,True): kind='delivery_rejected'
                        conn.execute('INSERT OR IGNORE INTO reply_evidence(scope,uid,attempt_id,email_id,kind) VALUES (?,?,?,?,?)',
                            (scope,str(uid),candidate['attempt_id'],candidate['id'],kind))
                    conn.execute("INSERT OR IGNORE INTO reply_messages VALUES (?,?,?,?)",(scope,str(uid),message.get("Message-ID"),timestamp()))
                    conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",("imap_cursor:"+scope,str(uid)))
        prefix='reply_report:'+scope+':'
        pending=rows('SELECT count(*) n FROM settings WHERE substr(key,1,?)=?',(len(prefix),prefix))[0]['n']
        result={'matches':matches,'scanned':scanned,'skipped':skipped,'unreviewed_reports':pending,'remaining':max(0,len(uids)-500),
            'complete':len(uids)<=500 and skipped==0 and pending==0,'mailbox':config.IMAP_MAILBOX,
            'account':config.GMAIL_ADDRESS.strip().lower(),'checked_at':timestamp()}
        result['last_successful_at']=result['checked_at'] if result['complete'] else last_success
        if not dry_run:
            with get_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('reply_scan',?)",(json.dumps(result),))
        return result if detailed else matches
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError("IMAP check failed. Check account settings and connectivity; progress is retained.") from exc
    finally:
        if mailbox:
            try: mailbox.logout()
            except Exception: pass
