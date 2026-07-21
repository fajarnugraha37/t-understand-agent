from __future__ import annotations
import argparse,json,sys,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]
from tu_runtime.core.contracts import ContractValidator
from tu_runtime.core.graph import GraphManager
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/graph-contract-report.json')); args=p.parse_args()
errors=[]; checks=0; contracts=ContractValidator(ROOT)
for name in ('application-graph','cross-repository-relation','relationship-candidate'):
    checks+=1
    if name not in contracts.validators: errors.append(f'missing runtime contract: {name}')
policy=yaml.safe_load((ROOT/'orchestrator/application-graph-policy.yaml').read_text()); checks+=5
if policy.get('contract',{}).get('id')!='TU-APPLICATION-GRAPH-POLICY': errors.append('bad graph policy id')
requirements=' '.join(x['requirement'] for x in policy['rules'])
if 'both endpoints' not in requirements: errors.append('two-sided evidence rule missing')
if 'Exact contract keys' not in requirements: errors.append('exact contract key rule missing')
if 'unresolved candidates' not in requirements: errors.append('unresolved candidate rule missing')
if 'deterministic' not in requirements: errors.append('deterministic graph rule missing')
for skill in ('tu-cross-repository-linking',):
    checks+=1
    if len(list((ROOT/'skills').glob(f'**/{skill}/SKILL.md')))!=1: errors.append(f'missing skill: {skill}')
checks+=4
for method in ('create','validate','show','list'):
    if not hasattr(GraphManager,method): errors.append(f'GraphManager missing {method}')
report={'status':'PASS' if not errors else 'FAIL','checks':checks,'schemas':3,'errors':errors}
Path(args.report).write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); raise SystemExit(0 if not errors else 1)
