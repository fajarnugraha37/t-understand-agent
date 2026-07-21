import argparse,json,yaml
from pathlib import Path
from tu_runtime.core.contracts import ContractValidator
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--report',default='reports/quality-contract-report.json');a=p.parse_args();errors=[];checks=0
for name in ('quality-report','quality-manifest'):
 checks+=1
 if name not in ContractValidator(ROOT).validators:errors.append(f'missing validator {name}')
arts={x['id']:x for x in yaml.safe_load((ROOT/'orchestrator/artifact-registry.yaml').read_text())['artifacts']}
for aid in ('quality-report','integration-report','release-qualification'):
 checks+=1
 if aid not in arts:errors.append(f'missing artifact {aid}')
policy=yaml.safe_load((ROOT/'orchestrator/quality-plane-policy.yaml').read_text());checks+=len(policy['rules'])
if len(policy['rules'])<5:errors.append('quality plane policy incomplete')
r={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors};Path(a.report).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if not errors else 1)
