"""Managed children stop when their supervisor's private stdin pipe closes."""
import os
import sys
import threading

def watch_parent():
    if os.environ.get('OUTREACH_MANAGED_CHILD')!='1': return
    if sys.stdin.buffer.read(1)!=b'1': raise SystemExit('Supervisor handshake missing')
    def watch():
        sys.stdin.buffer.read()
        # Abrupt submission interruption intentionally leaves durable recovery
        # to worker.recover rather than attempting another SMTP submission.
        os._exit(1)
    threading.Thread(target=watch,daemon=True).start()
