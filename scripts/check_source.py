"""Fail on private tracked artifacts, obvious credential formats or syntax errors."""
import ast
import re
import subprocess
from release import ROOT,prohibited

files=subprocess.check_output(["git","ls-files","-z"],cwd=ROOT).decode().split("\0")
failures=[]
patterns=[
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
for name in filter(None,files):
    path=ROOT/name
    if prohibited(name):
        failures.append("Private/generated tracked path: "+name)
        continue
    if not path.is_file(): continue
    text=path.read_text(encoding="utf8")
    if name.endswith(".py"): ast.parse(text,filename=name)
    if any(pattern.search(text) for pattern in patterns): failures.append("Credential-shaped content: "+name)
ignored=[".env.production","outreach.db-wal",".venv/example","candidate_context.txt","resumes/cv.pdf"]
for name in ignored:
    if subprocess.run(["git","check-ignore","-q",name],cwd=ROOT).returncode!=0:
        failures.append("Missing ignore rule: "+name)
if subprocess.run(["git","check-ignore","-q","tests/new_regression.py"],cwd=ROOT).returncode==0:
    failures.append("Regression tests must not be ignored")
subprocess.run(["node","--check","static/app.js"],cwd=ROOT,check=True)
if failures: raise SystemExit("\n".join(failures))
print("Tracked-source syntax, private-file and credential-format checks passed")
