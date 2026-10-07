"""Local database operations; never sends mail or calls AI."""
import argparse
import json
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
    backup=commands.add_parser("backup",help="Create an SQLite-consistent backup, including committed WAL data")
    backup.add_argument("--output",help="New backup filename; an existing file is never overwritten")
    args=parser.parse_args()
    try:
        if args.command=="init":
            db.init_db()
            print(json.dumps(check_database()))
        elif args.command=="check":
            print(json.dumps(check_database()))
        else:
            print(db.backup_database(args.output))
    except (ValueError,RuntimeError) as exc:
        parser.exit(1,str(exc)+"\n")

if __name__=="__main__":
    main()
