"""Local diagnostics and portable database/resume backup bundles."""
import hashlib
import json
import platform
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
import config
import db


def diagnostics():
    result={"python":platform.python_version(),"executable":sys.executable,
        "supported_runtime":sys.version_info[:2]==(3,12),
        "paths":{k:str(v) for k,v in {"database":config.DB_PATH,"resumes":config.RESUME_DIR,"facts":config.CONTEXT_PATH}.items()},
        "configuration":{"gemini_configured":bool(config.GEMINI_API_KEY),
            "gmail_configured":bool(config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD),
            "connections_verified":False},"schema":None,"worker":{"state":"not_seen"}}
    if config.DB_PATH.is_file():
        with closing(sqlite3.connect(config.DB_PATH.resolve().as_uri()+"?mode=ro",uri=True)) as conn:
            result["schema"]=conn.execute("PRAGMA user_version").fetchone()[0]
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='settings'").fetchone():
                row=conn.execute("SELECT value FROM settings WHERE key='worker_heartbeat'").fetchone()
                if row:
                    from followups import parsed_time
                    age=max(0,(config.now()-parsed_time(row[0])).total_seconds())
                    result["worker"]={"state":"recent" if age<30 else "stale_or_busy","last_seen":row[0]}
    return result


def backup_bundle(destination):
    target=Path(destination).resolve()
    if target.exists(): raise ValueError("Bundle destination must be new")
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent,prefix=".bundle-") as temporary:
        stage=Path(temporary)/"bundle"
        stage.mkdir()
        db.backup_database(stage/"database.sqlite")
        manifest={"version":1,"assets":[]}
        with closing(sqlite3.connect(stage/"database.sqlite")) as conn:
            for rid,original in conn.execute("SELECT id,file_path FROM resume_variants"):
                if not original: continue
                source=Path(original)
                if not source.is_absolute(): source=config.BASE_DIR/source
                source=source.resolve()
                if not source.is_relative_to(config.RESUME_DIR.resolve()):
                    raise ValueError("Referenced resume is outside RESUME_DIR")
                with source.open("rb") as file: data=file.read(config.MAX_RESUME_BYTES+1)
                if len(data)>config.MAX_RESUME_BYTES: raise ValueError("Referenced resume exceeds size limit")
                name=f"resume-{rid}.pdf"
                (stage/name).write_bytes(data)
                manifest["assets"].append({"id":rid,"file":name,"sha256":hashlib.sha256(data).hexdigest()})
        manifest["database_sha256"]=hashlib.sha256((stage/"database.sqlite").read_bytes()).hexdigest()
        (stage/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf8")
        stage.rename(target)
    return target


def restore_bundle(bundle,output,resume_output):
    source=Path(bundle).resolve(); target=Path(output).resolve(); assets=Path(resume_output).resolve()
    if target.exists() or assets.exists(): raise ValueError("Restore destinations must be new")
    if target==assets or target.is_relative_to(assets) or assets.is_relative_to(target):
        raise ValueError("Choose separate database and resume destinations")
    manifest=json.loads((source/"manifest.json").read_text(encoding="utf8"))
    if manifest.get("version")!=1: raise ValueError("Unsupported bundle")
    database=(source/"database.sqlite").read_bytes()
    if hashlib.sha256(database).hexdigest()!=manifest["database_sha256"]: raise ValueError("Database checksum mismatch")
    checked=[]
    seen=set()
    for item in manifest["assets"]:
        name=item["file"]
        rid=item['id']
        if type(rid) is not int or rid<1 or rid in seen or name!=f"resume-{rid}.pdf":
            raise ValueError("Invalid asset filename or duplicate identity")
        seen.add(rid)
        with (source/name).open('rb') as file: data=file.read(config.MAX_RESUME_BYTES+1)
        if len(data)>config.MAX_RESUME_BYTES: raise ValueError("Resume exceeds size limit")
        if hashlib.sha256(data).hexdigest()!=item["sha256"]: raise ValueError("Resume checksum mismatch")
        checked.append((item["id"],name,data))
    target.parent.mkdir(parents=True,exist_ok=True)
    assets.mkdir(parents=True,exist_ok=False)
    # Exclusive creation never overwrites an existing database.
    with target.open("xb") as file: file.write(database)
    with closing(sqlite3.connect(target)) as conn, conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0]!="ok": raise ValueError("Restored database failed integrity check")
        for rid,name,data in checked:
            (assets/name).write_bytes(data)
            conn.execute("UPDATE resume_variants SET file_path=? WHERE id=?",(str(assets/name),rid))
        # Absolute asset paths changed: old approvals cannot authorize delivery.
        columns={r[1] for r in conn.execute("PRAGMA table_info(emails)")}
        if "approval_json" in columns:
            conn.execute("UPDATE emails SET status='pending_review',approval_json=NULL,revision=revision+1 WHERE status='approved' AND sent_at IS NULL")
    return target
