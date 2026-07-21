import argparse,json
from pathlib import Path
from datetime import datetime,timezone
from tu_runtime.core.integration import SCENARIOS
from tu_runtime.core.contracts import ContractValidator
p=argparse.ArgumentParser();p.add_argument('--input-dir',default='reports/integration-scenarios');p.add_argument('--report',default='reports/integration-test-report.json');a=p.parse_args();items=[];errors=[]
for x in SCENARIOS:
 f=Path(a.input_dir)/f"{x['id']}.json"
 if not f.exists():errors.append(f'missing {f}');continue
 d=json.loads(f.read_text());items.append({k:d[k] for k in ('id','status','assertions','duration_ms')});errors.extend(d.get('failures',[]))
r={'schema_id':'https://t-understand.dev/schemas/integration-report.schema.json','schema_version':'1.0.0','status':'PASS' if len(items)==len(SCENARIOS) and all(x['status']=='PASS' for x in items) and not errors else 'FAIL','scenarios':items,'checks':sum(x['assertions'] for x in items),'errors':errors,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')}
ContractValidator(Path(__file__).resolve().parents[1]).validate('integration-report',r);Path(a.report).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if r['status']=='PASS' else 1)
