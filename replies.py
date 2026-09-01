import imaplib
import re

import config
from repository import EmailRepository
import tracker

def _clean_header_str(val):
    if not val:
        return ""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="ignore")
    return str(val)

def check_replies(dry_run=False):
    try:
        config.require_gmail_creds()
        imap = imaplib.IMAP4_SSL(config.IMAP_HOST)
        imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        imap.select("INBOX")
    except Exception as e:
        raise ValueError(f"IMAP Error: {e}")

    try:
        candidates = EmailRepository.get_sent_candidates_for_replies()
        candidates = [dict(c) for c in candidates]
        if not candidates:
            return []

        contact_counts = {}
        for c in candidates:
            c_email = (c["contact_email"] or "").strip().lower()
            contact_counts[c_email] = contact_counts.get(c_email, 0) + 1

        matches = []
        already_matched_ids = set()

        for c in candidates:
            if c["id"] in already_matched_ids:
                continue

            c_email = (c["contact_email"] or "").strip().lower()
            msg_id = (c.get("message_id") or "").strip()
            matched = False
            match_type = None

            if msg_id:
                clean_id = msg_id.strip("<> ")
                search_queries = [
                    f'HEADER References "{clean_id}"',
                    f'HEADER In-Reply-To "{clean_id}"',
                    f'HEADER References "{msg_id}"',
                    f'HEADER In-Reply-To "{msg_id}"',
                ]
                found_msg_nums = set()
                for query in search_queries:
                    try:
                        typ, data = imap.search(None, query)
                        if typ == "OK" and data and data[0]:
                            for num in data[0].split():
                                found_msg_nums.add(num)
                    except Exception:
                        pass

                if not found_msg_nums and c_email:
                    try:
                        typ, data = imap.search(None, f'FROM "{c_email}"')
                        if typ == "OK" and data and data[0]:
                            for num in data[0].split():
                                typ, fetch_data = imap.fetch(num, '(BODY.PEEK[HEADER.FIELDS (IN-REPLY-TO REFERENCES)])')
                                if typ == "OK" and fetch_data and isinstance(fetch_data[0], tuple):
                                    hdr_text = _clean_header_str(fetch_data[0][1])
                                    if clean_id in hdr_text or msg_id in hdr_text:
                                        found_msg_nums.add(num)
                                        break
                    except Exception:
                        pass

                if found_msg_nums:
                    matched = True
                    match_type = "message_id"

            else:
                if contact_counts.get(c_email, 0) == 1 and c_email:
                    try:
                        typ, data = imap.search(None, f'FROM "{c_email}"')
                        if typ == "OK" and data and data[0] and data[0].split():
                            matched = True
                            match_type = "address_fallback"
                    except Exception:
                        pass

            if matched:
                already_matched_ids.add(c["id"])
                match_info = {
                    "email_id": c["id"],
                    "contact_email": c["contact_email"],
                    "match_type": match_type,
                }
                if not dry_run:
                    tracker.mark_replied(c["id"])
                matches.append(match_info)

        return matches

    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass
