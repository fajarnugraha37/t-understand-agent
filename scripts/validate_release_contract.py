import argparse,json,yaml
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--report',default='reports/release-contract-report.json');args=parser.parse_args()
errors=[];checks=0
version=(ROOT/'VERSION').read_text().strip();checks+=1
if version!='1.1.0':errors.append('VERSION must be 1.1.0')
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
for name in (
 'phase-16-assurance.md','phase-17-assurance.md','phase-18-assurance.md','phase-19-assurance.md','phase-20-assurance.md',
 'tool-permissions-and-skill-namespace.md','agent-native-workflow.md','capability-greeting-and-artifact-documentation.md',
 'multi-repository-adaptive-deep-documentation.md',
):
 checks+=1
 if not (ROOT/'docs'/name).exists():errors.append(f'missing {name}')
for required in (
 'orchestrator/capabilities.yaml','orchestrator/documentation-generation-policy.yaml','orchestrator/modeling-policy.yaml',
 'runtime/tu_runtime/core/conversation.py','runtime/tu_runtime/core/workspace_discovery.py',
 'runtime/tu_runtime/core/modeling.py','runtime/tu_runtime/core/documentation.py',
 'schemas/capability-catalog.schema.json','schemas/agent-operation-plan.schema.json','schemas/agent-completion.schema.json',
 'schemas/agent-workspace-discovery.schema.json','schemas/documentation-requirements.schema.json',
 'schemas/documentation-generation-record.schema.json','tests/agent_native/test_multi_repo_documentation.py',
):
 checks+=1
 if not (ROOT/required).exists():errors.append(f'missing {required}')
checks+=1
if 'tu-capability-help' not in registered:errors.append('missing tu-capability-help skill')
root_agent=(ROOT/'agents/t-understand/AGENT.md').read_text();checks+=5
for required_text in ('DOCUMENTATION_GENERATION','agent-document','chat-only answer','multi-repo','requirement, model-record'):
 if required_text not in root_agent: errors.append(f'root agent lacks required contract: {required_text}')
policy=yaml.safe_load((ROOT/'orchestrator/documentation-generation-policy.yaml').read_text());checks+=7
publish=policy.get('planning',{}).get('publish_only_when',{})
for metric in ('requirement_coverage','model_record_coverage','required_section_coverage','repository_coverage','flow_coverage','inference_disclosure','section_traceability'):
 if publish.get(metric)!=1.0: errors.append(f'documentation policy does not require full {metric}')
result={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors};Path(args.report).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if not errors else 1)
