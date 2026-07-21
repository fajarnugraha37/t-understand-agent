from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]
from tu_runtime.core.contracts import SCHEMA_FILES
from tu_runtime.core.exporting import PROFILES
import yaml
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/export-contract-report.json')); a=p.parse_args(); errors=[]; checks=0
for x in ('export-manifest','render-validation'): checks+=1; errors += [] if x in SCHEMA_FILES else [f'missing {x}']
for profile in PROFILES: checks+=1
if len(PROFILES)!=5: errors.append('five canonical export profiles required')
template=yaml.safe_load((ROOT/'templates/export/profiles.yaml').read_text()); checks+=1
if tuple(template['profiles']) != PROFILES: errors.append('export template profiles differ from runtime profiles')
for f in ('orchestrator/documentation-export-policy.yaml','runtime/tu_runtime/core/exporting.py'): checks+=1; errors += [] if (ROOT/f).exists() else [f'missing {f}']
r={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,'profiles':list(PROFILES)}; Path(a.report).write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2)); raise SystemExit(0 if not errors else 1)
