"""Run one durable worker per database: python worker.py [--once]."""
import argparse
import logging
import time
from filelock import FileLock,Timeout
import config
import db
import jobs

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--once",action="store_true",help="Process at most one pending job and exit")
    args=parser.parse_args()
    db.init_db()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    lock=FileLock(str(config.DB_PATH)+".worker.lock",timeout=0)
    try:
        with lock:
            jobs.recover()
            while True:
                processed=jobs.process_next()
                if args.once: return
                if not processed: time.sleep(1)
    except Timeout:
        raise SystemExit("Another worker already owns this database")

if __name__=="__main__":
    main()
