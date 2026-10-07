"""Install a committed source ZIP in isolation and probe Waitress, schema and worker."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

def smoke(archive):
    with tempfile.TemporaryDirectory(prefix="outreach-release-") as temporary:
        base=Path(temporary)
        with zipfile.ZipFile(archive) as package:
            for info in package.infolist():
                if Path(info.filename).is_absolute() or ".." in Path(info.filename).parts:
                    raise ValueError("Unsafe archive path")
            package.extractall(base)
        project=base/"email-outreacher"
        environment=base/"runtime"
        subprocess.run([sys.executable,"-m","venv",str(environment)],check=True)
        python=environment/("Scripts/python.exe" if os.name=="nt" else "bin/python")
        subprocess.run([str(python),"-m","pip","install","--quiet","--upgrade","pip==26.2.1"],check=True)
        subprocess.run([str(python),"-m","pip","install","--quiet","--require-hashes","-r",str(project/"requirements.lock")],check=True)
        subprocess.run([str(python),"-m","pip","check"],check=True)
        env=dict(os.environ)
        for line in (project/".env.example").read_text(encoding="utf8").splitlines():
            if line and not line.startswith("#") and "=" in line: env.pop(line.split("=",1)[0],None)
        env.pop("PYTHONPATH",None)
        env.update(OUTREACH_DB_PATH=str(base/"smoke.db"),CONTEXT_PATH=str(base/"facts.txt"),RESUME_DIR=str(base/"resumes"),
                   GEMINI_API_KEY="",GMAIL_ADDRESS="",GMAIL_APP_PASSWORD="",OWNER_PASSWORD="",SECRET_KEY="",ALLOWED_HOSTS="localhost,127.0.0.1,::1",COOKIE_SECURE="0")
        def run(*args):
            subprocess.run([str(python),*args],cwd=project,env=env,check=True,timeout=60)
        run("manage.py","init")
        run("manage.py","check")
        run("worker.py","--once")
        run("manage.py","backup","--output",str(base/"snapshot.sqlite"))
        probe=r'''
import json,threading,urllib.request
from waitress import create_server
from app import app
server=create_server(app,host="127.0.0.1",port=0)
thread=threading.Thread(target=server.run,daemon=True);thread.start()
try:
    root="http://127.0.0.1:"+str(server.effective_port)
    for route in ["/","/api/session","/api/stats","/api/settings","/api/jobs"]:
        with urllib.request.urlopen(root+route,timeout=10) as response:
            assert response.status==200,route
    print("Clean runtime: Waitress read routes, schema, worker and backup passed")
finally:
    server.task_dispatcher.shutdown()
    server.close()
    thread.join(timeout=5)
'''
        run("-c",probe)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    args=parser.parse_args()
    smoke(args.archive.resolve())
