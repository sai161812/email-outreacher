"""Create a source ZIP from committed files, never from the working directory."""
import argparse
from pathlib import Path,PurePosixPath
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def prohibited(name):
    path=PurePosixPath(name)
    leaf=path.name.lower()
    return (
        leaf in {"context.txt","candidate_context.txt","fix.py","rewrite.py",".env"}
        or leaf.startswith(".env.") and leaf!=".env.example"
        or leaf.endswith((".db",".sqlite",".pdf",".zip",".pem",".key"))
        or any(token in leaf for token in (".db-",".sqlite-"))
        or any(part in {".git",".venv","venv","backups","__pycache__","test-results"} for part in path.parts)
    )

def source_files():
    data=subprocess.check_output(["git","ls-tree","-r","--name-only","HEAD"],cwd=ROOT,text=True)
    names=data.splitlines()
    if any(prohibited(name) for name in names):
        raise ValueError("Committed tree contains a prohibited private/generated file; package aborted")
    return names

def build(output=None):
    source_files()
    commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    target=Path(output).resolve() if output else ROOT/"dist"/f"email-outreacher-{commit[:12]}.zip"
    if target.exists(): raise ValueError("Choose a new output path; releases are never overwritten")
    target.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(["git","archive","--format=zip","--prefix=email-outreacher/",f"--output={target}",commit],cwd=ROOT,check=True)
    return target,commit

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output")
    args=parser.parse_args()
    try:
        path,commit=build(args.output)
        print(f"{path}\nSource commit: {commit}")
    except ValueError as exc:
        parser.exit(1,str(exc)+"\n")
