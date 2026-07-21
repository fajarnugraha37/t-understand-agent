import argparse, json
from pathlib import Path
from governance_lib import audit
p=argparse.ArgumentParser(); p.add_argument('--report',default='reports/governance-report.json'); args=p.parse_args()
r=audit(); Path(args.report).parent.mkdir(parents=True,exist_ok=True); Path(args.report).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
raise SystemExit(0 if r['status']=='PASS' else 1)
