import argparse,json,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--report',default='reports/review-export-contract-report.json');a=p.parse_args()
errors=[];checks=0
for name in ['review-export-manifest']:
 checks+=2
 if not (ROOT/'schemas'/f'{name}.schema.json').exists(): errors.append(f'missing schema {name}')
 if f'"{name}"' not in (ROOT/'runtime/tu_runtime/core/contracts.py').read_text(): errors.append(f'unregistered contract {name}')
cli=(ROOT/'runtime/tu_runtime/cli.py').read_text()
for command in ['review-export-create','review-export-show','review-export-list','review-export-validate','review-export-profiles']:
 checks+=1
 if command not in cli: errors.append(f'missing command {command}')
module=(ROOT/'runtime/tu_runtime/core/reviewing.py').read_text()
for profile in ['canonical','github','gitlab','cli','json']:
 checks+=1
 if f'"{profile}"' not in module: errors.append(f'missing export profile {profile}')
skills=yaml.safe_load((ROOT/'orchestrator/skill-registry.yaml').read_text())['skills']
for sid in ['tu-change-walkthrough','tu-review-export']:
 checks+=2;item=next((x for x in skills if x['id']==sid),None)
 if not item or item['status']!='implemented': errors.append(f'skill not implemented: {sid}')
 if not (ROOT/'skills/review'/sid/'SKILL.md').exists(): errors.append(f'missing skill package: {sid}')
r={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors};Path(a.report).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if not errors else 1)
