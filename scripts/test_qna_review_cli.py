from __future__ import annotations
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--report',default='reports/qna-review-cli-report.json');a=p.parse_args()
cases=[(['--help'],0),(['review-export-profiles'],0),(['qna-list'],0),(['review-list'],0),(['review-export-list'],0)]
checks=[];errors=[]
for args,expected in cases:
    try:
        cp=subprocess.run([str(ROOT/'bin/t-understand'),*args],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        checks.append({'command':' '.join(args),'returncode':cp.returncode})
        if cp.returncode!=expected: errors.append({'command':args,'expected':expected,'actual':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr})
    except subprocess.TimeoutExpired: errors.append({'command':args,'error':'timeout'})
r={'status':'PASS' if not errors else 'FAIL','checks':len(checks),'errors':errors,'commands':checks};Path(a.report).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if not errors else 1)
