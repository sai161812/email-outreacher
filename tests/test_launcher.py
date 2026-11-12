import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import pytest
import run

ROOT=Path(__file__).parents[1]

def environment(tmp_path):
    env=dict(os.environ)
    for line in (ROOT/'.env.example').read_text(encoding='utf8').splitlines():
        if line and not line.startswith('#') and '=' in line:
            key,value=line.split('=',1);env[key]=value
    env.update(OUTREACH_DB_PATH=str(tmp_path/'test.db'),RESUME_DIR=str(tmp_path/'resumes'),CONTEXT_PATH=str(tmp_path/'facts.txt'))
    env.pop('OUTREACH_MANAGED_CHILD',None)
    return env

@pytest.mark.browser
def test_launcher_start_status_stop_and_duplicate_guard(tmp_path):
    env=environment(tmp_path)
    with socket.socket() as probe: probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    state=run.state_path(env['OUTREACH_DB_PATH'])
    with (tmp_path/'launcher.log').open('w') as log:
        process=subprocess.Popen([sys.executable,'run.py','start','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                if state.exists() and run.control(state,'status').get('status')=='running': break
                if process.poll() is not None: pytest.fail((tmp_path/'launcher.log').read_text())
                time.sleep(.1)
            else: pytest.fail('Launcher did not become ready')
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/session',timeout=5) as response:
                assert response.status==200
            duplicate=subprocess.run([sys.executable,'run.py','start','--port',str(port)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
            assert duplicate.returncode!=0 and 'already owns' in duplicate.stderr
            assert run.control(state,'stop')['status']=='stopping'
            assert process.wait(timeout=15)==0
            assert run.control(state,'status')['status']=='not_running'
            with socket.socket() as probe: probe.bind(('127.0.0.1',port))
        finally:
            run.control(state,'stop')
            if process.poll() is None:
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired: process.terminate();process.wait(timeout=5)

def test_port_conflict_is_actionable_and_never_starts_worker(tmp_path):
    env=environment(tmp_path)
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',0));occupied.listen(1)
        result=subprocess.run([sys.executable,'run.py','start','--port',str(occupied.getsockname()[1])],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode!=0 and 'already in use' in result.stderr
    assert not Path(env['OUTREACH_DB_PATH']).exists()

def test_invalid_runtime_does_not_try_starting(monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['run.py','start'])
    monkeypatch.setattr(sys,'version_info',(3,11,0))
    with pytest.raises(SystemExit): run.main()
    assert 'Python 3.12 is required' in capsys.readouterr().err

def test_managed_child_exits_when_parent_pipe_closes(monkeypatch):
    import io
    from types import SimpleNamespace
    from threading import Event
    import parent_watch
    exited=Event()
    monkeypatch.setenv('OUTREACH_MANAGED_CHILD','1')
    monkeypatch.setattr(sys,'stdin',SimpleNamespace(buffer=io.BytesIO(b'1')))
    monkeypatch.setattr(parent_watch.os,'_exit',lambda code:exited.set())
    parent_watch.watch_parent()
    assert exited.wait(2)
