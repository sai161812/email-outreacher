"""Inventory local artifacts and scan reachable Git blobs without printing secrets."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PATTERNS=[re.compile(rb'AIza[0-9A-Za-z_-]{30,}'),re.compile(rb'gh[pousr]_[0-9A-Za-z]{30,}'),
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]

def audit():
    refs=subprocess.check_output(['git','for-each-ref','--format=%(refname)','refs/heads','refs/remotes','refs/tags'],cwd=ROOT,text=True).splitlines()
    objects=subprocess.check_output(['git','rev-list','--objects','--all'],cwd=ROOT,text=True).splitlines()
    private=[];paths={}
    for entry in objects:
        oid,_,name=entry.partition(' ');paths[oid]=name
        leaf=Path(name).name.lower()
        if leaf in {'context.txt','candidate_context.txt','.env'} or leaf.endswith(('.db','.sqlite','.pdf','.pem','.key')) or (leaf.startswith('.env.') and leaf!='.env.example'):
            private.append({'object':oid,'path':name})
    matches=[];skipped=[];scanned=0
    process=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        for oid,name in paths.items():
            process.stdin.write((oid+'\n').encode());process.stdin.flush()
            header=process.stdout.readline().split()
            size=int(header[2]);kind=header[1]
            if size>2*1024*1024:
                remaining=size
                while remaining:
                    block=process.stdout.read(min(65536,remaining));remaining-=len(block)
                if kind==b'blob': skipped.append({'object':oid,'path':name,'reason':'larger than 2 MiB'})
            else:
                data=process.stdout.read(size)
                if kind==b'blob':
                    scanned+=1
                    if any(pattern.search(data) for pattern in PATTERNS): matches.append({'object':oid,'path':name})
            process.stdout.read(1)
    finally:
        process.stdin.close();process.stdout.close();process.wait(timeout=10)
    inventory={name:[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size} for p in (ROOT/name).rglob('*') if p.is_file()]
        for name in ('dist','release','backups') if (ROOT/name).exists()}
    environments=[p.name for p in ROOT.iterdir() if p.is_dir() and (p.name=='venv' or p.name.startswith('.venv'))]
    return {'refs':refs,'unique_blobs_scanned':scanned,'credential_shape_candidates':matches,'historical_private_paths':private,
        'unscanned_large_blobs':skipped,'artifact_inventory':inventory,'environments':environments,
        'limits':'Shape scan only, not a credential guarantee. Candidate values are never printed. No deletion, rewriting or secret validation was performed.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Choose a new output path')
    report=audit();args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf8') as file: json.dump(report,file,indent=2)
    print(json.dumps({'refs':len(report['refs']),'blobs_scanned':report['unique_blobs_scanned'],
        'credential_shape_candidates':len(report['credential_shape_candidates']),'historical_private_paths':len(report['historical_private_paths']),
        'large_blobs_not_scanned':len(report['unscanned_large_blobs']),'environments':report['environments'],
        'artifact_counts':{k:len(v) for k,v in report['artifact_inventory'].items()}}))

if __name__=='__main__': main()
