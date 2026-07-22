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
 'multi-repository-adaptive-deep-documentation.md','graphify-first-repository-intelligence.md','ponytail-first-engineering.md',
):
 checks+=1
 if not (ROOT/'docs'/name).exists():errors.append(f'missing {name}')
for required in (
 'orchestrator/capabilities.yaml','orchestrator/documentation-generation-policy.yaml','orchestrator/modeling-policy.yaml',
 'orchestrator/repository-intelligence-policy.yaml','skills/discovery/tu-repository-intelligence/SKILL.md',
 'orchestrator/ponytail-engineering-policy.yaml','skills/foundation/tu-ponytail-engineering/SKILL.md',
 'runtime/tu_runtime/core/conversation.py','runtime/tu_runtime/core/workspace_discovery.py',
 'runtime/tu_runtime/core/modeling.py','runtime/tu_runtime/core/documentation.py',
 'schemas/capability-catalog.schema.json','schemas/agent-operation-plan.schema.json','schemas/agent-completion.schema.json',
 'schemas/agent-workspace-discovery.schema.json','schemas/documentation-requirements.schema.json',
 'schemas/documentation-generation-record.schema.json','tests/agent_native/test_multi_repo_documentation.py',
 'scripts/validate_graphify_integration.py','tests/graphify/test_graphify_integration.py',
 'scripts/validate_ponytail_integration.py','tests/ponytail/test_ponytail_integration.py','examples/ponytail-context.yaml',
):
 checks+=1
 if not (ROOT/required).exists():errors.append(f'missing {required}')
checks+=3
if 'tu-capability-help' not in registered:errors.append('missing tu-capability-help skill')
if 'tu-repository-intelligence' not in registered:errors.append('missing tu-repository-intelligence skill')
if 'tu-ponytail-engineering' not in registered:errors.append('missing tu-ponytail-engineering skill')
root_agent=(ROOT/'agents/t-understand/AGENT.md').read_text();checks+=11
for required_text in ('DOCUMENTATION_GENERATION','agent-document','chat-only answer','multi-repo','requirement, model-record','tu-repository-intelligence','Delegate that package once','tu-ponytail-engineering','Use a lightweight path','Delegate that context once','unsafe minimalism'):
 if required_text not in root_agent: errors.append(f'root agent lacks required contract: {required_text}')
policy=yaml.safe_load((ROOT/'orchestrator/documentation-generation-policy.yaml').read_text());checks+=7
publish=policy.get('planning',{}).get('publish_only_when',{})
for metric in ('requirement_coverage','model_record_coverage','required_section_coverage','repository_coverage','flow_coverage','inference_disclosure','section_traceability'):
 if publish.get(metric)!=1.0: errors.append(f'documentation policy does not require full {metric}')
repository_policy=yaml.safe_load((ROOT/'orchestrator/repository-intelligence-policy.yaml').read_text());checks+=4
if repository_policy.get('strategy')!='graphify-first-when-usable':errors.append('repository intelligence policy is not Graphify-first')
if repository_policy.get('query_policy',{}).get('automatically_install') is not False:errors.append('Graphify auto-install must be false')
if repository_policy.get('query_policy',{}).get('automatically_generate_graph') is not False:errors.append('Graphify graph generation must be opt-in')
if 'Do not stop the task.' not in repository_policy.get('failure_behavior',[]):errors.append('Graphify failure must be fail-open')
ponytail_policy=yaml.safe_load((ROOT/'orchestrator/ponytail-engineering-policy.yaml').read_text());checks+=8
if ponytail_policy.get('strategy')!='smallest-complete-solution':errors.append('Ponytail policy is not smallest-complete-solution')
if ponytail_policy.get('external_integration',{}).get('required') is not False:errors.append('external Ponytail integration must be optional')
if ponytail_policy.get('external_integration',{}).get('automatically_install') is not False:errors.append('Ponytail auto-install must be false')
if ponytail_policy.get('external_integration',{}).get('automatically_upgrade') is not False:errors.append('Ponytail auto-upgrade must be false')
if ponytail_policy.get('permissions',{}).get('expand_for_ponytail') is not False:errors.append('Ponytail must not expand permissions')
if len(ponytail_policy.get('decision_ladder',[]))!=9:errors.append('Ponytail decision ladder must contain nine ordered steps')
if 'small_task_path' not in ponytail_policy:errors.append('Ponytail policy lacks lightweight task path')
if 'correctness and required behavior' not in ponytail_policy.get('precedence',[]):errors.append('Ponytail policy lacks correctness precedence')
result={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors};Path(args.report).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if not errors else 1)
