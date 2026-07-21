import argparse,json,yaml
from pathlib import Path
from tu_runtime.core.qualification import PROFILES,RUNNERS,SCENARIOS
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--report',default='reports/qualification-contract-report.json');a=p.parse_args();errors=[];checks=0
profiles=yaml.safe_load((ROOT/'orchestrator/model-profiles.yaml').read_text())['profiles']
for x in PROFILES:checks+=1;errors += [] if x in profiles else [f'missing profile {x}']
checks+=1
if RUNNERS != ('contract-simulator',):errors.append('unexpected qualification runner set')
checks+=len(SCENARIOS)
if len(SCENARIOS)<6:errors.append('qualification scenarios incomplete')
text=(ROOT/'orchestrator/qualification-policy.yaml').read_text();checks+=1
if 'distinct from live-model qualification' not in text:errors.append('live-model claim boundary missing')
r={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors};Path(a.report).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if not errors else 1)
