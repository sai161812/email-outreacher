"""Local database operations; never sends mail or calls AI."""
import argparse
import json
import sqlite3
import config
import db

def check_database():
    if not config.DB_PATH.is_file():
        raise ValueError("Database does not exist; run python manage.py init")
    with db.get_connection() as conn:
        integrity=[r[0] for r in conn.execute("PRAGMA integrity_check")]
        foreign_keys=len(conn.execute("PRAGMA foreign_key_check").fetchall())
        version=conn.execute("PRAGMA user_version").fetchone()[0]
        reports=[dict(r) for r in conn.execute("SELECT * FROM migration_reports WHERE count>0")]
    result={"integrity":integrity,"foreign_key_violations":foreign_keys,"schema_version":version,"migration_reports":reports}
    if integrity!=["ok"] or foreign_keys or version!=db.SCHEMA_VERSION:
        raise ValueError("Database check failed; inspect a protected backup before continuing")
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest="command",required=True)
    commands.add_parser("init",help="Initialize or upgrade, backing up an existing database first")
    commands.add_parser("check",help="Check integrity and report legacy issues without exposing records")
    commands.add_parser("diagnose",help="Report runtime, paths and configuration presence without network calls")
    backup=commands.add_parser("backup",help="Create an SQLite-consistent backup, including committed WAL data")
    backup.add_argument("--output",help="New backup filename; an existing file is never overwritten")
    backup.add_argument("--bundle",help="New directory containing database, resume assets and manifest")
    restore=commands.add_parser("restore",help="Restore a bundle into NEW database and resume paths")
    restore.add_argument("--bundle",required=True)
    restore.add_argument("--output",required=True)
    restore.add_argument("--resume-output",required=True)
    args=parser.parse_args()
    try:
        if args.command=="init":
            db.init_db()
            print(json.dumps(check_database()))
        elif args.command=="check":
            print(json.dumps(check_database()))
        elif args.command=="diagnose":
            from operations import diagnostics
            print(json.dumps(diagnostics(),indent=2))
        elif args.command=="restore":
            from operations import restore_bundle
            print(restore_bundle(args.bundle,args.output,args.resume_output))
        elif args.bundle:
            if args.output: raise ValueError("Choose --output or --bundle")
            from operations import backup_bundle
            print(backup_bundle(args.bundle))
        else:
            print(db.backup_database(args.output))
    except (ValueError,RuntimeError,OSError,sqlite3.Error) as exc:
        parser.exit(1,str(exc)+"\n")

if __name__=="__main__":
    main()
