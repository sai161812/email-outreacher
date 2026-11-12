"""Small local foreground supervisor: python run.py start|status|stop [--port 5000]."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parent

def state_path(database):
    key=hashlib.sha256(str(Path(database).resolve()).encode()).hexdigest()[:16]
    return ROOT/'.runtime'/f'{key}.json'

def control(path,action):
    if not path.is_file(): return {'status':'not_running'}
    state=json.loads(path.read_text(encoding='utf8'))
    try:
        with socket.create_connection(('127.0.0.1',state['control_port']),timeout=3) as sock:
            sock.settimeout(3)
            sock.sendall((json.dumps({'token':state['token'],'action':action})+'\n').encode())
            response=sock.makefile('rb').readline(4096)
        return json.loads(response)
    except (OSError,ValueError): return {'status':'not_running','note':'No authenticated supervisor response; no process was killed.'}

def start(database,port):
    from filelock import FileLock,Timeout
    import config
    Path(database).parent.mkdir(parents=True,exist_ok=True)
    state=state_path(database);state.parent.mkdir(parents=True,exist_ok=True)
    lock=FileLock(str(database)+'.launcher.lock',timeout=0)
    try: lock.acquire()
    except Timeout: raise ValueError('A launcher already owns this database; use status or stop')
    children=[];logs=[];stopped=threading.Event();listener=None;ready=None
    try:
        try:
            with FileLock(str(database)+'.worker.lock',timeout=0): pass
        except Timeout: raise ValueError('Another worker owns this database; stop it before using the launcher')
        with socket.socket() as probe:
            try: probe.bind(('127.0.0.1',port))
            except OSError: raise ValueError(f'Port {port} is already in use; choose --port or stop its existing server')
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2);listener.settimeout(.2)
        token=secrets.token_urlsafe(32);run_id=uuid.uuid4().hex
        ready=state.parent/(run_id+'.ready')
        folder=state.parent/'logs';folder.mkdir(exist_ok=True)
        env=dict(os.environ,OUTREACH_DB_PATH=str(database),RESUME_DIR=str(config.RESUME_DIR),CONTEXT_PATH=str(config.CONTEXT_PATH),PYTHONUNBUFFERED='1',OUTREACH_MANAGED_CHILD='1')
        def launch(name,args):
            file=(folder/f'{run_id}-{name}.log').open('ab');logs.append(file)
            child=subprocess.Popen([sys.executable,*args],cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=file,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            children.append(child);child.stdin.write(b'1');child.stdin.flush();return child
        server=launch('server',['serve.py','--port',str(port),'--ready',str(ready),'--instance',run_id])
        deadline=time.monotonic()+15
        while not ready.exists():
            if server.poll() is not None: raise ValueError(f'Server failed to start; inspect {folder}')
            if time.monotonic()>deadline: raise ValueError(f'Server startup timed out; inspect {folder}')
            time.sleep(.05)
        # File creation may become visible before its short JSON write finishes.
        for _ in range(20):
            try: actual=json.loads(ready.read_text(encoding='utf8'));break
            except ValueError: time.sleep(.05)
        else: raise ValueError('Unreadable server readiness record')
        if actual['instance']!=run_id: raise ValueError('Server readiness did not match this launcher instance')
        worker=launch('worker',['worker.py'])
        state.write_text(json.dumps({'token':token,'control_port':listener.getsockname()[1],'port':port}),encoding='utf8')
        def listen():
            while not stopped.is_set():
                try: client,_=listener.accept()
                except socket.timeout: continue
                except OSError: return
                with client:
                    client.settimeout(1)
                    try:
                        request=json.loads(client.makefile('rb').readline(4096))
                        if not secrets.compare_digest(str(request.get('token','')),token): continue
                        action=request.get('action')
                        if action not in {'status','stop'}: continue
                        client.sendall((json.dumps({'status':'stopping' if action=='stop' else 'running','port':port,'server_pid':server.pid,'worker_pid':worker.pid})+'\n').encode())
                        if action=='stop': stopped.set()
                    except (OSError,ValueError): pass
        thread=threading.Thread(target=listen,daemon=True);thread.start()
        print(f'Running http://127.0.0.1:{port}; logs: {folder}. Ctrl+C or run.py stop to stop.',flush=True)
        while not stopped.wait(.2):
            if any(p.poll() is not None for p in children): raise ValueError(f'A child process stopped; inspect {folder}')
    finally:
        stopped.set()
        if listener: listener.close()
        # Owned Popen handles only: never terminate a PID read from disk.
        for child in reversed(children):
            child.stdin.close()
            if child.poll() is None:
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    try: child.wait(timeout=5)
                    except subprocess.TimeoutExpired: child.kill();child.wait(timeout=5)
        for file in logs: file.close()
        if ready: ready.unlink(missing_ok=True)
        state.unlink(missing_ok=True)
        lock.release()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('start','stop','status'))
    parser.add_argument('--port',type=int,default=5000)
    args=parser.parse_args()
    if sys.version_info[:2]!=(3,12): parser.exit(1,'Python 3.12 is required. Recreate .venv from requirements.lock.\n')
    if not 1<=args.port<=65535: parser.error('Port must be 1-65535')
    try:
        import config
        if args.action=='start': start(config.DB_PATH,args.port)
        else: print(json.dumps(control(state_path(config.DB_PATH),args.action)))
    except KeyboardInterrupt: print('Stopped. Review uncertain delivery attempts after an interrupted send.')
    except ImportError: parser.exit(1,'Missing dependencies: install requirements.lock into .venv first.\n')
    except (OSError,ValueError,RuntimeError) as exc: parser.exit(1,str(exc)+'\n')

if __name__=='__main__': main()
