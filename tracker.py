"""
You said you'll read replies yourself — this module just gives you a
place to record what happened, and surfaces what's due for follow-up.
"""
from datetime import datetime, timedelta, date, timezone
import config
from db import get_connection
import suppression


def mark_replied(email_id):
    _set_status(email_id, "replied")


def mark_ghosted(email_id):
    _set_status(email_id, "ghosted")


def mark_bounced(email_id):
    _set_status(email_id, "bounced")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT c.email FROM emails e JOIN contacts c ON e.contact_id = c.id WHERE e.id = ?",
            (email_id,)
        ).fetchone()
        if row and row["email"]:
            suppression.add(row["email"], "bounced")


def mark_interview_scheduled(email_id):
    _set_status(email_id, "interview_scheduled")


def mark_interview_completed(email_id):
    _set_status(email_id, "interview_completed")


def mark_offer(email_id):
    _set_status(email_id, "offer")


def mark_no_offer(email_id):
    _set_status(email_id, "no_offer")


def _set_status(email_id, status):
    with get_connection() as conn:
        conn.execute(
            "UPDATE emails SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(timezone.utc).isoformat(), email_id),
        )


def due_for_follow_up():
    """
    Sent emails with no reply after FOLLOW_UP_AFTER_DAYS, excluding ones
    that already have a follow-up drafted or sent (so you don't get
    prompted to follow up on the same email twice).
    """
    cutoff = (date.today() - timedelta(days=config.FOLLOW_UP_AFTER_DAYS)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.*, c.name as company_name, ct.email as contact_email "
            "FROM emails e "
            "JOIN companies c ON e.company_id = c.id "
            "JOIN contacts ct ON e.contact_id = ct.id "
            "WHERE e.status = 'sent' AND date(e.sent_at) <= ? "
            "AND e.id NOT IN (SELECT follow_up_to_email_id FROM emails "
            "WHERE follow_up_to_email_id IS NOT NULL)",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def pipeline_summary():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as n FROM emails GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}


def stats():
    with get_connection() as conn:
        variant_rows = conn.execute("SELECT id, name FROM resume_variants ORDER BY id").fetchall()
        emails = conn.execute(
            """
            SELECT e.id, e.status, e.sent_at, e.resume_variant_id, rv.name as variant_name
            FROM emails e
            LEFT JOIN resume_variants rv ON e.resume_variant_id = rv.id
            WHERE e.status IN ('sent','replied','ghosted','bounced','interview_scheduled','interview_completed','offer','no_offer')
               OR (e.sent_at IS NOT NULL AND e.status NOT IN ('pending_review', 'approved', 'rejected'))
            """
        ).fetchall()

    SENT_STATUSES = {'sent', 'replied', 'ghosted', 'bounced', 'interview_scheduled', 'interview_completed', 'offer', 'no_offer'}
    REPLY_STATUSES = {'replied', 'interview_scheduled', 'interview_completed', 'offer', 'no_offer'}
    INTERVIEW_STATUSES = {'interview_scheduled', 'interview_completed', 'offer', 'no_offer'}
    OFFER_STATUSES = {'offer'}

    variant_stats = {}
    for r in variant_rows:
        variant_stats[r["name"]] = {"sent": 0, "replied": 0, "interviews": 0, "offers": 0}
    variant_stats["unassigned"] = {"sent": 0, "replied": 0, "interviews": 0, "offers": 0}

    WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_stats = {day: {"sent": 0, "replied": 0, "interviews": 0, "offers": 0} for day in WEEKDAYS}

    for row in emails:
        v_name = row["variant_name"] or "unassigned"
        if v_name not in variant_stats:
            variant_stats[v_name] = {"sent": 0, "replied": 0, "interviews": 0, "offers": 0}

        status = row["status"]
        is_sent = status in SENT_STATUSES or row["sent_at"] is not None
        if not is_sent:
            continue

        variant_stats[v_name]["sent"] += 1
        if status in REPLY_STATUSES:
            variant_stats[v_name]["replied"] += 1
        if status in INTERVIEW_STATUSES:
            variant_stats[v_name]["interviews"] += 1
        if status in OFFER_STATUSES:
            variant_stats[v_name]["offers"] += 1

        if row["sent_at"]:
            try:
                clean_dt = str(row["sent_at"]).replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_dt)
                day_name = dt.strftime("%a")
                if day_name in weekday_stats:
                    weekday_stats[day_name]["sent"] += 1
                    if status in REPLY_STATUSES:
                        weekday_stats[day_name]["replied"] += 1
                    if status in INTERVIEW_STATUSES:
                        weekday_stats[day_name]["interviews"] += 1
                    if status in OFFER_STATUSES:
                        weekday_stats[day_name]["offers"] += 1
            except Exception:
                pass

    def _calc_entry(key_name, key_val, counts):
        s = counts["sent"]
        r = counts["replied"]
        i = counts["interviews"]
        o = counts["offers"]
        return {
            key_name: key_val,
            "sent": s,
            "replied": r,
            "interviews": i,
            "offers": o,
            "reply_rate": round((r / s) * 100, 1) if s > 0 else 0.0,
            "interview_rate": round((i / s) * 100, 1) if s > 0 else 0.0,
            "offer_rate": round((o / s) * 100, 1) if s > 0 else 0.0,
        }

    by_variant = [_calc_entry("name", name, counts) for name, counts in variant_stats.items()]
    for entry in by_variant:
        entry["variant"] = entry["name"]

    by_weekday = [_calc_entry("weekday", day, weekday_stats[day]) for day in WEEKDAYS]
    for entry in by_weekday:
        entry["day"] = entry["weekday"]

    return {
        "by_variant": by_variant,
        "by_weekday": by_weekday,
    }