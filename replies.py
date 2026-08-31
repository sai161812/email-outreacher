"""
Checks your Gmail INBOX via IMAP for replies to sent outreach emails.
Matches via In-Reply-To / References headers (Message-ID), or falls back to
the sender's From address for legacy emails without a Message-ID.
"""
import imaplib
import re

import config
from db import get_connection
import tracker


def _clean_header_str(val):
    if not val:
        return ""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="ignore")
    return str(val)


def check_replies(dry_run: bool = False):
    """
    Connects to IMAP inbox and checks for replies to emails currently in 'sent' status.
    Returns a list of dicts describing matched replies.
    """
    try:
        config.require_gmail_creds()
        imap = imaplib.IMAP4_SSL(config.IMAP_HOST)
        imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        imap.select("INBOX")
    except Exception as e:
        print(f"Error connecting to IMAP ({config.IMAP_HOST}): {e}")
        print(
            "Please verify that:\n"
            "1. IMAP access is enabled in Gmail (Settings -> Forwarding and POP/IMAP -> Enable IMAP).\n"
            "2. GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env are valid App Passwords."
        )
        return []

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT e.id, e.message_id, e.subject, e.sent_at, e.contact_id, 
                       c.email as contact_email, c.name as contact_name
                FROM emails e
                JOIN contacts c ON e.contact_id = c.id
                WHERE e.status = 'sent'
                ORDER BY e.id ASC
                """
            ).fetchall()
            candidates = [dict(r) for r in rows]

        if not candidates:
            return []

        # Count sent emails per contact address to ensure fallback only applies to unique contacts
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

                # Also search FROM contact email and inspect headers for References / In-Reply-To
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
                # Candidate has NO message_id -> fallback to FROM address matching
                # Only if exactly one 'sent'-status email exists for this contact
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
                    "contact_name": c.get("contact_name"),
                    "subject": c.get("subject"),
                    "match_type": match_type,
                    "matched_by": match_type,
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
