from __future__ import annotations
import argparse,json,sys,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]
from tu_runtime.core.contracts import ContractValidator
from tu_runtime.core.memory import MemoryManager
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/memory-contract-report.json')); args=p.parse_args()
errors=[]; checks=0; contracts=ContractValidator(ROOT)
for name in ('claim','memory-manifest','memory-invalidation','memory-critique','memory-verification','freshness-assessment'):
    checks+=1
    if name not in contracts.validators: errors.append(f'missing runtime contract: {name}')
policy=yaml.safe_load((ROOT/'orchestrator/canonical-memory-policy.yaml').read_text()); checks+=6
if policy.get('contract',{}).get('id')!='TU-CANONICAL-MEMORY-POLICY': errors.append('bad canonical memory policy id')
requirements=' '.join(x['requirement'] for x in policy['rules'])
for phrase in ('immutable','FACT claims require current evidence','Conflicts are preserved','rebuildable indexes','Invalidation propagates'):
    checks+=1
    if phrase not in requirements: errors.append(f'missing memory guarantee: {phrase}')
for skill in ('tu-memory-consolidation','tu-memory-critique','tu-memory-verification','tu-memory-invalidation','tu-freshness-check','tu-change-detection'):
    checks+=1
    if len(list((ROOT/'skills').glob(f'**/{skill}/SKILL.md')))!=1: errors.append(f'missing skill: {skill}')
for method in ('build','validate','critique','invalidate','freshness','rebuild_index','search'):
    checks+=1
    if not hasattr(MemoryManager,method): errors.append(f'MemoryManager missing {method}')
report={'status':'PASS' if not errors else 'FAIL','checks':checks,'schemas':6,'errors':errors}
Path(args.report).write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); raise SystemExit(0 if not errors else 1)
