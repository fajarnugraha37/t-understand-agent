import argparse,json,yaml
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--report',default='reports/release-contract-report.json');args=parser.parse_args()
errors=[];checks=0
version=(ROOT/'VERSION').read_text().strip();checks+=1
if version!='1.0.3':errors.append('VERSION must be 1.0.3')
registry=yaml.safe_load((ROOT/'orchestrator/skill-registry.yaml').read_text())['skills']
registered={item['id'] for item in registry};physical={item.parent.name for item in (ROOT/'skills').rglob('SKILL.md')};checks+=len(registered)+len(physical)
if registered!=physical:errors.append(f'skill registry/package mismatch missing={sorted(registered-physical)} orphan={sorted(physical-registered)}')
for skill_id in sorted(registered):
 checks+=1
 if not skill_id.startswith('tu-'):errors.append(f'non-namespaced canonical skill: {skill_id}')
aggregate=ROOT/'adapters/codex/tu-understand/SKILL.md';checks+=2
if not aggregate.exists() or 'name: tu-understand\n' not in aggregate.read_text():errors.append('missing namespaced Codex aggregate skill')
if (ROOT/'adapters/codex/t-understand').exists():errors.append('legacy Codex aggregate skill remains')
checks+=1
if not (ROOT/'orchestrator/tool-permission-policy.yaml').exists():errors.append('missing tool permission policy')
for name in ('phase-16-assurance.md','phase-17-assurance.md','phase-18-assurance.md','phase-19-assurance.md','phase-20-assurance.md','tool-permissions-and-skill-namespace.md','agent-native-workflow.md','capability-greeting-and-artifact-documentation.md'):
 checks+=1
 if not (ROOT/'docs'/name).exists():errors.append(f'missing {name}')
for required in ('orchestrator/capabilities.yaml','runtime/tu_runtime/core/conversation.py','schemas/capability-catalog.schema.json','schemas/agent-operation-plan.schema.json','schemas/agent-completion.schema.json'):
 checks+=1
 if not (ROOT/required).exists():errors.append(f'missing {required}')
checks+=1
if 'tu-capability-help' not in registered:errors.append('missing tu-capability-help skill')
checks+=1
root_agent=(ROOT/'agents/t-understand/AGENT.md').read_text()
if 'DOCUMENTATION_GENERATION' not in root_agent or 'agent-document' not in root_agent or 'chat-only answer' not in root_agent:errors.append('root agent lacks artifact-first documentation routing')
result={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors};Path(args.report).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if not errors else 1)
