"""Loopback Waitress entry point used by run.py; no worker or sending here."""
import argparse
import json
import os
from pathlib import Path
from parent_watch import watch_parent
watch_parent()
from waitress import create_server
from app import app

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--ready',type=Path,required=True)
    parser.add_argument('--instance',required=True)
    args=parser.parse_args()
    server=create_server(app,host='127.0.0.1',port=args.port)
    try:
        with args.ready.open('x',encoding='utf8') as file:
            json.dump({'pid':os.getpid(),'port':server.effective_port,'instance':args.instance},file)
        server.run()
    finally:
        server.task_dispatcher.shutdown();server.close()

if __name__=='__main__': main()
