from __future__ import annotations
import argparse, sys, json, sys, yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from tu_runtime.adapters import AdapterRegistry
from tu_runtime.core.contracts import ContractValidator

p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/discovery-contract-report.json')); args=p.parse_args()
errors=[]; checks=0
contracts=ContractValidator(ROOT)
for name in ('file-inventory-record','repository-discovery','application-discovery','adapter-manifest','adapter-extraction','adapter-run','adapter-capability-matrix'):
    checks+=1
    if name not in contracts.validators: errors.append(f'missing runtime contract: {name}')
for rel,contract_id in [('orchestrator/discovery-policy.yaml','TU-DISCOVERY-POLICY'),('orchestrator/language-adapter-policy.yaml','TU-LANGUAGE-ADAPTER-POLICY')]:
    checks+=1; obj=yaml.safe_load((ROOT/rel).read_text())
    if obj.get('contract',{}).get('id')!=contract_id: errors.append(f'bad policy id: {rel}')
registry=AdapterRegistry(ROOT); checks+=1
if len(registry.manifests)!=11: errors.append(f'expected 11 adapters, found {len(registry.manifests)}')
checks+=1
if [x for x,m in registry.manifests.items() if m['fallback']] != ['generic']: errors.append('generic must be sole fallback')
for adapter_id,manifest in registry.manifests.items():
    checks+=3
    if manifest['id']!=adapter_id: errors.append(f'adapter directory/id mismatch: {adapter_id}')
    if not manifest['capabilities']: errors.append(f'adapter lacks capabilities: {adapter_id}')
    if manifest['priority']<0: errors.append(f'invalid priority: {adapter_id}')
policy=yaml.safe_load((ROOT/'orchestrator/discovery-policy.yaml').read_text()); checks+=5
if policy['source_access']['mode']!='READ_ONLY': errors.append('discovery must be read-only')
if policy['source_access']['protected_content']!='deny': errors.append('protected content must be denied')
if policy['inventory']['deterministic_order']!='path-ascending': errors.append('inventory ordering must be deterministic')
if not policy['coverage']['repository_ledger'] or not policy['coverage']['application_ledger']: errors.append('coverage ledgers are required')
if policy['outputs']['root']!='discovery/<discovery-id>': errors.append('unexpected discovery output root')
report={'status':'PASS' if not errors else 'FAIL','checks':checks,'adapters':len(registry.manifests),'errors':errors}
Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2)); import os
sys.stdout.flush()
sys.stderr.flush()
os._exit(0 if not errors else 1)
