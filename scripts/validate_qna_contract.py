import argparse,json,re,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--report',default='reports/qna-contract-report.json');a=p.parse_args()
errors=[];checks=0
required_schemas=['qna-retrieval-set','direct-source-verification','qna-answer','answer-critique','citation-validation','qna-manifest']
contracts=(ROOT/'runtime/tu_runtime/core/contracts.py').read_text();cli=(ROOT/'runtime/tu_runtime/cli.py').read_text();policy=yaml.safe_load((ROOT/'orchestrator/qna-policy.yaml').read_text());skills=yaml.safe_load((ROOT/'orchestrator/skill-registry.yaml').read_text())['skills']
for name in required_schemas:
 checks+=2
 if not (ROOT/'schemas'/f'{name}.schema.json').exists(): errors.append(f'missing schema {name}')
 if f'"{name}"' not in contracts: errors.append(f'unregistered runtime contract {name}')
for command in ['qna-ask','qna-show','qna-answer','qna-list','qna-validate','qna-critique']:
 checks+=1
 if command not in cli: errors.append(f'missing CLI command {command}')
for sid in ['tu-evidence-retrieval','tu-direct-source-verification','tu-answer-synthesis','tu-answer-critique','tu-citation-validation']:
 checks+=2; item=next((x for x in skills if x['id']==sid),None)
 if not item or item['status']!='implemented': errors.append(f'skill not implemented: {sid}')
 if not list((ROOT/'skills/qna'/sid).glob('SKILL.md')): errors.append(f'missing skill package: {sid}')
for rule in ['QNA-001','QNA-002','QNA-003','QNA-004','QNA-005','QNA-006']:
 checks+=1
 if not any(x['id']==rule for x in policy['rules']): errors.append(f'missing policy rule {rule}')
r={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors};Path(a.report).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if not errors else 1)
