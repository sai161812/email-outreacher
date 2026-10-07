"""Cumulative per-message funnel, grouped by resume ID and local send day."""
from datetime import datetime,timezone
import config
import followups
from errors import Conflict,NotFound
from repository import EmailRepository,ResumeRepository,rows

def _set_status(eid,status):
    return EmailRepository.update_status(eid,status)

def mark_replied(eid):
    original=EmailRepository.get_by_id(eid)
    if not original:
        raise NotFound("Email not found")
    root=original["thread_root_id"] or original["id"]
    for item in rows("SELECT * FROM emails WHERE id=? OR thread_root_id=?",(root,root)):
        if item["sent_at"] and item["status"] in {"sent","ghosted"}:
            try:
                _set_status(item["id"],"replied")
            except Conflict:
                pass  # A concurrent interview/offer must not be downgraded.

def mark_ghosted(eid): return _set_status(eid,"ghosted")
def mark_bounced(eid): return _set_status(eid,"bounced")
def mark_interview_scheduled(eid): return _set_status(eid,"interview_scheduled")
def mark_interview_completed(eid): return _set_status(eid,"interview_completed")
def mark_offer(eid): return _set_status(eid,"offer")
def mark_no_offer(eid): return _set_status(eid,"no_offer")
def due_for_follow_up(): return followups.due()

def pipeline_summary():
    result={r["status"]:r["n"] for r in rows("SELECT status,COUNT(*) n FROM emails GROUP BY status")}
    sent=rows("SELECT * FROM emails WHERE sent_at IS NOT NULL")
    result["sent"]=len(sent)
    result["replied"]=sum(e["status"] in {"replied","interview_scheduled","interview_completed","offer","no_offer"} for e in sent)
    return result

def stats():
    variants={r["id"]:r["name"] for r in ResumeRepository.get_all()}
    metrics={}
    weekdays={d:{"sent":0,"replied":0,"interviews":0,"offers":0} for d in ("Mon","Tue","Wed","Thu","Fri","Sat","Sun")}
    for row in rows("SELECT * FROM emails WHERE sent_at IS NOT NULL"):
        key=row["resume_variant_id"]
        entry=metrics.setdefault(key,{"sent":0,"replied":0,"interviews":0,"offers":0})
        parsed=datetime.fromisoformat(row["sent_at"].replace("Z","+00:00"))
        if not parsed.tzinfo: parsed=parsed.replace(tzinfo=timezone.utc)
        day=parsed.astimezone(config.TIMEZONE).strftime("%a")
        flags={"sent":1,"replied":int(row["status"] in {"replied","interview_scheduled","interview_completed","offer","no_offer"}),
               "interviews":int(row["status"] in {"interview_scheduled","interview_completed","offer","no_offer"}),"offers":int(row["status"]=="offer")}
        for name,value in flags.items():
            entry[name]+=value
            weekdays[day][name]+=value
    def rates(entry):
        return {**entry,**{name+"_rate":round(entry[field]/entry["sent"]*100,1) if entry["sent"] else 0
                          for name,field in (("reply","replied"),("interview","interviews"),("offer","offers"))}}
    return {"denominator":"sent messages (including follow-ups)",
            "by_variant":[{"id":key,"name":variants.get(key,"Unassigned"),"variant":variants.get(key,"Unassigned"),**rates(value)} for key,value in metrics.items()],
            "by_weekday":[{"day":day,"weekday":day,**rates(value)} for day,value in weekdays.items()]}
