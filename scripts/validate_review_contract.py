import argparse,json,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--report',default='reports/review-contract-report.json');a=p.parse_args()
errors=[];checks=0
schemas=['review-changed-file','review-coverage','review-analysis','review-finding','finding-critique','severity-calibration','review-verification','review-manifest']
contracts=(ROOT/'runtime/tu_runtime/core/contracts.py').read_text();cli=(ROOT/'runtime/tu_runtime/cli.py').read_text();skills=yaml.safe_load((ROOT/'orchestrator/skill-registry.yaml').read_text())['skills'];policy=yaml.safe_load((ROOT/'orchestrator/review-policy.yaml').read_text())
for name in schemas:
 checks+=2
 if not (ROOT/'schemas'/f'{name}.schema.json').exists(): errors.append(f'missing schema {name}')
 if f'"{name}"' not in contracts: errors.append(f'unregistered runtime contract {name}')
for command in ['review-run','review-show','review-list','review-findings','review-validate']:
 checks+=1
 if command not in cli: errors.append(f'missing CLI command {command}')
for sid in ['tu-diff-analysis','tu-static-codebase-audit','tu-impact-tracing','tu-specialized-review','tu-finding-deduplication','tu-finding-critique','tu-severity-calibration','tu-review-verification']:
 checks+=2; item=next((x for x in skills if x['id']==sid),None)
 if not item or item['status']!='implemented': errors.append(f'skill not implemented: {sid}')
 if not (ROOT/'skills/review'/sid/'SKILL.md').exists(): errors.append(f'missing skill package: {sid}')
for rule in [f'REV-00{x}' for x in range(1,9)]:
 checks+=1
 if not any(x['id']==rule for x in policy['rules']): errors.append(f'missing policy rule {rule}')
r={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors};Path(a.report).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if not errors else 1)
