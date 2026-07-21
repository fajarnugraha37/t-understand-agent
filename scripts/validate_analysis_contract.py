from __future__ import annotations
import argparse,json,sys,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]
from tu_runtime.core.contracts import ContractValidator
from tu_runtime.core.analysis import AnalysisManager
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/analysis-contract-report.json')); args=p.parse_args()
errors=[]; checks=0; contracts=ContractValidator(ROOT)
for name in ('evidence-record','analysis-entity','analysis-relation','analysis-observation','analysis-summary','analysis-run'):
    checks+=1
    if name not in contracts.validators: errors.append(f'missing runtime contract: {name}')
policy=yaml.safe_load((ROOT/'orchestrator/analysis-policy.yaml').read_text()); checks+=5
if policy.get('contract',{}).get('id')!='TU-ANALYSIS-POLICY': errors.append('bad analysis policy id')
if policy['source_access']['mode']!='READ_ONLY': errors.append('analysis source access must be READ_ONLY')
if policy['source_access']['execution']!='DENY': errors.append('analysis must deny source execution')
if not any(r['id']=='ANL-004' for r in policy['rules']): errors.append('incremental equivalence rule missing')
if not any(r['id']=='ANL-005' for r in policy['rules']): errors.append('atomic publication rule missing')
for skill in ('tu-structural-analysis','tu-behavior-analysis','tu-selective-reanalysis','tu-impact-identification'):
    checks+=1
    found=list((ROOT/'skills').glob(f'**/{skill}/SKILL.md'))
    if len(found)!=1: errors.append(f'missing or duplicate skill package: {skill}')
checks+=4
for method in ('run','refresh','validate','show'):
    if not hasattr(AnalysisManager,method): errors.append(f'AnalysisManager missing {method}')
report={'status':'PASS' if not errors else 'FAIL','checks':checks,'schemas':6,'errors':errors}
Path(args.report).write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); raise SystemExit(0 if not errors else 1)
