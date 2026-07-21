import argparse, json, yaml
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(); p.add_argument('--report',default='reports/contract-test-report.json'); args=p.parse_args()
results=[]
for ex in sorted((root/'examples/contracts').glob('*.yaml')):
    obj=yaml.safe_load(ex.read_text()); schema_name=obj['schema_id'].rsplit('/',1)[-1]
    schema=json.loads((root/'schemas'/schema_name).read_text())
    errors=list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(obj))
    results.append({'example':ex.name,'status':'PASS' if not errors else 'FAIL','errors':[e.message for e in errors]})
# Explicit negative schema semantics
claim=yaml.safe_load((root/'examples/contracts/claim.yaml').read_text()); claim['evidence']=[]
schema=json.loads((root/'schemas/claim.schema.json').read_text()); rejected=bool(list(Draft202012Validator(schema).iter_errors(claim)))
results.append({'example':'FACT without evidence is rejected','status':'PASS' if rejected else 'FAIL','errors':[] if rejected else ['invalid FACT accepted']})
finding=yaml.safe_load((root/'examples/contracts/review-finding.yaml').read_text()); finding['critic_status']='pending'
schema=json.loads((root/'schemas/review-finding.schema.json').read_text()); rejected=bool(list(Draft202012Validator(schema).iter_errors(finding)))
results.append({'example':'MAJOR finding without completed critic challenge is rejected','status':'PASS' if rejected else 'FAIL','errors':[] if rejected else ['unchallenged major finding accepted']})
status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL'
out={'status':status,'cases':len(results),'results':results}; Path(args.report).parent.mkdir(parents=True,exist_ok=True); Path(args.report).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2)); raise SystemExit(0 if status=='PASS' else 1)
