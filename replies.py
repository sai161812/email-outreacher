"""Incremental, read-only IMAP scanning with exact thread matching."""
import email
import imaplib
import json
import re
from datetime import timezone
from email.utils import getaddresses,parsedate_to_datetime
import config
import tracker
from errors import ProviderError
from db import get_connection
from repository import EmailRepository,rows,timestamp
from followups import parsed_time

def classify(message):
    if message.get_content_type()=="multipart/report":
        for part in message.walk():
            if part.get_content_type()=="message/delivery-status":
                for block in part.get_payload():
                    if block.get("Action","").lower()=="failed" and block.get("Status","").startswith("5."):
                        return "bounced"
        return "automatic"
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
    return [c for c in candidates if c.get("message_id") in ids and c["sent_at"] and received>=parsed_time(c["sent_at"])
            and (kind=="bounced" or c["contact_email"].strip().lower() in senders)]

def _ok(result,operation):
    status,data=result
    if status!="OK":
        raise ProviderError(f"IMAP {operation} failed")
    return data

def check_replies(dry_run=False):
    config.require_gmail_creds()
    candidates=EmailRepository.get_sent_candidates_for_replies()
    if not candidates:
        return []
    mailbox=None
    matches=[]
    try:
        mailbox=imaplib.IMAP4_SSL(config.IMAP_HOST,timeout=config.PROVIDER_TIMEOUT)
        _ok(mailbox.login(config.GMAIL_ADDRESS,config.GMAIL_APP_PASSWORD),"login")
        _ok(mailbox.select("INBOX",readonly=True),"select")
        validity_data=mailbox.response("UIDVALIDITY")[1]
        validity=(validity_data[0] if validity_data else b"unknown").decode()
        if validity=="unknown":
            raise ProviderError("IMAP UIDVALIDITY is unavailable")
        scope=f"{config.GMAIL_ADDRESS.lower()}:INBOX:{validity}"
        previous=rows("SELECT value FROM settings WHERE key=?",("imap_cursor:"+scope,))
        last=int(previous[0]["value"]) if previous else 0
        found=_ok(mailbox.uid("search",None,"UID",f"{last+1}:*"),"search")
        uids=[int(v) for v in (found[0] or b"").split() if int(v)>last]
        for uid in sorted(uids)[:500]:
            processed=rows("SELECT 1 FROM reply_messages WHERE uidvalidity=? AND uid=?",(scope,str(uid)))
            if processed: continue
            fetched=_ok(mailbox.uid("fetch",str(uid),"(BODY.PEEK[HEADER] RFC822.SIZE)"),"fetch")
            chunks=[v for v in fetched if isinstance(v,tuple)]
            if not chunks:
                raise ProviderError("IMAP returned an unreadable message header")
            metadata,raw=chunks[0]
            message=email.message_from_bytes(raw)
            if message.get_content_type()=="multipart/report":
                sizes=re.findall(rb"RFC822.SIZE (\d+)",metadata)
                if not sizes or int(sizes[0])>config.MAX_UPLOAD_BYTES:
                    raise ProviderError("Delivery report exceeds scan size limit")
                complete=_ok(mailbox.uid("fetch",str(uid),"(BODY.PEEK[])"),"fetch delivery report")
                raw=next((v[1] for v in complete if isinstance(v,tuple)),b"")
                message=email.message_from_bytes(raw)
            matched=matched_candidates(message,candidates)
            for candidate in matched:
                kind=classify(message)
                matches.append({"email_id":candidate["id"],"contact_email":candidate["contact_email"],"match_type":"exact_thread","kind":kind})
                if not dry_run:
                    if kind=="bounced": tracker.mark_bounced(candidate["id"])
                    else: tracker.mark_replied(candidate["id"])
            if not dry_run:
                with get_connection() as conn:
                    conn.execute("INSERT OR IGNORE INTO reply_messages VALUES (?,?,?,?)",(scope,str(uid),message.get("Message-ID"),timestamp()))
                    conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",("imap_cursor:"+scope,str(uid)))
        return matches
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError("IMAP check failed. Check account settings and connectivity; progress is retained.") from exc
    finally:
        if mailbox:
            try: mailbox.logout()
            except Exception: pass
