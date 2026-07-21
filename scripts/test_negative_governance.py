import argparse, json, yaml
from copy import deepcopy
from pathlib import Path
from governance_lib import ROOT, canonical_data, audit
p=argparse.ArgumentParser(); p.add_argument('--report',default='reports/negative-test-report.json'); args=p.parse_args()
cases=yaml.safe_load((ROOT/'tests/negative/governance-cases.yaml').read_text())['cases']
results=[]
for case in cases:
    d=deepcopy(canonical_data()); parts=case['target'].split('.'); cur=d
    for x in parts[:-1]: cur=cur[int(x)] if x.isdigit() else cur[x]
    key=parts[-1]; target=cur[int(key)] if key.isdigit() else cur[key]
    op=case.get('operation','set')
    if op=='append': target.append(case['value'])
    elif op=='remove': target.remove(case['value'])
    else:
        if key.isdigit(): cur[int(key)]=case['value']
        else: cur[key]=case['value']
    report=audit(d); codes={e['code'] for e in report['errors']}; passed=case['expected'] in codes
    results.append({'id':case['id'],'expected':case['expected'],'observed':sorted(codes),'status':'PASS' if passed else 'FAIL'})
status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL'
out={'status':status,'cases':len(results),'results':results}
Path(args.report).parent.mkdir(parents=True,exist_ok=True); Path(args.report).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2)); raise SystemExit(0 if status=='PASS' else 1)
